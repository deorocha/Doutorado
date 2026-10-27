"""Hardware: eixos Z (mock / ESP8266) e câmera."""
from __future__ import annotations

import time
from typing import Optional, Tuple

import cv2
import numpy as np

from .serial_utils import open_serial_robust, HAS_PYSERIAL

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# ======================================================================
# Mock
# ======================================================================

def _prepare_base_image(img: np.ndarray, max_dim: int = 1280) -> np.ndarray:
    h, w = img.shape[:2]
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        img = cv2.resize(
            img,
            (max(1, int(round(w * scale))), max(1, int(round(h * scale)))),
            interpolation=cv2.INTER_AREA,
        )
    return img


def load_uploaded_image(uploaded_file) -> Optional[np.ndarray]:
    """Carrega imagem do st.file_uploader. Aceita PNG, JPEG, TIFF (8/16-bit).

    Tenta OpenCV; se falhar, tenta PIL. Normaliza dtype → uint8.
    Retorna ndarray (grayscale 2D ou BGR 3D) ou None.
    """
    if uploaded_file is None:
        return None
    try:
        file_bytes = np.frombuffer(uploaded_file.read(), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_UNCHANGED)

        if img is None:
            try:
                import io
                from PIL import Image
                pil_img = Image.open(io.BytesIO(file_bytes))
                if pil_img.mode == "P":
                    pil_img = pil_img.convert("RGB")
                arr = np.array(pil_img)
                if arr.ndim == 3 and arr.shape[2] == 3:
                    arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
                img = arr
            except Exception:
                pass

        if img is None:
            return None

        if img.dtype == np.uint16:
            img = np.clip(img / 257.0, 0, 255).astype(np.uint8)
        elif img.dtype != np.uint8:
            f = img.astype(np.float64)
            rng = f.max() - f.min()
            img = (np.zeros(f.shape, np.uint8) if rng < 1e-9
                   else (((f - f.min()) / rng) * 255.0).astype(np.uint8))

        if img.ndim == 3 and img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        if img.ndim not in (2, 3):
            return None
        if img.ndim == 3 and img.shape[2] == 1:
            img = img[:, :, 0]
        if img.ndim == 3 and img.shape[2] not in (1, 3):
            return None
        return img
    except Exception:
        return None


class MockZAxis:
    def __init__(self, pos: float = 0.0):
        self.pos = float(pos)
    def move_to_mm(self, p: float) -> None: self.pos = float(p)
    def wait_until_idle(self) -> None: pass
    def close(self) -> None: pass


class MockCamera:
    """Simula desfoque Gaussiano em função da distância a `true_focus`."""

    def __init__(self, zaxis: MockZAxis, true_focus_mm: float = 22.0,
                 size: Tuple[int, int] = (512, 640),
                 base_image: Optional[np.ndarray] = None):
        self.z = zaxis
        self.true_focus = float(true_focus_mm)
        if base_image is not None:
            self._base = _prepare_base_image(base_image)
            self.size = self._base.shape[:2]
        else:
            self.size = size
            self._base = self._make_base()

    def _make_base(self) -> np.ndarray:
        h, w = self.size
        rng = np.random.default_rng(42)
        img = np.zeros((h, w), np.uint8)
        for y in range(30, h - 30, 40):
            for x in range(30, w - 30, 40):
                cv2.circle(img,
                           (x + int(rng.integers(-8, 8)),
                            y + int(rng.integers(-8, 8))),
                           int(rng.integers(6, 12)),
                           int(rng.integers(120, 230)), -1)
        for _ in range(25):
            cv2.line(img,
                     (int(rng.integers(0, w)), int(rng.integers(0, h))),
                     (int(rng.integers(0, w)), int(rng.integers(0, h))),
                     int(rng.integers(80, 200)), 1)
        return img

    def capture(self) -> np.ndarray:
        sigma = abs(self.true_focus - self.z.pos) * 0.2
        return self._base.copy() if sigma < 0.3 else \
            cv2.GaussianBlur(self._base, (0, 0), sigma)

    def close(self) -> None: pass


# ======================================================================
# ESP8266 — base comum
# ======================================================================

class _ESPBase:
    """Lógica compartilhada de eixo Z via ESP8266.

    Subclasses implementam apenas os 5 métodos `_tx_*`.
    """
    def move_to_mm(self, p: float) -> None:
        self._tx_command(f"Z{float(p):.4f}")

    def wait_until_idle(self) -> None:
        self._tx_wait()

    def read_z_steps_per_mm(self) -> Optional[float]:
        return self._tx_read_spm()

    def send_setting(self, name: str, value) -> None:
        self._tx_command(f"{name}={value}")

    def close(self) -> None:
        self._tx_close()

    # interface abstrata
    def _tx_command(self, c: str) -> None: raise NotImplementedError
    def _tx_wait(self) -> None: raise NotImplementedError
    def _tx_read_spm(self) -> Optional[float]: raise NotImplementedError
    def _tx_close(self) -> None: raise NotImplementedError


