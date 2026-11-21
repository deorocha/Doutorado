"""Métricas de foco — funções puras, sem dependência de Streamlit."""
from __future__ import annotations

from typing import Dict, Optional, Tuple

import cv2
import numpy as np


# ======================================================================
# Caches — evitam recomputar Hamming e máscara a cada frame
# ======================================================================

_HAMMING_CACHE: Dict[Tuple[int, int], np.ndarray] = {}
_MASK_CACHE: Dict[Tuple[int, int, float], np.ndarray] = {}

# LUT para OD = -log10(v/255 + eps). 256 entradas, computadas 1 vez.
_LOG_LUT = (-np.log10(np.arange(256, dtype=np.float64) / 255.0 + 1e-6)
            ).astype(np.float32)


# ======================================================================
# Helpers
# ======================================================================

def _to_gray(img: np.ndarray) -> np.ndarray:
    if img.ndim == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


# ======================================================================
# 1) Variância do Laplaciano
# ======================================================================

def metric_laplacian(img: np.ndarray) -> float:
    return float(cv2.Laplacian(_to_gray(img), cv2.CV_64F).var())


# ======================================================================
# 2) Tenengrad
# ======================================================================

def metric_tenengrad(img: np.ndarray) -> float:
    g = _to_gray(img).astype(np.float64)
    gx = cv2.Sobel(g, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(g, cv2.CV_64F, 0, 1, ksize=3)
    return float((gx * gx + gy * gy).mean())


# ======================================================================
# 3) Brenner
# ======================================================================

def metric_brenner(img: np.ndarray, k: int = 2) -> float:
    g = _to_gray(img).astype(np.float64)
    dx = g[:, k:] - g[:, :-k]
    dy = g[k:, :] - g[:-k, :]
    return float((dx * dx).mean() + (dy * dy).mean())


# ======================================================================
# 4) Energia de alta frequência via FFT
# ======================================================================

def _hamming_2d(shape: Tuple[int, int]) -> np.ndarray:
    if shape not in _HAMMING_CACHE:
        h, w = shape
        wy = np.hamming(h)[:, None]
        wx = np.hamming(w)[None, :]
        _HAMMING_CACHE[shape] = (wy * wx).astype(np.float64)
    return _HAMMING_CACHE[shape]


def _fft_mask(shape: Tuple[int, int], radius_frac: float) -> np.ndarray:
    key = (shape[0], shape[1], radius_frac)
    if key not in _MASK_CACHE:
        h, w = shape
        cy, cx = h // 2, w // 2
        Y, X = np.ogrid[:h, :w]
        r = int(min(h, w) * radius_frac)
        _MASK_CACHE[key] = (Y - cy) ** 2 + (X - cx) ** 2 > r * r
    return _MASK_CACHE[key]


def metric_fft_hf(img: np.ndarray, radius_frac: float = 1 / 8) -> float:
    g = _to_gray(img)
    if g.dtype != np.float64:
        g = g.astype(np.float64)
    g = g * _hamming_2d(g.shape)
    M = np.abs(np.fft.fftshift(np.fft.fft2(g)))
    return float(M[_fft_mask(M.shape, radius_frac)].mean())


# ======================================================================
# 5) MSCG v3 — duas escalas, saturação fixa (mantida para A/B)
# ======================================================================

def metric_mscg_v3(img: np.ndarray,
                   channel: str = "green",
                   w_fine: float = 0.7,
                   w_coarse: float = 0.3,
                   sat_low: float = 0.05,
                   sat_high: float = 0.35,
                   max_side: Optional[int] = None,
                   eps: float = 1e-6) -> float:
    """MSCG v3 — duas escalas, saturação fixa, sem normalização local."""
    if img is None:
        return 0.0

    if max_side is not None:
        h, w = img.shape[:2]
        if max(h, w) > max_side:
            scale = max_side / max(h, w)
            img = cv2.resize(img, None, fx=scale, fy=scale,
                             interpolation=cv2.INTER_AREA)

    if img.ndim == 2:
        gray = img
        weight: Optional[np.ndarray] = None
    else:
        gray = np.ascontiguousarray(img[:, :, 1])
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        sat = hsv[:, :, 1].astype(np.float32) * (1.0 / 255.0)
        span = max(sat_high - sat_low, 1e-6)
        weight = np.clip((sat - sat_low) / span, 0.0, 1.0)
        if float(weight.sum()) < 1.0:
            return 0.0

    if channel == "green":
        od = _LOG_LUT[gray]
    elif channel == "all":
        if img.ndim == 2:
            od = _LOG_LUT[gray]
        else:
            b = np.ascontiguousarray(img[:, :, 0])
            r = np.ascontiguousarray(img[:, :, 2])
            od = _LOG_LUT[b] + _LOG_LUT[gray] + _LOG_LUT[r]
    else:
        raise ValueError(f"channel inválido: {channel!r} "
                         f"(use 'green'|'all')")

    gx = cv2.Sobel(od, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(od, cv2.CV_32F, 0, 1, ksize=3)
    e = gx * gx + gy * gy

    if weight is not None:
        mean_fine = float((e * weight).sum()) / float(weight.sum())
    else:
        mean_fine = float(e.mean())

    od_c = cv2.resize(od, None, fx=0.5, fy=0.5,
                      interpolation=cv2.INTER_AREA)
    gx_c = cv2.Sobel(od_c, cv2.CV_32F, 1, 0, ksize=3)
    gy_c = cv2.Sobel(od_c, cv2.CV_32F, 0, 1, ksize=3)
    e_c = gx_c * gx_c + gy_c * gy_c

    if weight is not None:
        w_c = cv2.resize(weight, (od_c.shape[1], od_c.shape[0]),
                         interpolation=cv2.INTER_AREA)
        ws_c = float(w_c.sum())
        if ws_c < 0.25:
            return float(w_fine * mean_fine)
        mean_coarse = float((e_c * w_c).sum()) / ws_c
    else:
        mean_coarse = float(e_c.mean())

    return float(w_fine * mean_fine + w_coarse * mean_coarse)


metric_mscg_v3.needs_color = True


# ======================================================================
# 6) MSCG v4 — três escalas + normalização por variância local
#                + saturação adaptativa por percentis
# ======================================================================

def metric_mscg(img: np.ndarray,
                channel: str = "green",
                w_fine: float = 0.5,
                w_medium: float = 0.35,
                w_coarse: float = 0.15,
                sat_low_pct: float = 20.0,
                sat_high_pct: float = 80.0,
                norm_window: int = 15,
                eps_floor_frac: float = 0.05,
                max_side: Optional[int] = None,
                eps: float = 1e-6) -> float:
    """MSCG v4 — três escalas, normalização local, saturação adaptativa.

    Args:
        channel: "green" (OD do canal G) ou "all" (soma dos 3 ODs).
        w_fine/w_medium/w_coarse: pesos das escalas (somam ~1).
        sat_low_pct/sat_high_pct: percentis para rampa de saturação.
        norm_window: janela (px) para std local. 15 é adequado para
                     512×640 e 1280×1024.
        eps_floor_frac: piso da normalização (fração do std global).
        max_side: downscale máximo. None = sem downscale (preserva
                  discriminação; use 1536 só se a imagem for >4 MP).

    Retorna:
        Escalar ≥ 0 (maior = mais nítido).
    """
    if img is None:
        return 0.0

    # ---- 0. Downscale opcional ----
    if max_side is not None:
        h, w = img.shape[:2]
        if max(h, w) > max_side:
            scale = max_side / max(h, w)
            img = cv2.resize(img, None, fx=scale, fy=scale,
                             interpolation=cv2.INTER_AREA)

    # ---- 1. Canal + peso por saturação (adaptativa) ----
    if img.ndim == 2:
        gray = img
        weight: Optional[np.ndarray] = None
    else:
        gray = np.ascontiguousarray(img[:, :, 1])
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        sat = hsv[:, :, 1].astype(np.float32) * (1.0 / 255.0)
        sat_lo = float(np.percentile(sat, sat_low_pct))
        sat_hi = float(np.percentile(sat, sat_high_pct))
        span = max(sat_hi - sat_lo, 1e-6)
        weight = np.clip((sat - sat_lo) / span, 0.0, 1.0)
        if float(weight.sum()) < 1.0:
            return 0.0

    # ---- 2. Optical density (LUT) ----
    if channel == "green":
        od = _LOG_LUT[gray]
    elif channel == "all":
        if img.ndim == 2:
            od = _LOG_LUT[gray]
        else:
            b = np.ascontiguousarray(img[:, :, 0])
            r = np.ascontiguousarray(img[:, :, 2])
            od = _LOG_LUT[b] + _LOG_LUT[gray] + _LOG_LUT[r]
    else:
        raise ValueError(f"channel inválido: {channel!r} "
                         f"(use 'green'|'all')")

    # ---- 3. Energia por escala com normalização local ----
    def _scale_energy(od_s: np.ndarray,
                      weight_s: Optional[np.ndarray]) -> Optional[float]:
        gx = cv2.Sobel(od_s, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(od_s, cv2.CV_32F, 0, 1, ksize=3)
        e = gx * gx + gy * gy

        k = norm_window
        mu = cv2.boxFilter(od_s, -1, (k, k))
        mu2 = cv2.boxFilter(od_s * od_s, -1, (k, k))
        std_local = np.sqrt(np.maximum(mu2 - mu * mu, 0.0))

        global_std = float(np.std(od_s))
        floor = max(eps_floor_frac * global_std, eps)
        e_norm = e / (std_local + floor)

        if weight_s is not None:
            w_sum = float(weight_s.sum())
            if w_sum < 1.0:
                return None
            return float((e_norm * weight_s).sum()) / w_sum
        return float(e_norm.mean())

    # ---- 4. Escala fine (full res) ----
    e_fine = _scale_energy(od, weight)
    if e_fine is None:
        return 0.0

    # ---- 5. Escala medium (0.5×) ----
    od_m = cv2.resize(od, None, fx=0.5, fy=0.5,
                      interpolation=cv2.INTER_AREA)
    w_m = (cv2.resize(weight, (od_m.shape[1], od_m.shape[0]),
                      interpolation=cv2.INTER_AREA)
           if weight is not None else None)
    e_med = _scale_energy(od_m, w_m)
    if e_med is None:
        return float(e_fine)

    # ---- 6. Escala coarse (0.25×) ----
    od_c = cv2.resize(od, None, fx=0.25, fy=0.25,
                      interpolation=cv2.INTER_AREA)
    w_c = (cv2.resize(weight, (od_c.shape[1], od_c.shape[0]),
                      interpolation=cv2.INTER_AREA)
           if weight is not None else None)
    e_crs = _scale_energy(od_c, w_c)
    if e_crs is None:
        return float((w_fine * e_fine + w_medium * e_med)
                     / max(w_fine + w_medium, eps))

    # ---- 7. Combinação ponderada ----
    return float(w_fine * e_fine + w_medium * e_med + w_coarse * e_crs)

def metric_mscg_v4a(img: np.ndarray,
                    channel: str = "green",
                    w_fine: float = 0.6,
                    w_medium: float = 0.3,
                    w_coarse: float = 0.1,
                    sat_low: float = 0.05,
                    sat_high: float = 0.35,
                    max_side: Optional[int] = None,
                    eps: float = 1e-6) -> float:
    """MSCG v4a — só adiciona escala média (0.5×) à v3.

    Mantém: saturação fixa, sem normalização local, sem escala coarse.
    Isola o efeito de adicionar uma escala intermediária.
    """
    if img is None:
        return 0.0

    if max_side is not None:
        h, w = img.shape[:2]
        if max(h, w) > max_side:
            scale = max_side / max(h, w)
            img = cv2.resize(img, None, fx=scale, fy=scale,
                             interpolation=cv2.INTER_AREA)

    if img.ndim == 2:
        gray = img
        weight: Optional[np.ndarray] = None
    else:
        gray = np.ascontiguousarray(img[:, :, 1])
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        sat = hsv[:, :, 1].astype(np.float32) * (1.0 / 255.0)
        span = max(sat_high - sat_low, 1e-6)
        weight = np.clip((sat - sat_low) / span, 0.0, 1.0)
        if float(weight.sum()) < 1.0:
            return 0.0

    if channel == "green":
        od = _LOG_LUT[gray]
    elif channel == "all":
        if img.ndim == 2:
            od = _LOG_LUT[gray]
        else:
            b = np.ascontiguousarray(img[:, :, 0])
            r = np.ascontiguousarray(img[:, :, 2])
            od = _LOG_LUT[b] + _LOG_LUT[gray] + _LOG_LUT[r]
    else:
        raise ValueError(f"channel inválido: {channel!r}")

    def _energy(od_s: np.ndarray, w_s: Optional[np.ndarray]) -> float:
        gx = cv2.Sobel(od_s, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(od_s, cv2.CV_32F, 0, 1, ksize=3)
        e = gx * gx + gy * gy
        if w_s is not None:
            ws = float(w_s.sum())
            return float((e * w_s).sum()) / ws if ws > 1.0 else 0.0
        return float(e.mean())

    e_fine = _energy(od, weight)
    if weight is not None:
        ws = float(weight.sum())

    # Escala média (0.5×)
    od_m = cv2.resize(od, None, fx=0.5, fy=0.5,
                      interpolation=cv2.INTER_AREA)
    w_m = (cv2.resize(weight, (od_m.shape[1], od_m.shape[0]),
                      interpolation=cv2.INTER_AREA)
           if weight is not None else None)
    e_med = _energy(od_m, w_m)

    return float(w_fine * e_fine + w_medium * e_med)


def metric_hybrid(img, alpha=0.5):
    # Normaliza cada métrica pelo pico histórico (fixado empiricamente)
    mscg = metric_mscg_v3(img)
    lap = metric_laplacian(img)
    # Normalização: dividir pelo valor típico em foco
    return alpha * (mscg / 1.99) + (1 - alpha) * (lap / 801.9)

metric_mscg_v4a.needs_color = True

metric_mscg.needs_color = True


# ======================================================================
# Registro global
# ======================================================================

METRICS = {
    "laplacian": metric_laplacian,
    "tenengrad": metric_tenengrad,
    "brenner":   metric_brenner,
    "fft_hf":    metric_fft_hf,
    "mscg":      metric_mscg_v3,    # ← reverter para v3
}

DISPLAY = {
    "laplacian": "Var. Laplaciano",
    "tenengrad": "Tenengrad",
    "brenner":   "Brenner",
    "fft_hf":    "FFT (alta freq.)",
    "mscg":      "MSCG (proposto)",
}

# Sanidade: METRICS e DISPLAY devem ter exatamente as mesmas chaves.
assert set(METRICS.keys()) == set(DISPLAY.keys()), (
    f"Chaves divergentes entre METRICS e DISPLAY:\n"
    f"  Só em METRICS: {set(METRICS) - set(DISPLAY)}\n"
    f"  Só em DISPLAY: {set(DISPLAY) - set(METRICS)}"
)
