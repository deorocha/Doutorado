"""
streamlit_autofocus.py — Autofoco Z com 4 métricas em interface Streamlit.

Versão 2.5 — correções aplicadas:
  - Nova aba "📊 Histogramas" (pico por métrica + comparação foco vs. desfoque).
  - Medição de tempo por métrica (acurácia + tempo comparados).
  - Tabela formatada (coarse/refine explicados, decimais consistentes).
  - Gráfico não aparece duplicado (placeholders limpos ao final do sweep).
  - Melhores imagens em grade 2×2.

Hardware:
  - Mock (demo): sem hardware.
  - ESP8266 Serial USB: Wemos D1 R2 + ZAxis_Nema17_Wemos.ino.
  - ESP8266 WiFi (HTTP): mesmo firmware, interface HTTP.

Pré-requisitos:
  pip install pyserial requests
"""
from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

try:
    import serial as pyserial
    HAS_PYSERIAL = True
except ImportError:
    HAS_PYSERIAL = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# ======================================================================
# 1) Métricas de foco
# ======================================================================

def _to_gray(img: np.ndarray) -> np.ndarray:
    if img.ndim == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


def metric_laplacian(img: np.ndarray) -> float:
    return float(cv2.Laplacian(_to_gray(img), cv2.CV_64F).var())