class ESP8266SerialZAxis(_ESPBase):
    def __init__(self, port: str, baud: int = 115200,
                 handshake_timeout: float = 8.0):
        if not HAS_PYSERIAL:
            raise ImportError("Instale pyserial: pip install pyserial")
        self.ser = open_serial_robust(port, baud, timeout=1.0)
        time.sleep(2.0)
        self.ser.reset_input_buffer()

        ultimas: list = []
        alive = False
        t0 = time.time()
        while time.time() - t0 < handshake_timeout and not alive:
            try:
                self.ser.write(b"PING\n$102?\n")
            except Exception:
                pass
            tt = time.time()
            while time.time() - tt < 0.5:
                try:
                    line = self.ser.readline().decode(errors="ignore").strip()
                except Exception:
                    break
                if not line:
                    break
                ultimas.append(line)
                ultimas[:] = ultimas[-8:]
                if line in ("PONG", "ok") or line.startswith("$102="):
                    alive = True
                    break

        if not alive:
            self.ser.close()
            raise RuntimeError(
                f"ESP não respondeu em {handshake_timeout:.0f}s.\n"
                f"Últimas: {ultimas}\n"
                f"Verifique: firmware, Monitor Serial fechado, baud 115200."
            )
        self.ser.reset_input_buffer()

    def _tx_command(self, c: str) -> None:
        self.ser.write((c + "\n").encode())
        t0 = time.time()
        while time.time() - t0 < 30.0:
            line = self.ser.readline().decode(errors="ignore").strip()
            if not line:
                continue
            if line == "ok":
                return
            if line.startswith("error"):
                raise RuntimeError(f"Firmware: '{line}' em '{c}'")
        raise TimeoutError(f"Firmware não respondeu '{c}' em 30s")

    def _tx_wait(self) -> None:
        self.ser.write(b"W\n")
        t0 = time.time()
        while time.time() - t0 < 60.0:
            line = self.ser.readline().decode(errors="ignore").strip()
            if line == "ok":
                return
        raise TimeoutError("Aguardar fim do movimento excedeu 60s")

    def _tx_read_spm(self) -> Optional[float]:
        self.ser.write(b"$102?\n")
        t0 = time.time()
        while time.time() - t0 < 3.0:
            line = self.ser.readline().decode(errors="ignore").strip()
            if line.startswith("$102="):
                try:
                    return float(line.split("=", 1)[1])
                except ValueError:
                    return None
        return None

    def _tx_close(self) -> None:
        try: self.ser.close()
        except Exception: pass


class ESP8266WiFiZAxis(_ESPBase):
    def __init__(self, host: str, timeout_s: float = 60.0):
        if not HAS_REQUESTS:
            raise ImportError("Instale requests: pip install requests")
        if not host.startswith("http"):
            host = f"http://{host}"
        self.base = host.rstrip("/")
        self.timeout = float(timeout_s)
        try:
            requests.get(f"{self.base}/spm", timeout=5).raise_for_status()
        except Exception as e:
            raise RuntimeError(f"ESP8266 não respondeu em {self.base}: {e}")

    def _tx_command(self, c: str) -> None:
        if c.startswith("Z"):
            r = requests.get(f"{self.base}/move",
                             params={"mm": float(c[1:])}, timeout=10)
        elif c.startswith("$102="):
            r = requests.post(f"{self.base}/spm",
                              data={"v": c.split("=", 1)[1]}, timeout=5)
        else:
            raise ValueError(f"Comando não suportado em HTTP: {c}")
        r.raise_for_status()

    def _tx_wait(self) -> None:
        r = requests.get(f"{self.base}/wait", timeout=self.timeout)
        r.raise_for_status()

    def _tx_read_spm(self) -> Optional[float]:
        try:
            r = requests.get(f"{self.base}/spm", timeout=5)
            r.raise_for_status()
            return float(r.text.strip())
        except Exception:
            return None

    def _tx_close(self) -> None:
        pass


# ======================================================================
# Câmera real
# ======================================================================

class OpenCVCamera:
    def __init__(self, index: int = 0, width: int = 1280, height: int = 1024):
        self.cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            raise RuntimeError(f"Não abriu câmera índice {index}")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
        self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)

    def capture(self) -> np.ndarray:
        ok, frame = self.cap.read()
        if not ok:
            raise RuntimeError("Falha na captura")
        return frame

    def close(self) -> None:
        try: self.cap.release()
        except Exception: pass
