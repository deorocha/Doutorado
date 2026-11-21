"""Varredura grossa + refinamento, com medição de tempo por métrica.

Dois modos de busca:
  - run_sweep         : varredura uniforme (N_coarse) + refinamento por métrica
  - run_sweep_brent   : seed de 3 pontos + Brent parabólico + refinamento
                        (cai automaticamente para uniforme se a curva for
                         não-unimodal)

Dispatcher: run_sweep_dispatch escolhe com base em cfg["search_mode"].
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np

from .metrics import _to_gray


# ======================================================================
# Helpers compartilhados
# ======================================================================

def _make_measure_fn(zaxis, camera, cfg: dict):
    """Cria a closure `measure(z, phase)` — usada pelos dois sweeps.

    Aplica o patch `needs_color`: métricas com `fn.needs_color = True`
    (ex.: MSCG) recebem a imagem BGR; as demais recebem grayscale.
    """
    roi = cfg.get("roi")
    settle_s = float(cfg.get("settle_s", 0.0))
    save_dir = cfg.get("save_dir")

    def measure(z: float, phase: str) -> dict:
        zaxis.move_to_mm(z)
        zaxis.wait_until_idle()
        if settle_s > 0:
            time.sleep(settle_s)

        img = camera.capture()
        if roi is not None:
            y0, y1, x0, x1 = roi
            img = img[y0:y1, x0:x1]

        gray = _to_gray(img)

        scores: Dict[str, float] = {}
        times: Dict[str, float] = {}
        for name, fn in cfg["metrics"].items():
            try:
                needs_color = getattr(fn, "needs_color", False)
                input_img = img if needs_color else gray
                t0 = time.perf_counter()
                scores[name] = float(fn(input_img))
                times[name] = time.perf_counter() - t0
            except Exception:
                scores[name] = float("nan")
                times[name] = float("nan")

        path = None
        if save_dir is not None:
            path = str(Path(save_dir) / f"{phase}_z{z:09.3f}.png")
            cv2.imwrite(path, img)

        return {"z_mm": float(z), "scores": scores, "times": times,
                "phase": phase, "img_path": path}

    return measure


def _refine_by_metric(samples: List[dict], measure, cfg: dict,
                      total_ub: int):
    """Refinamento uniforme ao redor do pico de cada métrica.

    Gerador: yields (step, total_ub, sample, samples).
    Deduplica posições já medidas (tolerância 0.01 mm).
    """
    z_step_ref = (cfg["z_max"] - cfg["z_min"]) / max(1, cfg.get("n_coarse", 25) - 1)
    half = z_step_ref * cfg["window_factor"]
    targets = (list(cfg["metrics"].keys()) if cfg["refine_mode"] == "each"
               else [cfg["primary"]])

    positions = set()
    for m in targets:
        valid = [s for s in samples if not np.isnan(s["scores"][m])]
        if not valid:
            continue
        peak = max(valid, key=lambda s: s["scores"][m])
        lo = max(cfg["z_min"], peak["z_mm"] - half)
        hi = min(cfg["z_max"], peak["z_mm"] + half)
        for z in np.linspace(lo, hi, cfg["n_refine"]):
            positions.add(round(float(z), 3))

    for z in sorted(positions):
        if any(abs(s["z_mm"] - z) < 0.01 for s in samples):
            continue
        s = measure(z, "refine")
        samples.append(s)
        yield len(samples), total_ub, s, samples


# ======================================================================
# Sweep uniforme (original)
# ======================================================================

def run_sweep(zaxis, camera, cfg: dict):
    """Varredura uniforme (N_coarse) + refinamento por métrica.

    Interface: gerador que yields (step, total_ub, sample, samples).
    """
    samples: List[dict] = []
    measure = _make_measure_fn(zaxis, camera, cfg)

    n_targets = len(cfg["metrics"]) if cfg["refine_mode"] == "each" else 1
    total_ub = int(cfg["n_coarse"]) + int(cfg["n_refine"]) * n_targets

    for z in np.linspace(cfg["z_min"], cfg["z_max"], int(cfg["n_coarse"])):
        s = measure(float(z), "coarse")
        samples.append(s)
        yield len(samples), total_ub, s, samples

    yield from _refine_by_metric(samples, measure, cfg, total_ub)


# ======================================================================
# Brent — busca parabólica adaptativa
# ======================================================================

def _parabolic_vertex(x1: float, x2: float, x3: float,
                      f1: float, f2: float, f3: float) -> Optional[float]:
    """Vértice da parábola por (x1,f1),(x2,f2),(x3,f3). Requer x1<x2<x3.

    Funciona tanto para máximo quanto para mínimo. Retorna None se os
    pontos forem colineares (den ≈ 0).
    """
    num = (x2 - x1) ** 2 * (f2 - f3) - (x2 - x3) ** 2 * (f2 - f1)
    den = (x2 - x1) * (f2 - f3) - (x2 - x3) * (f2 - f1)
    if abs(den) < 1e-12:
        return None
    return x2 - 0.5 * num / den


def _uniform_fallback(samples: List[dict], measure, cfg: dict,
                      total_ub: int):
    """Fallback: varredura uniforme + refinamento (usado se curva for
    não-unimodal). Gerador.
    """
    n_coarse = int(cfg.get("n_coarse", 25))
    for z in np.linspace(cfg["z_min"], cfg["z_max"], n_coarse):
        if any(abs(s["z_mm"] - float(z)) < 0.01 for s in samples):
            continue
        s = measure(float(z), "coarse")
        samples.append(s)
        yield len(samples), total_ub, s, samples

    yield from _refine_by_metric(samples, measure, cfg, total_ub)


def run_sweep_brent(zaxis, camera, cfg: dict):
    """Busca parabólica iterativa (Brent simplificado) com safeguard.

    Fases:
      1. Seed: 3 pontos (z_min, mid, z_max). Detecta unimodalidade.
      2. Brent: 4–6 iterações parabólicas até |Δz| < search_tol_mm.
         Safeguard: se o vértice cair fora do bracket ou muito longe,
         usa o mid do maior lado (garante convergência).
      3. Refinamento uniforme por métrica (idêntico ao run_sweep).

    Campos adicionais em cfg (opcionais):
      - search_tol_mm   (float, default 0.2): critério de parada.
      - search_max_iter (int,   default 8): máximo de iterações Brent.
      - n_coarse        (int,   default 25): usado no fallback uniforme.

    Se a curva for não-unimodal (pico não interior), cai em
    _uniform_fallback — comportamento equivalente ao run_sweep.
    """
    samples: List[dict] = []
    measure = _make_measure_fn(zaxis, camera, cfg)

    metric = cfg["primary"]
    tol_mm = float(cfg.get("search_tol_mm", 0.2))
    max_iter = int(cfg.get("search_max_iter", 8))
    n_targets = len(cfg["metrics"]) if cfg["refine_mode"] == "each" else 1
    total_ub = 3 + max_iter + int(cfg["n_refine"]) * n_targets

    # ---------- Fase 1: seed ----------
    z_a, z_b = float(cfg["z_min"]), float(cfg["z_max"])
    z_mid = 0.5 * (z_a + z_b)

    s_a = measure(z_a, "seed")
    samples.append(s_a)
    yield len(samples), total_ub, s_a, samples

    s_mid = measure(z_mid, "seed")
    samples.append(s_mid)
    yield len(samples), total_ub, s_mid, samples

    s_b = measure(z_b, "seed")
    samples.append(s_b)
    yield len(samples), total_ub, s_b, samples

    f_a = s_a["scores"][metric]
    f_mid = s_mid["scores"][metric]
    f_b = s_b["scores"][metric]

    # ---------- Fase 2a: fallback (curva não-unimodal) ----------
    peak_in_interior = (f_mid > f_a) and (f_mid > f_b)
    if not peak_in_interior or np.isnan(f_mid):
        yield from _uniform_fallback(samples, measure, cfg, total_ub)
        return

    # ---------- Fase 2b: Brent parabólico ----------
    trio: List[tuple] = [(z_a, f_a), (z_mid, f_mid), (z_b, f_b)]

    for _ in range(max_iter):
        trio_sorted = sorted(trio, key=lambda p: p[0])
        x1, f1 = trio_sorted[0]
        x2, f2 = trio_sorted[1]
        x3, f3 = trio_sorted[2]
        span = x3 - x1
        if span < tol_mm:
            break

        v = _parabolic_vertex(x1, x2, x3, f1, f2, f3)

        # Safeguard: vértice inválido → mid do maior lado
        if v is None or v <= x1 or v >= x3 or abs(v - x2) > 0.9 * span:
            if (x2 - x1) > (x3 - x2):
                v = 0.5 * (x1 + x2)
            else:
                v = 0.5 * (x2 + x3)

        # Convergência
        if abs(v - x2) < tol_mm:
            break

        # Evita remedir posição já visitada (ruído numérico)
        if any(abs(v - s["z_mm"]) < 1e-3 for s in samples):
            break

        s_new = measure(float(v), "refine")
        samples.append(s_new)
        yield len(samples), total_ub, s_new, samples

        # Atualiza trio com os 3 melhores
        trio.append((float(v), s_new["scores"][metric]))
        trio.sort(key=lambda p: p[1], reverse=True)
        trio = trio[:3]

    # ---------- Fase 3: refinamento uniforme por métrica ----------
    yield from _refine_by_metric(samples, measure, cfg, total_ub)


# ======================================================================
# Dispatcher
# ======================================================================

def run_sweep_dispatch(zaxis, camera, cfg: dict):
    """Escolhe o sweep por cfg['search_mode'] ('uniform' | 'brent').

    Uniforme é o padrão — use brent apenas quando a curva puder ser
    assumida unimodal (caso típico em lâminas histológicas com uma
    única camada de tecido).
    """
    if cfg.get("search_mode") == "brent":
        yield from run_sweep_brent(zaxis, camera, cfg)
    else:
        yield from run_sweep(zaxis, camera, cfg)