def metric_tenengrad(img: np.ndarray) -> float:
    g = _to_gray(img).astype(np.float64)
    gx = cv2.Sobel(g, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(g, cv2.CV_64F, 0, 1, ksize=3)
    return float((gx * gx + gy * gy).mean())


def metric_brenner(img: np.ndarray, k: int = 2) -> float:
    g = _to_gray(img).astype(np.float64)
    dx = g[:, k:] - g[:, :-k]
    dy = g[k:, :] - g[:-k, :]
    return float((dx * dx).mean() + (dy * dy).mean())


def metric_fft_hf(img: np.ndarray, radius_frac: float = 1 / 8) -> float:
    g = _to_gray(img).astype(np.float64)
    wy = np.hamming(g.shape[0])[:, None]
    wx = np.hamming(g.shape[1])[None, :]
    g = g * wy * wx
    M = np.abs(np.fft.fftshift(np.fft.fft2(g)))
    h, w = M.shape
    cy, cx = h // 2, w // 2
    Y, X = np.ogrid[:h, :w]
    r = int(min(h, w) * radius_frac)
    mask = (Y - cy) ** 2 + (X - cx) ** 2 > r * r
    return float(M[mask].mean())


METRICS = {
    "laplacian": metric_laplacian,
    "tenengrad": metric_tenengrad,
    "brenner":   metric_brenner,
    "fft_hf":    metric_fft_hf,
}
DISPLAY = {
    "laplacian": "Var. Laplaciano",
    "tenengrad": "Tenengrad",
    "brenner":   "Brenner",
    "fft_hf":    "FFT (alta freq.)",
}

DEFAULT_SPM = 400.0


# ======================================================================
# 2) Serial robusto (contorna OSError(22) do CH340 no Windows)
# ======================================================================

def _open_serial_robust(port: str, baud: int = 115200,
                        timeout: float = 1.0,
                        attempts: int = 3) -> "pyserial.Serial":
    if not HAS_PYSERIAL:
        raise ImportError("Instale pyserial: pip install pyserial")

    last_err: Optional[Exception] = None
    for attempt in range(attempts):
        try:
            return pyserial.Serial(port=port, baudrate=baud, timeout=timeout)
        except OSError as e:
            last_err = e
            if attempt < attempts - 1:
                time.sleep(0.5)

    try:
        ser = pyserial.Serial()
        ser.port = port
        ser.baudrate = baud
        ser.timeout = timeout
        ser.dtr = False
        ser.rts = False
        ser.open()
        return ser
    except OSError as e:
        last_err = e

    raise RuntimeError(
        f"Não foi possível abrir {port} ({baud} baud).\n"
        f"Erro: {last_err}\n\n"
        f"Verifique na ordem:\n"
        f"  1. Monitor Serial do Arduino IDE FECHADO?\n"
        f"  2. Cura, Pronterface, VSCode/PlatformIO — algum aberto?\n"
        f"  3. Desconecte e reconecte o cabo USB.\n"
        f"  4. Tente outra porta USB (traseira, direto na placa-mãe).\n"
        f"  5. Reinstale o driver CH340 (wch.cn → CH341SER).\n"
        f"  6. Reinicie o PC."
    ) from last_err


# ======================================================================
# 3) Hardware — Mock
# ======================================================================

class MockZAxis:
    def __init__(self, pos: float = 0.0):
        self.pos = float(pos)
    def move_to_mm(self, p: float) -> None:
        self.pos = float(p)
    def wait_until_idle(self) -> None:
        pass
    def close(self) -> None:
        pass


class MockCamera:
    def __init__(self, zaxis: MockZAxis, true_focus_mm: float = 22.0,
                 size: Tuple[int, int] = (512, 640)):
        self.z = zaxis
        self.true_focus = float(true_focus_mm)
        self.size = size
        self._base = self._make_base()

    def _make_base(self) -> np.ndarray:
        h, w = self.size
        rng = np.random.default_rng(42)
        img = np.zeros((h, w), np.uint8)
        for y in range(30, h - 30, 40):
            for x in range(30, w - 30, 40):
                cy = y + int(rng.integers(-8, 8))
                cx = x + int(rng.integers(-8, 8))
                r = int(rng.integers(6, 12))
                v = int(rng.integers(120, 230))
                cv2.circle(img, (cx, cy), r, v, -1)
        for _ in range(25):
            p1 = (int(rng.integers(0, w)), int(rng.integers(0, h)))
            p2 = (int(rng.integers(0, w)), int(rng.integers(0, h)))
            cv2.line(img, p1, p2, int(rng.integers(80, 200)), 1)
        return img

    def capture(self) -> np.ndarray:
        sigma = abs(self.true_focus - self.z.pos) * 0.2
        if sigma < 0.3:
            return self._base.copy()
        return cv2.GaussianBlur(self._base, (0, 0), sigma)

    def close(self) -> None:
        pass


# ======================================================================
# 4) Hardware — ESP8266 Serial
# ======================================================================

class ESP8266SerialZAxis:
    def __init__(self, port: str, baud: int = 115200,
                 handshake_timeout: float = 8.0):
        if not HAS_PYSERIAL:
            raise ImportError("Instale pyserial: pip install pyserial")

        self.ser = _open_serial_robust(port, baud, timeout=1.0)
        time.sleep(2.0)
        self.ser.reset_input_buffer()

        alive = False
        ultimas = []
        t0 = time.time()
        while time.time() - t0 < handshake_timeout and not alive:
            try:
                self.ser.write(b"PING\n")
                self.ser.write(b"$102?\n")
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
                if (line == "PONG"
                        or line.startswith("$102=")
                        or line == "ok"):
                    alive = True
                    break

        if not alive:
            self.ser.close()
            raise RuntimeError(
                f"ESP não respondeu a PING/$102? em "
                f"{handshake_timeout:.0f}s.\n"
                f"Últimas mensagens: {ultimas}\n"
                f"Verifique: (1) firmware v2; (2) Monitor Serial fechado; "
                f"(3) baudrate 115200; (4) cabo USB com dados."
            )

        self.ser.reset_input_buffer()

    def _cmd(self, c: str, timeout: float = 30.0) -> str:
        self.ser.write((c + "\n").encode())
        t0 = time.time()
        while time.time() - t0 < timeout:
            line = self.ser.readline().decode(errors="ignore").strip()
            if not line:
                continue
            if line == "ok":
                return line
            if line.startswith("error"):
                raise RuntimeError(f"Firmware: '{line}' a '{c}'")
        raise TimeoutError(f"Firmware não respondeu '{c}' em {timeout:.0f}s")

    def move_to_mm(self, p: float) -> None:
        self._cmd(f"Z{p:.4f}")

    def wait_until_idle(self) -> None:
        self._cmd("W", timeout=60.0)

    def read_z_steps_per_mm(self) -> Optional[float]:
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

    def send_setting(self, name: str, value) -> None:
        self._cmd(f"{name}={value}")

    def close(self) -> None:
        try:
            self.ser.close()
        except Exception:
            pass


class ESP8266WiFiZAxis:
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

    def move_to_mm(self, p: float) -> None:
        r = requests.get(f"{self.base}/move",
                         params={"mm": float(p)}, timeout=10)
        r.raise_for_status()

    def wait_until_idle(self) -> None:
        r = requests.get(f"{self.base}/wait", timeout=self.timeout)
        r.raise_for_status()

    def read_z_steps_per_mm(self) -> Optional[float]:
        try:
            r = requests.get(f"{self.base}/spm", timeout=5)
            r.raise_for_status()
            return float(r.text.strip())
        except Exception:
            return None

    def send_setting(self, name: str, value) -> None:
        if name != "$102":
            raise ValueError(f"setting {name} não suportado")
        r = requests.post(f"{self.base}/spm", data={"v": value}, timeout=5)
        r.raise_for_status()

    def close(self) -> None:
        pass


# ======================================================================
# 5) Hardware — Câmera
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
        try:
            self.cap.release()
        except Exception:
            pass


# ======================================================================
# 6) Sweep (com medição de tempo por métrica)
# ======================================================================

def run_sweep(zaxis, camera, cfg: dict):
    samples: List[dict] = []

    def measure(z: float, phase: str) -> dict:
        zaxis.move_to_mm(z)
        zaxis.wait_until_idle()
        if cfg["settle_s"] > 0:
            time.sleep(cfg["settle_s"])
        img = camera.capture()
        if cfg["roi"] is not None:
            y0, y1, x0, x1 = cfg["roi"]
            img = img[y0:y1, x0:x1]
        gray = _to_gray(img)

        scores: Dict[str, float] = {}
        times: Dict[str, float] = {}
        for name, fn in cfg["metrics"].items():
            try:
                t_metric = time.perf_counter()
                scores[name] = float(fn(gray))
                times[name] = time.perf_counter() - t_metric
            except Exception:
                scores[name] = float("nan")
                times[name] = float("nan")

        path = None
        if cfg["save_dir"] is not None:
            path = str(Path(cfg["save_dir"]) / f"{phase}_z{z:09.3f}.png")
            cv2.imwrite(path, img)
        return {"z_mm": float(z), "scores": scores, "times": times,
                "phase": phase, "img_path": path}

    n_targets = (len(cfg["metrics"]) if cfg["refine_mode"] == "each" else 1)
    total_ub = cfg["n_coarse"] + cfg["n_refine"] * n_targets

    zs = np.linspace(cfg["z_min"], cfg["z_max"], cfg["n_coarse"])
    step = 0
    for z in zs:
        s = measure(float(z), "coarse")
        samples.append(s)
        step += 1
        yield step, total_ub, s, samples

    coarse = [s for s in samples if s["phase"] == "coarse"]
    z_step = (cfg["z_max"] - cfg["z_min"]) / max(1, cfg["n_coarse"] - 1)
    half = z_step * cfg["window_factor"]
    targets = (list(cfg["metrics"].keys()) if cfg["refine_mode"] == "each"
               else [cfg["primary"]])

    positions = set()
    for m in targets:
        valid = [s for s in coarse if not np.isnan(s["scores"][m])]
        if not valid:
            continue
        peak = max(valid, key=lambda s: s["scores"][m])
        lo = max(cfg["z_min"], peak["z_mm"] - half)
        hi = min(cfg["z_max"], peak["z_mm"] + half)
        for z in np.linspace(lo, hi, cfg["n_refine"]):
            positions.add(round(float(z), 3))

    for z in sorted(positions):
        s = measure(z, "refine")
        samples.append(s)
        step += 1
        yield step, total_ub, s, samples


# ======================================================================
# 7) Helpers de UI
# ======================================================================

def _normalize(ys: List[float]) -> List[float]:
    lo, hi = min(ys), max(ys)
    if hi - lo < 1e-12:
        return [0.0] * len(ys)
    return [(y - lo) / (hi - lo) for y in ys]


def make_fig(samples: List[dict], metric_names: List[str],
             best: Optional[Dict[str, dict]] = None) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for m in metric_names:
        data = sorted([s for s in samples if not np.isnan(s["scores"][m])],
                      key=lambda s: s["z_mm"])
        if not data:
            continue
        zs = [s["z_mm"] for s in data]
        ys = _normalize([s["scores"][m] for s in data])
        ax.plot(zs, ys, "-o", markersize=3.5, label=DISPLAY[m])
        if best and m in best:
            ax.axvline(best[m]["z_mm"], linestyle=":",
                       color=ax.lines[-1].get_color(), alpha=0.5)
    ax.set_xlabel("Posição Z (mm)")
    ax.set_ylabel("Score normalizado [0–1]")
    ax.set_title("Curvas de foco — varredura grossa + refinamento")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    return fig


def make_fig_per_metric(samples: List[dict], metric_names: List[str],
                        best: Dict[str, dict]) -> plt.Figure:
    n = len(metric_names)
    nrows = (n + 1) // 2
    fig, axes = plt.subplots(nrows, 2, figsize=(11, 3.6 * nrows), squeeze=False)
    for i, m in enumerate(metric_names):
        ax = axes[i // 2][i % 2]
        for phase, style in [("coarse", "o-"), ("refine", "s--")]:
            data = sorted([s for s in samples
                           if s["phase"] == phase
                           and not np.isnan(s["scores"][m])],
                          key=lambda s: s["z_mm"])
            if not data:
                continue
            ax.plot([s["z_mm"] for s in data],
                    [s["scores"][m] for s in data],
                    style, markersize=4, label=phase)
        if m in best:
            ax.axvline(best[m]["z_mm"], color="red", linestyle=":",
                       alpha=0.7, label=f"ótimo z={best[m]['z_mm']:.2f}")
        ax.set_title(DISPLAY[m])
        ax.set_xlabel("Z (mm)")
        ax.set_ylabel("score")
        ax.legend(fontsize=7)
        ax.grid(alpha=0.3)
    for j in range(n, nrows * 2):
        axes[j // 2][j % 2].axis("off")
    fig.tight_layout()
    return fig


def make_accuracy_fig(best: Dict[str, dict], metric_names: List[str],
                      samples: List[dict],
                      true_focus: Optional[float] = None) -> plt.Figure:
    """1×2 subplots: acurácia (esquerda) + tempo de cálculo (direita)."""
    fig, (ax_acc, ax_time) = plt.subplots(1, 2, figsize=(14, 5))

    valid = [(m, best[m]) for m in metric_names
             if m in best and best[m].get("z_mm") is not None]

    if not valid:
        for ax in (ax_acc, ax_time):
            ax.text(0.5, 0.5, "Sem dados válidos",
                    ha="center", va="center",
                    transform=ax.transAxes, fontsize=12)
            ax.axis("off")
        fig.tight_layout()
        return fig

    names = [DISPLAY[m] for m, _ in valid]

    if true_focus is not None:
        errors = [abs(b["z_mm"] - true_focus) for _, b in valid]
        best_idx = int(np.argmin(errors))
        colors = ["#e74c3c" if i == best_idx else "#95a5a6"
                  for i in range(len(errors))]
        bars = ax_acc.bar(names, errors, color=colors,
                          edgecolor="black", linewidth=0.6)
        for bar, (_, b), err in zip(bars, valid, errors):
            ax_acc.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height(),
                        f"{err * 1000:.1f} µm\n(z={b['z_mm']:.3f})",
                        ha="center", va="bottom", fontsize=9)
        ax_acc.set_ylabel("Erro |z_ótimo − z_verdadeiro|  (mm)")
        ax_acc.set_title(f"Acurácia — z_verdadeiro = {true_focus:.2f} mm")
        ax_acc.axhline(y=errors[best_idx], color="#e74c3c",
                       linestyle=":", alpha=0.6)
        ax_acc.text(0.98, 0.98,
                    f"🏆 Melhor: {names[best_idx]}\n"
                    f"Erro: {errors[best_idx] * 1000:.1f} µm",
                    transform=ax_acc.transAxes, ha="right", va="top",
                    fontsize=10,
                    bbox=dict(boxstyle="round,pad=0.5",
                              facecolor="#fef9e7", edgecolor="#f39c12"))
    else:
        zs = [b["z_mm"] for _, b in valid]
        median = float(np.median(zs))
        best_idx = int(np.argmin([abs(z - median) for z in zs]))
        colors = ["#e67e22" if i == best_idx else "#3498db"
                  for i in range(len(zs))]
        bars = ax_acc.bar(names, zs, color=colors,
                          edgecolor="black", linewidth=0.6)
        for bar, (_, b) in zip(bars, valid):
            ax_acc.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height(), f"{b['z_mm']:.3f}",
                        ha="center", va="bottom", fontsize=9)
        ax_acc.axhline(y=median, color="#e67e22",
                       linestyle="--", alpha=0.8,
                       label=f"Mediana: {median:.3f} mm")
        spread = max(zs) - min(zs)
        ax_acc.set_ylabel("Posição Z ótima (mm)")
        ax_acc.set_title(f"Concordância — spread = {spread:.3f} mm "
                         f"({spread * 1000:.1f} µm)")
        ax_acc.legend(loc="upper right", fontsize=9)

    ax_acc.grid(axis="y", alpha=0.3)

    time_data = []
    for m in metric_names:
        valid_t = [s["times"][m] for s in samples
                   if "times" in s and m in s["times"]
                   and not np.isnan(s["times"][m])]
        if valid_t:
            time_data.append((m, float(np.mean(valid_t) * 1000)))

    if time_data:
        names_t = [DISPLAY[m] for m, _ in time_data]
        times_t = [t for _, t in time_data]
        best_t_idx = int(np.argmin(times_t))
        colors_t = ["#27ae60" if i == best_t_idx else "#95a5a6"
                    for i in range(len(times_t))]
        bars_t = ax_time.bar(names_t, times_t, color=colors_t,
                             edgecolor="black", linewidth=0.6)
        for bar, t in zip(bars_t, times_t):
            ax_time.text(bar.get_x() + bar.get_width() / 2,
                         bar.get_height(), f"{t:.2f}",
                         ha="center", va="bottom", fontsize=9)
        ax_time.set_ylabel("Tempo médio de cálculo por imagem (ms)")
        ax_time.set_title("Custo computacional (menor = melhor)")
        ax_time.grid(axis="y", alpha=0.3)
        ax_time.text(0.98, 0.98,
                     f"⚡ Mais rápida: {names_t[best_t_idx]}\n"
                     f"{times_t[best_t_idx]:.2f} ms",
                     transform=ax_time.transAxes, ha="right", va="top",
                     fontsize=10,
                     bbox=dict(boxstyle="round,pad=0.5",
                               facecolor="#e8f8f5", edgecolor="#27ae60"))

    fig.tight_layout()
    return fig


# -------------------- NOVAS FUNÇÕES: HISTOGRAMAS --------------------

def _load_img_for_hist(path: Optional[str]) -> Optional[np.ndarray]:
    """Carrega imagem do disco e devolve em grayscale. None se indisponível."""
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    img = cv2.imread(str(p), cv2.IMREAD_UNCHANGED)
    if img is None:
        return None
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


def make_histogram_fig(samples: List[dict], metric_names: List[str],
                       best: Dict[str, dict],
                       use_color: bool = False) -> plt.Figure:
    """2×2 grid: histograma da imagem no z_ótimo de cada métrica."""
    n = len(metric_names)
    nrows = (n + 1) // 2
    fig, axes = plt.subplots(nrows, 2, figsize=(13, 4.2 * nrows),
                             squeeze=False)

    for i, m in enumerate(metric_names):
        ax = axes[i // 2][i % 2]
        if m not in best:
            ax.axis("off")
            continue

        sample = best[m]
        path = sample.get("img_path")
        img_gray = _load_img_for_hist(path)

        if img_gray is None:
            ax.text(0.5, 0.5,
                    "Imagem não disponível\n(use 'Salvar imagens')",
                    ha="center", va="center",
                    transform=ax.transAxes, fontsize=11)
            ax.set_title(f"{DISPLAY[m]} — z={sample['z_mm']:.3f} mm")
            ax.axis("off")
            continue

        # Se quiser RGB, carrega colorida
        if use_color and path and Path(path).exists():
            img_color = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if img_color is not None:
                for c, color, label in zip(range(3),
                                           ("#3498db", "#27ae60", "#e74c3c"),
                                           ("Azul (B)", "Verde (G)", "Vermelho (R)")):
                    ax.hist(img_color[:, :, c].ravel(), bins=64,
                            color=color, alpha=0.45, label=label,
                            density=True)
                ax.legend(fontsize=7, loc="upper right")
        else:
            ax.hist(img_gray.ravel(), bins=64, color="steelblue",
                    alpha=0.8, density=True)
            ax.axvline(float(img_gray.mean()), color="#e74c3c",
                       linestyle="--", linewidth=1.5,
                       label=f"média = {img_gray.mean():.1f}")
            ax.axvline(float(np.median(img_gray)), color="#27ae60",
                       linestyle=":", linewidth=1.5,
                       label=f"mediana = {np.median(img_gray):.1f}")
            ax.legend(fontsize=7, loc="upper right")

        ax.set_title(f"{DISPLAY[m]} — z={sample['z_mm']:.3f} mm "
                     f"(score={sample['scores'][m]:.3e})",
                     fontsize=10)
        ax.set_xlabel("Intensidade (0–255)")
        ax.set_ylabel("Densidade")
        ax.grid(alpha=0.3)

    for j in range(n, nrows * 2):
        axes[j // 2][j % 2].axis("off")

    fig.suptitle("Histogramas das imagens no pico de cada métrica",
                 fontsize=12, y=1.02)
    fig.tight_layout()
    return fig


def make_histogram_comparison_fig(samples: List[dict],
                                  primary_metric: str) -> Optional[plt.Figure]:
    """Compara histogramas em z_min, z_ótimo e z_max.

    Ilustra por que histogramas globais NÃO discriminam foco:
    as curvas são quase idênticas enquanto a métrica varia drasticamente.
    """
    if not samples:
        return None

    # Seleciona amostras de interesse
    sorted_s = sorted(samples, key=lambda s: s["z_mm"])
    zmin_s = sorted_s[0]
    zmax_s = sorted_s[-1]
    peak_s = max(
        (s for s in samples if not np.isnan(s["scores"].get(primary_metric, np.nan))),
        key=lambda s: s["scores"][primary_metric],
        default=None,
    )

    if peak_s is None:
        return None

    # Deduplica por z (se o pico coincidir com z_min ou z_max)
    targets: List[Tuple[str, dict, str]] = []
    seen_z = set()
    for label, s, color in [
        ("Desfocado (z_min)", zmin_s, "#95a5a6"),
        (f"Pico ({DISPLAY[primary_metric]})", peak_s, "#e74c3c"),
        ("Desfocado (z_max)", zmax_s, "#3498db"),
    ]:
        z_key = round(s["z_mm"], 3)
        if z_key in seen_z:
            continue
        seen_z.add(z_key)
        targets.append((label, s, color))

    fig, (ax_hist, ax_info) = plt.subplots(1, 2, figsize=(14, 5),
                                            gridspec_kw={"width_ratios": [2, 1]})

    # --- Histogramas sobrepostos (densidade normalizada) ---
    n_plots = 0
    for label, s, color in targets:
        img_gray = _load_img_for_hist(s.get("img_path"))
        if img_gray is None:
            continue
        ax_hist.hist(img_gray.ravel(), bins=64, color=color, alpha=0.45,
                     label=f"{label}  z={s['z_mm']:.2f} mm",
                     density=True, edgecolor=color, linewidth=0.5)
        ax_hist.axvline(float(img_gray.mean()), color=color,
                        linestyle="--", alpha=0.8, linewidth=1.2)
        n_plots += 1

    if n_plots == 0:
        ax_hist.text(0.5, 0.5, "Imagens não disponíveis",
                     ha="center", va="center", transform=ax_hist.transAxes)
        ax_hist.axis("off")
    else:
        ax_hist.set_xlabel("Intensidade (0–255)")
        ax_hist.set_ylabel("Densidade")
        ax_hist.set_title(
            "Histogramas globais em 3 posições Z — quase idênticos",
            fontsize=11)
        ax_hist.legend(fontsize=9, loc="upper right")
        ax_hist.grid(alpha=0.3)

    # --- Painel de informação ---
    ax_info.axis("off")
    lines = [f"Métrica primária: {DISPLAY[primary_metric]}\n"]
    for label, s, _ in targets:
        v = s["scores"].get(primary_metric, np.nan)
        img_gray = _load_img_for_hist(s.get("img_path"))
        if img_gray is not None:
            mu = float(img_gray.mean())
            sd = float(img_gray.std())
            lines.append(
                f"{label}\n"
                f"  z     = {s['z_mm']:.3f} mm\n"
                f"  μ     = {mu:.1f}\n"
                f"  σ     = {sd:.1f}\n"
                f"  score = {v:.3e}\n"
            )
        else:
            lines.append(f"{label}\n  z = {s['z_mm']:.3f} mm\n"
                         f"  score = {v:.3e}\n  (imagem indisponível)\n")

    lines.append(
        "─────────────────────────\n"
        "Se μ e σ são quase iguais\n"
        "nas 3 posições, mas o score\n"
        "varia drasticamente:\n"
        "→ histograma GLOBAL não\n"
        "  discrimina foco.\n"
        "→ é preciso métrica ESPACIAL\n"
        "  (gradiente, Laplaciano, FFT)."
    )
    ax_info.text(0.0, 1.0, "\n".join(lines),
                 va="top", ha="left", fontsize=9, family="monospace",
                 bbox=dict(boxstyle="round,pad=0.6",
                           facecolor="#f8f9fa", edgecolor="#7f8c8d"))

    fig.tight_layout()
    return fig


def make_histogram_gallery_fig(samples: List[dict],
                               primary_metric: str) -> Optional[plt.Figure]:
    """Grade 1×3 com imagens em z_min, pico e z_max + histograma abaixo."""
    if not samples:
        return None

    sorted_s = sorted(samples, key=lambda s: s["z_mm"])
    zmin_s = sorted_s[0]
    zmax_s = sorted_s[-1]
    peak_s = max(
        (s for s in samples
         if not np.isnan(s["scores"].get(primary_metric, np.nan))),
        key=lambda s: s["scores"][primary_metric],
        default=None,
    )
    if peak_s is None:
        return None

    targets: List[Tuple[str, dict, str]] = [
        ("z_min (desfocado)", zmin_s, "#95a5a6"),
        (f"z_ótimo ({DISPLAY[primary_metric]})", peak_s, "#e74c3c"),
        ("z_max (desfocado)", zmax_s, "#3498db"),
    ]

    fig, axes = plt.subplots(2, len(targets),
                              figsize=(5 * len(targets), 7),
                              gridspec_kw={"height_ratios": [2, 1]})
    if len(targets) == 1:
        axes = axes.reshape(2, 1)

    for col, (label, s, color) in enumerate(targets):
        ax_img = axes[0, col]
        ax_hist = axes[1, col]

        img_gray = _load_img_for_hist(s.get("img_path"))
        if img_gray is None:
            ax_img.text(0.5, 0.5, "Imagem indisponível",
                        ha="center", va="center",
                        transform=ax_img.transAxes)
            ax_img.axis("off")
            ax_hist.axis("off")
            continue

        ax_img.imshow(img_gray, cmap="gray", vmin=0, vmax=255)
        ax_img.set_title(
            f"{label}\nz = {s['z_mm']:.3f} mm  ·  "
            f"score = {s['scores'].get(primary_metric, np.nan):.3e}",
            fontsize=10)
        ax_img.axis("off")

        ax_hist.hist(img_gray.ravel(), bins=64, color=color,
                     alpha=0.8, density=True)
        ax_hist.axvline(float(img_gray.mean()), color="black",
                        linestyle="--", linewidth=1.2,
                        label=f"μ = {img_gray.mean():.1f}")
        ax_hist.set_xlabel("Intensidade")
        ax_hist.set_ylabel("Densidade")
        ax_hist.set_xlim(0, 255)
        ax_hist.legend(fontsize=8, loc="upper right")
        ax_hist.grid(alpha=0.3)

    fig.suptitle("Comparação visual + histograma (3 posições Z)",
                 fontsize=12, y=1.01)
    fig.tight_layout()
    return fig


# -------------------- /NOVAS FUNÇÕES --------------------


def make_table(samples: List[dict], metric_names: List[str]) -> pd.DataFrame:
    """DataFrame numérico (usado para exportação CSV)."""
    rows = []
    for s in samples:
        row = {"Fase": s["phase"], "z (mm)": s["z_mm"]}
        for m in metric_names:
            row[DISPLAY[m]] = s["scores"][m]
        rows.append(row)
    return pd.DataFrame(rows)


# ======================================================================
# 8) App principal
# ======================================================================

def main() -> None:
    st.set_page_config(page_title="Autofoco Z — Scanner histológico",
                       page_icon="🔬", layout="wide")
    st.title("🔬 Autofoco do eixo Z — Scanner histológico")
    st.caption("4 métricas: Laplaciano · Tenengrad · Brenner · FFT — "
               "hardware ESP8266 + Nema17 + DRV8825")

    for k, v in [("samples", []), ("best", {}),
                 ("elapsed", None), ("run_metrics", []),
                 ("spm_read", None), ("true_focus_used", None)]:
        if k not in st.session_state:
            st.session_state[k] = v

    # ---------------- SIDEBAR ----------------
    with st.sidebar:
        st.header("Hardware")
        hw_mode = st.radio(
            "Modo",
            ["Mock (demo)", "ESP8266 — Serial USB", "ESP8266 — WiFi (HTTP)"],
        )

        roi = None
        use_roi = False

        if hw_mode == "Mock (demo)":
            true_focus = st.number_input("Foco verdadeiro simulado (mm)",
                                         0.0, 40.0, 22.0, 0.5)
            size_str = st.selectbox("Resolução simulada",
                                    ["512x640", "768x1024"], index=0)
            h_sim, w_sim = [int(x) for x in size_str.split("x")]

        elif hw_mode == "ESP8266 — Serial USB":
            if not HAS_PYSERIAL:
                st.error("`pyserial` não instalado. Rode: `pip install pyserial`")
            with st.expander("Eixo Z — ESP Serial", expanded=True):
                port = st.text_input("Porta serial", "COM5",
                                     help="Windows: COM4/COM5. "
                                          "Linux: /dev/ttyUSB0.")
                baud = st.number_input("Baudrate", 9600, 250000, 115200, 9600)

            with st.expander("⚙️ Calibração `$102` (steps/mm Z)",
                             expanded=False):
                _render_calibration_panel(mode="serial", port=port, baud=baud)

            with st.expander("Câmera (OpenCV)", expanded=True):
                cam_index = st.number_input("Índice da câmera", 0, 10, 0)
                cam_w = st.number_input("Largura", 320, 4096, 1280, 64)
                cam_h = st.number_input("Altura", 240, 4096, 1024, 64)
            with st.expander("ROI (opcional)", expanded=False):
                use_roi = st.checkbox("Recortar região", False)
                if use_roi:
                    y0 = st.number_input("y0", 0, int(cam_h), 0)
                    y1 = st.number_input("y1", 0, int(cam_h), int(cam_h))
                    x0 = st.number_input("x0", 0, int(cam_w), 0)
                    x1 = st.number_input("x1", 0, int(cam_w), int(cam_w))
                    roi = (y0, y1, x0, x1)

        else:
            if not HAS_REQUESTS:
                st.error("`requests` não instalado. Rode: `pip install requests`")
            with st.expander("Eixo Z — ESP WiFi (HTTP)", expanded=True):
                host = st.text_input("IP do ESP8266", "192.168.1.42",
                                     help="Mostrado no Monitor Serial.")

            with st.expander("⚙️ Calibração `$102` (steps/mm Z)",
                             expanded=False):
                _render_calibration_panel(mode="wifi", host=host)

            with st.expander("Câmera (OpenCV)", expanded=True):
                cam_index = st.number_input("Índice da câmera", 0, 10, 0)
                cam_w = st.number_input("Largura", 320, 4096, 1280, 64)
                cam_h = st.number_input("Altura", 240, 4096, 1024, 64)
            with st.expander("ROI (opcional)", expanded=False):
                use_roi = st.checkbox("Recortar região", False)
                if use_roi:
                    y0 = st.number_input("y0", 0, int(cam_h), 0)
                    y1 = st.number_input("y1", 0, int(cam_h), int(cam_h))
                    x0 = st.number_input("x0", 0, int(cam_w), 0)
                    x1 = st.number_input("x1", 0, int(cam_w), int(cam_w))
                    roi = (y0, y1, x0, x1)

        st.header("Varredura")
        z_min = st.number_input("Z mínimo (mm)", 0.0, 200.0, 0.0, 0.5)
        z_max = st.number_input("Z máximo (mm)", 0.0, 200.0, 40.0, 0.5)
        n_coarse = st.slider("Pontos na varredura grossa", 5, 60, 25)
        settle_s = st.number_input("Pausa após mover (s)", 0.0, 5.0, 0.2, 0.05)

        st.header("Refinamento")
        n_refine = st.slider("Pontos por métrica", 3, 25, 11)
        window_factor = st.slider("Janela (× passo grosso)", 0.5, 5.0, 2.0, 0.25)
        refine_choice = st.radio("Refinar em torno de",
                                 ["Cada métrica", "Apenas a primária"], index=0)

        st.header("Métricas")
        metric_names = st.multiselect(
            "Selecionadas", list(METRICS.keys()),
            default=list(METRICS.keys()),
            format_func=lambda k: DISPLAY[k],
        )
        primary = st.selectbox(
            "Primária (posição final)", metric_names or ["tenengrad"],
            format_func=lambda k: DISPLAY.get(k, k),
        )

        st.header("Saída")
        save_images = st.checkbox(
            "Salvar imagens permanentemente", True,
            help="Se desmarcado, imagens vão para diretório temporário. "
                 "A aba Histogramas requer imagens em disco."
        )
        save_dir_str = st.text_input("Diretório", "autofocus_images",
                                     disabled=not save_images)

        st.divider()
        run_btn = st.button("▶️ Iniciar varredura", type="primary",
                            use_container_width=True,
                            disabled=not metric_names)
        if st.button("🧹 Limpar resultados", use_container_width=True):
            for k in ("samples", "best", "elapsed", "run_metrics",
                      "true_focus_used"):
                st.session_state[k] = (
                    [] if k in ("samples", "run_metrics")
                    else ({} if k == "best" else None)
                )
            st.rerun()

    # ---------------- mensagens de modo ----------------
    if hw_mode == "Mock (demo)":
        st.info(f"**Modo demo.** Foco verdadeiro simulado em "
                f"**z = {true_focus:.1f} mm**.")
    elif hw_mode == "ESP8266 — Serial USB":
        st.warning("**Modo ESP Serial.** Calibre `$102` antes do primeiro "
                   "teste. Depois clique em *Testar conexão*.")
    else:
        st.warning("**Modo ESP WiFi.** Calibre `$102` antes do primeiro "
                   "teste. Depois clique em *Testar conexão*.")

    # ---- Testar câmera e ESP separadamente ----
    if hw_mode != "Mock (demo)":
        if st.button("🔌 Testar conexão (câmera + ESP)"):
            cam_ok = False
            cam = None
            try:
                cam = OpenCVCamera(int(cam_index), int(cam_w), int(cam_h))
                img = cam.capture()
                st.success(f"✅ Câmera OK — frame {img.shape}")
                st.image(cv2.cvtColor(img, cv2.COLOR_BGR2RGB),
                         caption="Preview", width=420)
                cam_ok = True
            except Exception as e:
                st.error(f"❌ Câmera: {e}")
                st.caption("Feche Câmera do Windows, Teams, Zoom, OBS. "
                           "Tente outro índice (0, 1, 2...).")
            finally:
                if cam is not None:
                    try:
                        cam.close()
                    except Exception:
                        pass

            esp_ok = False
            z_t = None
            try:
                if hw_mode == "ESP8266 — Serial USB":
                    z_t = ESP8266SerialZAxis(port, int(baud))
                else:
                    z_t = ESP8266WiFiZAxis(host, timeout_s=10.0)
                spm = z_t.read_z_steps_per_mm()
                st.success(f"✅ ESP OK — `$102 = {spm}`")
                esp_ok = True
            except Exception as e:
                st.error(f"❌ ESP: {e}")
            finally:
                if z_t is not None:
                    try:
                        z_t.close()
                    except Exception:
                        pass

            if cam_ok and esp_ok:
                st.info("🎉 Hardware completo OK. Pode iniciar a varredura.")

    # ---------------- execução ----------------
    if run_btn and metric_names:
        try:
            if hw_mode == "Mock (demo)":
                zaxis = MockZAxis()
                camera = MockCamera(zaxis, true_focus_mm=true_focus,
                                    size=(h_sim, w_sim))
            elif hw_mode == "ESP8266 — Serial USB":
                zaxis = ESP8266SerialZAxis(port, int(baud))
                camera = OpenCVCamera(int(cam_index), int(cam_w), int(cam_h))
            else:
                zaxis = ESP8266WiFiZAxis(host, timeout_s=60.0)
                camera = OpenCVCamera(int(cam_index), int(cam_w), int(cam_h))
        except Exception as e:
            st.error(f"Não foi possível iniciar hardware: {e}")
            st.stop()

        st.session_state["true_focus_used"] = (
            true_focus if hw_mode == "Mock (demo)" else None
        )

        if save_images:
            save_dir = Path(save_dir_str)
            save_dir.mkdir(parents=True, exist_ok=True)
        else:
            save_dir = Path(tempfile.mkdtemp(prefix="autofocus_"))

        cfg = {
            "z_min": z_min, "z_max": z_max, "n_coarse": n_coarse,
            "n_refine": n_refine, "window_factor": window_factor,
            "refine_mode": "each" if refine_choice == "Cada métrica" else "primary",
            "metrics": {k: METRICS[k] for k in metric_names},
            "primary": primary,
            "settle_s": settle_s, "roi": roi, "save_dir": save_dir,
        }

        st.session_state.samples = []
        st.session_state.best = {}
        st.session_state.elapsed = None
        st.session_state.run_metrics = metric_names

        progress = st.progress(0.0, text="Iniciando…")
        status = st.empty()
        chart_ph = st.empty()
        img_ph = st.empty()
        table_ph = st.empty()

        collected: List[dict] = []
        t0 = time.time()
        try:
            for step, total, sample, all_samples in run_sweep(zaxis, camera, cfg):
                collected = all_samples
                progress.progress(min(step / total, 0.99),
                                  text=f"[{sample['phase']}] {step}/{total}  "
                                       f"z={sample['z_mm']:.2f} mm")
                scores_txt = " · ".join(
                    f"**{DISPLAY[k]}**={v:.3g}"
                    for k, v in sample["scores"].items()
                )
                status.markdown(f"`z = {sample['z_mm']:.3f} mm` — {scores_txt}")
                if sample["img_path"] and Path(sample["img_path"]).exists():
                    img_ph.image(sample["img_path"], width=360,
                                 caption=f"{sample['phase']} @ "
                                         f"z={sample['z_mm']:.2f} mm")
                if step % 3 == 0 or step == total:
                    fig = make_fig(collected, metric_names)
                    chart_ph.pyplot(fig)
                    plt.close(fig)
                if step % 5 == 0 or step == total:
                    table_ph.dataframe(make_table(collected, metric_names),
                                       use_container_width=True, height=230)
        finally:
            try:
                zaxis.close()
            except Exception:
                pass
            try:
                camera.close()
            except Exception:
                pass

        elapsed = time.time() - t0
        progress.progress(1.0, text=f"✅ Concluído em {elapsed:.1f} s")

        status.success(f"✅ {len(collected)} medidas em {elapsed:.1f} s")
        chart_ph.empty()
        img_ph.empty()
        table_ph.empty()

        best: Dict[str, dict] = {}
        for m in metric_names:
            valid = [s for s in collected if not np.isnan(s["scores"][m])]
            if valid:
                best[m] = max(valid, key=lambda s: s["scores"][m])

        st.session_state.samples = collected
        st.session_state.best = best
        st.session_state.elapsed = elapsed

        if hw_mode != "Mock (demo)" and primary in best:
            try:
                if hw_mode == "ESP8266 — Serial USB":
                    z_final = ESP8266SerialZAxis(port, int(baud))
                else:
                    z_final = ESP8266WiFiZAxis(host, timeout_s=10.0)
                z_final.move_to_mm(best[primary]["z_mm"])
                z_final.wait_until_idle()
                z_final.close()
                st.success(f"Eixo Z posicionado em "
                           f"**{best[primary]['z_mm']:.3f} mm** "
                           f"({DISPLAY[primary]})")
            except Exception as e:
                st.warning(f"Não reposicionei o Z: {e}")

    # ---------------- resultados ----------------
    if st.session_state.samples:
        st.divider()
        st.subheader("📊 Resultados")
        samples = st.session_state.samples
        best = st.session_state.best
        metric_names = st.session_state.run_metrics or list(METRICS.keys())

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Medidas", len(samples))
        if st.session_state.elapsed is not None:
            c2.metric("Tempo total", f"{st.session_state.elapsed:.1f} s")
        if primary in best:
            c3.metric(f"Ótimo — {DISPLAY[primary]}",
                      f"{best[primary]['z_mm']:.2f} mm")
        if len(best) > 1:
            zs_opt = [b["z_mm"] for b in best.values()]
            c4.metric("Spread entre métricas",
                      f"{(max(zs_opt) - min(zs_opt)):.2f} mm")

        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
            ["Curvas sobrepostas", "Painéis por métrica",
             "🎯 Acurácia + Tempo", "📊 Histogramas",
             "Tabela", "Melhores imagens"])

        # ---------- TAB 1 ----------
        with tab1:
            fig = make_fig(samples, metric_names, best=best)
            st.pyplot(fig); plt.close(fig)

        # ---------- TAB 2 ----------
        with tab2:
            fig = make_fig_per_metric(samples, metric_names, best)
            st.pyplot(fig); plt.close(fig)

        # ---------- TAB 3: Acurácia + Tempo ----------
        with tab3:
            true_focus_used = st.session_state.get("true_focus_used")

            if true_focus_used is not None:
                st.markdown(
                    f"**Acurácia + tempo** — erro absoluto entre o pico "
                    f"de cada métrica e o foco verdadeiro simulado "
                    f"(**z = {true_focus_used:.2f} mm**), junto com o "
                    f"tempo médio de cálculo por imagem."
                )
                st.info(
                    "ℹ️ **Modo mock:** as 4 métricas convergem para o "
                    "mesmo z porque o simulador aplica um desfoque "
                    "Gaussiano simétrico. Em imagens reais de H&E, com "
                    "ruído, texturas e aberrações ópticas distintas, as "
                    "métricas divergem. Aqui, o **diferenciador prático "
                    "é o custo computacional**."
                )
            else:
                st.markdown(
                    "**Sem ground truth** — posição Z ótima de cada métrica "
                    "(mediana = proxy de consenso) + tempo médio de cálculo."
                )

            fig_acc = make_accuracy_fig(best, metric_names, samples,
                                        true_focus=true_focus_used)
            st.pyplot(fig_acc); plt.close(fig_acc)

            st.markdown("**Detalhamento**")
            rows = []
            for m in metric_names:
                if m not in best:
                    continue
                b = best[m]
                valid_times = [s["times"][m] for s in samples
                               if "times" in s and m in s["times"]
                               and not np.isnan(s["times"][m])]
                mean_ms = (float(np.mean(valid_times) * 1000)
                           if valid_times else None)
                total_ms = (float(np.sum(valid_times) * 1000)
                            if valid_times else None)

                row = {
                    "Métrica": DISPLAY[m],
                    "z_ótimo (mm)": b["z_mm"],
                    "Tempo médio (ms)": mean_ms,
                    "Tempo total (ms)": total_ms,
                }
                if true_focus_used is not None:
                    row["Erro (µm)"] = (
                        abs(b["z_mm"] - true_focus_used) * 1000)
                rows.append(row)

            df_acc = pd.DataFrame(rows)
            if true_focus_used is not None and "Erro (µm)" in df_acc.columns:
                df_acc = df_acc.sort_values("Erro (µm)").reset_index(drop=True)
            else:
                df_acc = df_acc.sort_values(
                    "Tempo médio (ms)").reset_index(drop=True)
            df_acc.index = df_acc.index + 1
            df_acc.index.name = "Rank"

            df_disp = df_acc.copy()
            df_disp["z_ótimo (mm)"] = df_disp["z_ótimo (mm)"].map(
                lambda x: f"{x:.3f}")
            df_disp["Tempo médio (ms)"] = df_disp["Tempo médio (ms)"].map(
                lambda x: "—" if pd.isna(x) else f"{x:.2f}")
            df_disp["Tempo total (ms)"] = df_disp["Tempo total (ms)"].map(
                lambda x: "—" if pd.isna(x) else f"{x:.1f}")
            if "Erro (µm)" in df_disp.columns:
                df_disp["Erro (µm)"] = df_disp["Erro (µm)"].map(
                    lambda x: f"{x:.1f}")

            st.dataframe(df_disp, use_container_width=True)

            st.download_button(
                "⬇️ Baixar CSV de acurácia + tempo",
                data=df_acc.to_csv().encode("utf-8"),
                file_name="accuracy_comparison.csv",
                mime="text/csv",
            )

        # ---------- TAB 4: 📊 Histogramas ----------
        with tab4:
            st.markdown(
                "Histogramas das imagens capturadas em diferentes posições "
                "do eixo Z. As duas análises abaixo respondem a perguntas "
                "distintas: **(1)** como as imagens no pico de cada métrica "
                "se comparam; **(2)** por que histogramas globais **não** "
                "são bons indicadores de foco."
            )

            # --- Seletor de modo ---
            modo_hist = st.radio(
                "Visualização:",
                ["Histograma no pico de cada métrica",
                 "Comparação: foco vs. desfoque (métrica primária)",
                 "Galeria visual + histograma (3 posições)"],
                horizontal=True,
                key="hist_mode",
            )

            st.divider()

            # ---------- Seção 1: histogramas por métrica ----------
            if modo_hist == "Histograma no pico de cada métrica":
                st.subheader("Histogramas no pico de cada métrica")

                use_color = st.checkbox(
                    "Mostrar canais RGB (requer imagem colorida)",
                    False,
                    help="Se a imagem for em cinza (mock), ignora esta opção."
                )

                # Verifica se há pelo menos uma imagem disponível
                disponiveis = sum(
                    1 for m in metric_names
                    if m in best
                    and _load_img_for_hist(best[m].get("img_path")) is not None
                )
                if disponiveis == 0:
                    st.warning(
                        "⚠️ Nenhuma imagem disponível em disco. Verifique se "
                        "**'Salvar imagens permanentemente'** está marcado "
                        "no sidebar. Imagens em diretório temporário podem "
                        "expirar durante a sessão."
                    )
                else:
                    fig_h = make_histogram_fig(samples, metric_names, best,
                                                use_color=use_color)
                    st.pyplot(fig_h)
                    plt.close(fig_h)
                    st.caption(
                        f"**{disponiveis}/{len(metric_names)}** imagens "
                        f"disponíveis. Eixo X = intensidade (0–255); "
                        f"Eixo Y = densidade. As linhas verticais indicam "
                        f"média (vermelho) e mediana (verde)."
                    )

            # ---------- Seção 2: comparação foco vs desfoque ----------
            elif modo_hist == "Comparação: foco vs. desfoque (métrica primária)":
                st.subheader("Por que histogramas globais não discriminam foco")
                st.markdown(
                    "Os **três histogramas abaixo** correspondem à mesma "
                    "cena nas posições **z_min** (desfocado), "
                    f"**z_ótimo** (pico da métrica *{DISPLAY[primary]}*) e "
                    "**z_max** (desfocado). Se as três distribuições forem "
                    "quase idênticas, isso confirma que o **histograma "
                    "global não é um bom indicador de foco** — e que é "
                    "necessário usar uma **métrica espacial** (gradiente, "
                    "Laplaciano, FFT)."
                )

                fig_cmp = make_histogram_comparison_fig(samples, primary)
                if fig_cmp is None:
                    st.warning(
                        "⚠️ Não foi possível gerar a comparação. "
                        "Verifique se as imagens estão em disco."
                    )
                else:
                    st.pyplot(fig_cmp)
                    plt.close(fig_cmp)

            # ---------- Seção 3: galeria visual ----------
            else:
                st.subheader("Galeria visual + histograma")
                st.markdown(
                    f"Miniaturas das imagens em **z_min**, **pico "
                    f"({DISPLAY[primary]})** e **z_max**, cada uma com "
                    f"seu histograma abaixo. Útil para inspeção visual "
                    f"do efeito do desfoque no conteúdo, contrastando "
                    f"com a quase-invariância dos histogramas."
                )

                fig_gal = make_histogram_gallery_fig(samples, primary)
                if fig_gal is None:
                    st.warning(
                        "⚠️ Não foi possível carregar as imagens. "
                        "Verifique se estão em disco."
                    )
                else:
                    st.pyplot(fig_gal)
                    plt.close(fig_gal)

        # ---------- TAB 5: Tabela ----------
        with tab5:
            st.caption(
                "**Fase** — `coarse` = varredura grossa inicial "
                "(grade uniforme entre Z mínimo e máximo). "
                "`refine` = refinamento ao redor do pico de cada métrica. "
                "Scores em notação científica (mesma formatação em todas "
                "as linhas); `z` em milímetros com 3 casas decimais."
            )
            df = make_table(samples, metric_names)

            df_disp = df.copy()
            df_disp["z (mm)"] = df_disp["z (mm)"].map(lambda x: f"{x:.3f}")
            for m in metric_names:
                col = DISPLAY[m]
                df_disp[col] = df_disp[col].map(
                    lambda x: "—" if pd.isna(x) else f"{x:.3e}")

            st.dataframe(df_disp, use_container_width=True, height=420)

            st.download_button(
                "⬇️ Baixar CSV (valores numéricos)",
                data=df.to_csv(index=False).encode("utf-8"),
                file_name="sweep_results.csv", mime="text/csv")

        # ---------- TAB 6: Melhores imagens (2×2) ----------
        with tab6:
            imgs = list(best.items())
            if not imgs:
                st.info("Sem imagens para exibir.")
            else:
                for row_start in range(0, len(imgs), 2):
                    cols = st.columns(2)
                    for i, (m, s) in enumerate(imgs[row_start:row_start + 2]):
                        with cols[i]:
                            st.markdown(f"### {DISPLAY[m]}")
                            st.caption(
                                f"z = **{s['z_mm']:.3f} mm** · "
                                f"score = {s['scores'][m]:.3e}"
                            )
                            if (s.get("img_path")
                                    and Path(s["img_path"]).exists()):
                                st.image(s["img_path"],
                                         use_column_width=True)


# ======================================================================
# 9) Painel de calibração $102
# ======================================================================

def _render_calibration_panel(mode: str, **kwargs) -> None:
    st.caption(
        "**`$102`** é o número de passos por milímetro do eixo Z. "
        "Valor errado = posições em mm erradas."
    )

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("📊 Ler `$102`", use_container_width=True):
            try:
                if mode == "serial":
                    z = ESP8266SerialZAxis(kwargs["port"], int(kwargs["baud"]))
                else:
                    z = ESP8266WiFiZAxis(kwargs["host"], timeout_s=10.0)
                v = z.read_z_steps_per_mm()
                z.close()
                if v is not None:
                    st.session_state["spm_read"] = v
                    st.success(f"`$102 = {v}`")
                else:
                    st.warning("`$102` não respondeu.")
            except Exception as e:
                st.error(f"Falha: {e}")
    with col_b:
        if "spm_read" in st.session_state and st.session_state["spm_read"]:
            st.metric("Lido do firmware",
                      f"{st.session_state['spm_read']:g}")

    st.markdown("**Calibrar**")
    default_spm = float(st.session_state.get("spm_read") or DEFAULT_SPM)
    new_102 = st.number_input("Novo valor (steps/mm Z)",
                              1.0, 10000.0, default_spm, 1.0,
                              key="new_102_input")
    if st.button("💾 Aplicar `$102`", use_container_width=True):
        try:
            if mode == "serial":
                z = ESP8266SerialZAxis(kwargs["port"], int(kwargs["baud"]))
            else:
                z = ESP8266WiFiZAxis(kwargs["host"], timeout_s=10.0)
            z.send_setting("$102", new_102)
            z.close()
            st.success(f"`$102 = {new_102:g}` gravado.")
        except Exception as e:
            st.error(f"Falha: {e}")

    st.caption(
        "**Procedimento:** `$0` → `Z10` → mede D com paquímetro → "
        "`$102_novo = $102_atual × 10 / D` → aplicar → repetir."
    )


if __name__ == "__main__":
    main()
