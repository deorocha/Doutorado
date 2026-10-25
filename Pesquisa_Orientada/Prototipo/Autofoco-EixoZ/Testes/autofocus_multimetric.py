"""
autofocus_multimetric.py

Varredura de autofoco com 4 métricas em paralelo:
  1. Variância do Laplaciano
  2. Tenengrad (energia do gradiente Sobel)
  3. Brenner
  4. Energia de alta frequência via FFT

Uso (mock):
    python autofocus_multimetric.py --mock
    python autofocus_multimetric.py --mock --no-show

# Com hardware real: implemente SerialZAxis/OpenCVCamera, comente o
# raise em main() e rode:
    python autofocus_multimetric.py --z-min 0 --z-max 40 --n-coarse 25

Saída em ./autofocus_out/:
    images/coarse_zXXXXXXXX.png      (todos os frames)
    images/refine_zXXXXXXXX.png
    sweep_results.csv
    focus_curves.png                 (4 curvas normalizadas sobrepostas)
    focus_curves_per_metric.png      (2x2 painéis individuais)
    summary.txt
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

# Backend headless: precisa vir ANTES de importar pyplot
import matplotlib
if "--no-show" in sys.argv:
    matplotlib.use("Agg")
import matplotlib.pyplot as plt


# ======================================================================
# 1) Métricas de foco  (top-level → picklable se migrar p/ ProcessPool)
# ======================================================================

def _to_gray(img: np.ndarray) -> np.ndarray:
    if img.ndim == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


def metric_laplacian(img: np.ndarray) -> float:
    """Variância do Laplaciano (passa-alta de 2ª ordem)."""
    g = _to_gray(img)
    return float(cv2.Laplacian(g, cv2.CV_64F).var())


def metric_tenengrad(img: np.ndarray) -> float:
    """Energia do gradiente Sobel (Tenengrad)."""
    g = _to_gray(img).astype(np.float64)
    gx = cv2.Sobel(g, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(g, cv2.CV_64F, 0, 1, ksize=3)
    return float((gx * gx + gy * gy).mean())


def metric_brenner(img: np.ndarray, k: int = 2) -> float:
    """Brenner (diferença k-vizinha ao quadrado, X+Y)."""
    g = _to_gray(img).astype(np.float64)
    dx = g[:, k:] - g[:, :-k]
    dy = g[k:, :] - g[:-k, :]
    return float((dx * dx).mean() + (dy * dy).mean())


def metric_fft_highfreq(img: np.ndarray, radius_frac: float = 1 / 8) -> float:
    """Energia média do espectro fora da região de baixas frequências."""
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
    "fft_hf":    metric_fft_highfreq,
}

DISPLAY = {
    "laplacian": "Var. Laplaciano",
    "tenengrad": "Tenengrad",
    "brenner":   "Brenner",
    "fft_hf":    "FFT (alta freq.)",
}

DEFAULT_WORKERS = max(1, min(len(METRICS), os.cpu_count() or 4))


# ======================================================================
# 2) Hardware — interfaces + exemplos (TODO para seu hardware real)
# ======================================================================

class ZAxis(ABC):
    @abstractmethod
    def move_to_mm(self, position_mm: float) -> None: ...
    @abstractmethod
    def wait_until_idle(self) -> None: ...
    @abstractmethod
    def get_position_mm(self) -> float: ...


class Camera(ABC):
    @abstractmethod
    def capture(self) -> np.ndarray: ...


# --- Exemplo: controlador via serial (GRBL / Marlin) -----------------
# Descomente e ajuste se for usar hardware real.
#
# class SerialZAxis(ZAxis):
#     def __init__(self, port="/dev/ttyUSB0", baud=115200, steps_per_mm=400):
#         import serial
#         self.ser = serial.Serial(port, baud, timeout=2)
#         self.steps_per_mm = steps_per_mm
#         self.pos_steps = 0
#         time.sleep(2)  # reset do Arduino
#     def move_to_mm(self, p):
#         self.pos_steps = int(round(p * self.steps_per_mm))
#         self.ser.write(f"G0 Z{self.pos_steps}\n".encode())
#     def wait_until_idle(self):
#         self.ser.write(b"G4 P0\n"); self.ser.write(b"M400\n")
#         while True:
#             line = self.ser.readline().decode(errors="ignore")
#             if line.strip() == "ok": break
#     def get_position_mm(self):
#         return self.pos_steps / self.steps_per_mm
#
# class OpenCVCamera(Camera):
#     def __init__(self, index=0, width=1280, height=1024):
#         self.cap = cv2.VideoCapture(index)
#         self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
#         self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
#         self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
#         self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
#     def capture(self):
#         ok, frame = self.cap.read()
#         if not ok: raise RuntimeError("Falha na captura")
#         return frame


# ======================================================================
# 3) Mock (só para validar a lógica antes de plugar o hardware)
# ======================================================================

class MockZAxis(ZAxis):
    def __init__(self, pos=0.0):
        self.pos = float(pos)
    def move_to_mm(self, p):
        self.pos = float(p)
    def wait_until_idle(self):
        pass
    def get_position_mm(self):
        return self.pos


class MockCamera(Camera):
    """Imagem sintética; foco real em `true_focus_mm`."""
    def __init__(self, zaxis: MockZAxis, true_focus_mm=22.0, size=(512, 640)):
        self.z = zaxis
        self.true_focus = true_focus_mm
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


# ======================================================================
# 4) Estrutura de amostra + classe principal
# ======================================================================

@dataclass
class Sample:
    z_mm: float
    scores: Dict[str, float]
    phase: str                     # "coarse" | "refine"
    img_path: Optional[str] = None


class MultiMetricAutofocus:
    def __init__(
        self,
        zaxis: ZAxis,
        camera: Camera,
        z_min_mm: float = 0.0,
        z_max_mm: float = 40.0,
        n_coarse: int = 25,
        settle_s: float = 0.2,
        roi: Optional[Tuple[int, int, int, int]] = None,   # (y0,y1,x0,x1)
        save_dir: Optional[Path] = None,
        metrics: Optional[Dict[str, callable]] = None,
        workers: int = DEFAULT_WORKERS,
        primary_metric: str = "tenengrad",
    ):
        self.zaxis = zaxis
        self.camera = camera
        self.z_min = float(z_min_mm)
        self.z_max = float(z_max_mm)
        self.n_coarse = int(n_coarse)
        self.settle_s = float(settle_s)
        self.roi = roi
        self.save_dir = Path(save_dir) if save_dir else None
        if self.save_dir:
            self.save_dir.mkdir(parents=True, exist_ok=True)
        self.metrics = dict(metrics) if metrics else dict(METRICS)
        if primary_metric not in self.metrics:
            raise ValueError(f"primary_metric '{primary_metric}' não está em metrics")
        self.primary = primary_metric
        self._pool = ThreadPoolExecutor(max_workers=workers)
        self.samples: List[Sample] = []

    # ---------------- medição de 1 ponto ----------------
    def _compute_metrics(self, gray: np.ndarray) -> Dict[str, float]:
        futures = {self._pool.submit(fn, gray): name
                   for name, fn in self.metrics.items()}
        out: Dict[str, float] = {}
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                out[name] = float(fut.result())
            except Exception as e:
                out[name] = float("nan")
                print(f"[warn] métrica '{name}' falhou: {e}")
        # preserva ordem de declaração
        return {name: out[name] for name in self.metrics}

    def _measure_at(self, z_mm: float, phase: str) -> Sample:
        self.zaxis.move_to_mm(z_mm)
        self.zaxis.wait_until_idle()
        if self.settle_s:
            time.sleep(self.settle_s)

        img = self.camera.capture()
        if self.roi is not None:
            y0, y1, x0, x1 = self.roi
            img = img[y0:y1, x0:x1]

        path = None
        if self.save_dir is not None:
            path = str(self.save_dir / f"{phase}_z{z_mm:09.3f}.png")
            cv2.imwrite(path, img)

        gray = _to_gray(img)
        scores = self._compute_metrics(gray)

        s = Sample(z_mm=float(z_mm), scores=scores, phase=phase, img_path=path)
        self.samples.append(s)

        line = f"[{phase:6s}] z={z_mm:7.3f} mm  " + "  ".join(
            f"{name}={v:.4g}" for name, v in scores.items()
        )
        print(line)
        return s

    # ---------------- fase 1: varredura grossa ----------------
    def coarse_sweep(self) -> None:
        zs = np.linspace(self.z_min, self.z_max, self.n_coarse)
        print(f"\n=== Varredura GROSSA: {self.n_coarse} pontos em "
              f"[{self.z_min:.2f}, {self.z_max:.2f}] mm ===")
        for z in zs:
            self._measure_at(float(z), "coarse")

    # ---------------- fase 2: refinamento ----------------
    def refine_sweep(
        self,
        n_refine: int = 11,
        window_factor: float = 2.0,
        mode: str = "each",          # "each" | "primary"
    ) -> None:
        coarse = [s for s in self.samples if s.phase == "coarse"]
        if not coarse:
            return
        if self.n_coarse < 2:
            raise ValueError("n_coarse deve ser >= 2 para refinar")

        z_step = (self.z_max - self.z_min) / (self.n_coarse - 1)
        half = z_step * window_factor

        targets = list(self.metrics.keys()) if mode == "each" else [self.primary]

        positions = set()
        for m in targets:
            peak = max(coarse, key=lambda s: s.scores[m])
            lo = max(self.z_min, peak.z_mm - half)
            hi = min(self.z_max, peak.z_mm + half)
            for z in np.linspace(lo, hi, n_refine):
                positions.add(round(float(z), 3))

        print(f"\n=== Refinamento (mode='{mode}'): "
              f"{len(positions)} posições novas ===")
        for z in sorted(positions):
            self._measure_at(z, "refine")

    # ---------------- melhor por métrica ----------------
    def best_per_metric(self) -> Dict[str, Sample]:
        if not self.samples:
            return {}
        return {m: max(self.samples, key=lambda s: s.scores[m])
                for m in self.metrics}

    # ---------------- orquestração ----------------
    def run(
        self,
        n_refine: int = 11,
        window_factor: float = 2.0,
        refine_mode: str = "each",
    ) -> Dict[str, Sample]:
        self.coarse_sweep()
        self.refine_sweep(n_refine, window_factor, refine_mode)

        best = self.best_per_metric()
        target = best[self.primary].z_mm
        self.zaxis.move_to_mm(target)
        self.zaxis.wait_until_idle()
        return best

    # ---------------- exportações ----------------
    def export_csv(self, path: Path) -> None:
        if not self.samples:
            return
        names = list(self.metrics.keys())
        path = Path(path)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["phase", "z_mm", *names, "img_path"])
            for s in self.samples:
                w.writerow(
                    [s.phase, f"{s.z_mm:.4f}",
                     *[f"{s.scores[m]:.6g}" for m in names],
                     s.img_path or ""]
                )

    def __del__(self):
        try:
            self._pool.shutdown(wait=False)
        except Exception:
            pass


# ======================================================================
# 5) Plotagem
# ======================================================================

def _normalize(arr: np.ndarray) -> np.ndarray:
    lo, hi = np.nanmin(arr), np.nanmax(arr)
    if not np.isfinite(lo) or not np.isfinite(hi) or hi - lo < 1e-12:
        return arr * 0.0
    return (arr - lo) / (hi - lo)


def plot_results(
    samples: List[Sample],
    best: Dict[str, Sample],
    metric_names: List[str],
    out_dir: Path,
    show: bool = True,
) -> None:
    out_dir = Path(out_dir)

    # ---- (a) curvas normalizadas sobrepostas ----
    fig1, ax = plt.subplots(figsize=(10, 5))
    for m in metric_names:
        data = sorted(samples, key=lambda s: s.z_mm)
        zs = np.array([s.z_mm for s in data])
        ys = np.array([s.scores[m] for s in data], dtype=float)
        if not np.isfinite(ys).any():
            continue
        ax.plot(zs, _normalize(ys), "-o", markersize=4, label=DISPLAY[m])
        bp = best[m]
        ax.axvline(bp.z_mm, color=ax.lines[-1].get_color(),
                   linestyle=":", alpha=0.5)
    ax.set_xlabel("Posição Z (mm)")
    ax.set_ylabel("Score normalizado [0–1]")
    ax.set_title("Curvas de foco — 4 métricas (grossa + refinamento)")
    ax.legend(loc="best", fontsize=9)
    ax.grid(True, alpha=0.3)
    fig1.tight_layout()
    fig1.savefig(out_dir / "focus_curves.png", dpi=150)
    if show:
        plt.show()
    else:
        plt.close(fig1)

    # ---- (b) 2x2 painéis individuais ----
    fig2, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True)
    for i, m in enumerate(metric_names):
        ax = axes[i // 2, i % 2]
        coarse = sorted([s for s in samples if s.phase == "coarse"],
                        key=lambda s: s.z_mm)
        refine = sorted([s for s in samples if s.phase == "refine"],
                        key=lambda s: s.z_mm)
        if coarse:
            ax.plot([s.z_mm for s in coarse],
                    [s.scores[m] for s in coarse],
                    "o-", color="C0", markersize=4, label="coarse")
        if refine:
            ax.plot([s.z_mm for s in refine],
                    [s.scores[m] for s in refine],
                    "s--", color="C1", markersize=5, label="refine")
        bp = best[m]
        ax.axvline(bp.z_mm, color="red", linestyle=":", alpha=0.7,
                   label=f"ótimo: z={bp.z_mm:.2f} mm")
        ax.set_title(DISPLAY[m])
        ax.set_ylabel("score")
        ax.legend(fontsize=8, loc="best")
        ax.grid(True, alpha=0.3)
    for ax in axes[-1]:
        ax.set_xlabel("Posição Z (mm)")
    fig2.tight_layout()
    fig2.savefig(out_dir / "focus_curves_per_metric.png", dpi=150)
    if show:
        plt.show()
    else:
        plt.close(fig2)


# ======================================================================
# 6) main
# ======================================================================

def _write_summary(path: Path, best: Dict[str, Sample],
                   elapsed_s: float, primary: str) -> None:
    lines = [f"Tempo total: {elapsed_s:.1f} s", "",
             "Melhor Z por métrica:",
             f"  {'métrica':<14s} {'z (mm)':>10s} {'score':>14s}"]
    for m, s in best.items():
        marker = "  <-- primária" if m == primary else ""
        lines.append(f"  {m:<14s} {s.z_mm:>10.3f} {s.scores[m]:>14.6g}{marker}")
    lines.append("")
    lines.append(f"Posição final aplicada: {best[primary].z_mm:.3f} mm "
                 f"(métrica primária '{primary}')")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Autofoco multi-métrica em paralelo."
    )
    ap.add_argument("--mock", action="store_true",
                    help="Usa hardware simulado (demo).")
    ap.add_argument("--z-min", type=float, default=0.0)
    ap.add_argument("--z-max", type=float, default=40.0)
    ap.add_argument("--n-coarse", type=int, default=25)
    ap.add_argument("--n-refine", type=int, default=11)
    ap.add_argument("--settle", type=float, default=0.2,
                    help="pausa após mover Z, em segundos")
    ap.add_argument("--roi", type=int, nargs=4, default=None,
                    metavar=("Y0", "Y1", "X0", "X1"),
                    help="ROI opcional (ignorar fundo branco)")
    ap.add_argument("--primary", default="tenengrad",
                    choices=list(METRICS.keys()),
                    help="métrica usada para a posição final")
    ap.add_argument("--refine-mode", default="each",
                    choices=("each", "primary"))
    ap.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    ap.add_argument("--out-dir", default="autofocus_out")
    ap.add_argument("--no-save-images", action="store_true",
                    help="não salva os frames em disco")
    ap.add_argument("--no-show", action="store_true",
                    help="não abre janelas matplotlib (headless)")
    args = ap.parse_args()

    if args.mock:
        zaxis = MockZAxis()
        camera = MockCamera(zaxis, true_focus_mm=22.0)
    else:
        # Substitua pelas suas classes reais:
        #   zaxis  = SerialZAxis("/dev/ttyUSB0", steps_per_mm=400)
        #   camera = OpenCVCamera(0, 1280, 1024)
        raise SystemExit(
            "Sem --mock: implemente suas classes ZAxis/Camera reais "
            "e edite a seção correspondente em main()."
        )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    save_dir = None if args.no_save_images else out_dir / "images"

    af = MultiMetricAutofocus(
        zaxis=zaxis,
        camera=camera,
        z_min_mm=args.z_min,
        z_max_mm=args.z_max,
        n_coarse=args.n_coarse,
        settle_s=args.settle,
        roi=tuple(args.roi) if args.roi else None,
        save_dir=save_dir,
        workers=args.workers,
        primary_metric=args.primary,
    )

    t0 = time.time()
    best = af.run(
        n_refine=args.n_refine,
        refine_mode=args.refine_mode,
    )
    elapsed = time.time() - t0

    print("\n=== Resumo ===")
    for m, s in best.items():
        tag = "  <-- primária" if m == args.primary else ""
        print(f"  {m:<12s}  z = {s.z_mm:7.3f} mm   "
              f"score = {s.scores[m]:.6g}{tag}")
    print(f"\nTempo total: {elapsed:.1f} s")
    print(f"Posição final: {best[args.primary].z_mm:.3f} mm "
          f"(métrica primária '{args.primary}')")

    af.export_csv(out_dir / "sweep_results.csv")
    _write_summary(out_dir / "summary.txt", best, elapsed, args.primary)
    plot_results(af.samples, best, list(METRICS.keys()),
                 out_dir, show=not args.no_show)

    print(f"\nArquivos salvos em: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
