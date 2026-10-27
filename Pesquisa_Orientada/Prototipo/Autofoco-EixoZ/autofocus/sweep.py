"""Varredura grossa + refinamento, com medição de tempo por métrica."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List

import cv2
import numpy as np

from .metrics import _to_gray


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
                t0 = time.perf_counter()
                scores[name] = float(fn(gray))
                times[name] = time.perf_counter() - t0
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

    step = 0
    for z in np.linspace(cfg["z_min"], cfg["z_max"], cfg["n_coarse"]):
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
