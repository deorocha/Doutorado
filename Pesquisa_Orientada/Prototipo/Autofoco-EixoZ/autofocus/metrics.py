"""Métricas de foco — funções puras, sem dependência de Streamlit."""
from __future__ import annotations

from typing import Dict, Tuple

import cv2
import numpy as np

# Cache por shape — evita recomputar hamming e máscara a cada frame.
_HAMMING_CACHE: Dict[Tuple[int, int], np.ndarray] = {}
_MASK_CACHE: Dict[Tuple[int, int, float], np.ndarray] = {}


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
