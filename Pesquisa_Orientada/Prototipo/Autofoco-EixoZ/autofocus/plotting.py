"""Figuras matplotlib — todas retornam Figure; chamador fecha com plt.close()."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .metrics import DISPLAY


# ---------------- helpers ----------------

def _normalize(ys: List[float]) -> List[float]:
    lo, hi = min(ys), max(ys)
    if hi - lo < 1e-12:
        return [0.0] * len(ys)
    return [(y - lo) / (hi - lo) for y in ys]


def _load_gray(path: Optional[str]) -> Optional[np.ndarray]:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    img = cv2.imread(str(p), cv2.IMREAD_UNCHANGED)
    if img is None:
        return None
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img


# ---------------- curvas de foco ----------------

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
            if data:
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


# ---------------- acurácia + tempo ----------------

def make_accuracy_fig(best: Dict[str, dict], metric_names: List[str],
                      samples: List[dict],
                      true_focus: Optional[float] = None) -> plt.Figure:
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
        spread = max(zs) - min(zs)
        ax_acc.axhline(y=median, color="#e67e22", linestyle="--",
                       alpha=0.8, label=f"Mediana: {median:.3f} mm")
        ax_acc.set_ylabel("Posição Z ótima (mm)")
        ax_acc.set_title(f"Concordância — spread = {spread:.3f} mm "
                         f"({spread * 1000:.1f} µm)")
        ax_acc.legend(loc="upper right", fontsize=9)

    ax_acc.grid(axis="y", alpha=0.3)

    time_data = []
    for m in metric_names:
        valid_t = [s["times"][m] for s in samples
                   if m in s.get("times", {})
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
        ax_time.set_ylabel("Tempo médio (ms)")
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


# ---------------- histogramas ----------------

def make_histogram_fig(samples: List[dict], metric_names: List[str],
                       best: Dict[str, dict],
                       use_color: bool = False) -> plt.Figure:
    n = len(metric_names)
    nrows = (n + 1) // 2
    fig, axes = plt.subplots(nrows, 2, figsize=(13, 4.2 * nrows),
                             squeeze=False)
    for i, m in enumerate(metric_names):
        ax = axes[i // 2][i % 2]
        if m not in best:
            ax.axis("off")
            continue
        s = best[m]
        path = s.get("img_path")
        gray = _load_gray(path)
        if gray is None:
            ax.text(0.5, 0.5, "Imagem não disponível\n(use 'Salvar imagens')",
                    ha="center", va="center",
                    transform=ax.transAxes, fontsize=11)
            ax.set_title(f"{DISPLAY[m]} — z={s['z_mm']:.3f} mm")
            ax.axis("off")
            continue

        if use_color and path:
            color = cv2.imread(path, cv2.IMREAD_COLOR)
            if color is not None:
                for c, col, label in zip(range(3),
                                         ("#3498db", "#27ae60", "#e74c3c"),
                                         ("Azul (B)", "Verde (G)", "Vermelho (R)")):
                    ax.hist(color[:, :, c].ravel(), bins=64, color=col,
                            alpha=0.45, label=label, density=True)
                ax.legend(fontsize=7, loc="upper right")
        else:
            ax.hist(gray.ravel(), bins=64, color="steelblue",
                    alpha=0.8, density=True)
            ax.axvline(float(gray.mean()), color="#e74c3c",
                       linestyle="--", linewidth=1.5,
                       label=f"média = {gray.mean():.1f}")
            ax.axvline(float(np.median(gray)), color="#27ae60",
                       linestyle=":", linewidth=1.5,
                       label=f"mediana = {np.median(gray):.1f}")
            ax.legend(fontsize=7, loc="upper right")

        ax.set_title(f"{DISPLAY[m]} — z={s['z_mm']:.3f} mm "
                     f"(score={s['scores'][m]:.3e})", fontsize=10)
        ax.set_xlabel("Intensidade (0–255)")
        ax.set_ylabel("Densidade")
        ax.grid(alpha=0.3)

    for j in range(n, nrows * 2):
        axes[j // 2][j % 2].axis("off")
    fig.suptitle("Histogramas das imagens no pico de cada métrica",
                 fontsize=12, y=1.02)
    fig.tight_layout()
    return fig


def _three_positions(samples: List[dict], primary: str
                     ) -> Optional[List[Tuple[str, dict, str]]]:
    """Retorna [(label, sample, color), ...] em z_min, pico, z_max."""
    if not samples:
        return None
    sorted_s = sorted(samples, key=lambda s: s["z_mm"])
    peak = max((s for s in samples
                if not np.isnan(s["scores"].get(primary, np.nan))),
               key=lambda s: s["scores"][primary], default=None)
    if peak is None:
        return None
    targets, seen = [], set()
    for label, s, color in [
        ("Desfocado (z_min)", sorted_s[0], "#95a5a6"),
        (f"Pico ({DISPLAY[primary]})", peak, "#e74c3c"),
        ("Desfocado (z_max)", sorted_s[-1], "#3498db"),
    ]:
        z_key = round(s["z_mm"], 3)
        if z_key in seen:
            continue
        seen.add(z_key)
        targets.append((label, s, color))
    return targets


def make_histogram_comparison_fig(samples: List[dict],
                                  primary_metric: str) -> Optional[plt.Figure]:
    targets = _three_positions(samples, primary_metric)
    if targets is None:
        return None

    fig, (ax_hist, ax_info) = plt.subplots(
        1, 2, figsize=(14, 5), gridspec_kw={"width_ratios": [2, 1]})

    n_plots = 0
    for label, s, color in targets:
        gray = _load_gray(s.get("img_path"))
        if gray is None:
            continue
        ax_hist.hist(gray.ravel(), bins=64, color=color, alpha=0.45,
                     label=f"{label}  z={s['z_mm']:.2f} mm",
                     density=True, edgecolor=color, linewidth=0.5)
        ax_hist.axvline(float(gray.mean()), color=color,
                        linestyle="--", alpha=0.8, linewidth=1.2)
        n_plots += 1

    if n_plots == 0:
        ax_hist.text(0.5, 0.5, "Imagens não disponíveis",
                     ha="center", va="center", transform=ax_hist.transAxes)
        ax_hist.axis("off")
    else:
        ax_hist.set_xlabel("Intensidade (0–255)")
        ax_hist.set_ylabel("Densidade")
        ax_hist.set_title("Histogramas globais em 3 posições Z — quase idênticos")
        ax_hist.legend(fontsize=9, loc="upper right")
        ax_hist.grid(alpha=0.3)

    ax_info.axis("off")
    lines = [f"Métrica primária: {DISPLAY[primary_metric]}\n"]
    for label, s, _ in targets:
        v = s["scores"].get(primary_metric, np.nan)
        gray = _load_gray(s.get("img_path"))
        if gray is not None:
            lines.append(
                f"{label}\n"
                f"  z     = {s['z_mm']:.3f} mm\n"
                f"  μ     = {gray.mean():.1f}\n"
                f"  σ     = {gray.std():.1f}\n"
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
        "→ é preciso métrica ESPACIAL."
    )
    ax_info.text(0.0, 1.0, "\n".join(lines),
                 va="top", ha="left", fontsize=9, family="monospace",
                 bbox=dict(boxstyle="round,pad=0.6",
                           facecolor="#f8f9fa", edgecolor="#7f8c8d"))
    fig.tight_layout()
    return fig


def make_histogram_gallery_fig(samples: List[dict],
                               primary_metric: str) -> Optional[plt.Figure]:
    targets = _three_positions(samples, primary_metric)
    if targets is None:
        return None

    fig, axes = plt.subplots(2, len(targets),
                             figsize=(5 * len(targets), 7),
                             gridspec_kw={"height_ratios": [2, 1]})
    if len(targets) == 1:
        axes = axes.reshape(2, 1)

    for col, (label, s, color) in enumerate(targets):
        ax_img, ax_hist = axes[0, col], axes[1, col]
        gray = _load_gray(s.get("img_path"))
        if gray is None:
            ax_img.text(0.5, 0.5, "Imagem indisponível",
                        ha="center", va="center",
                        transform=ax_img.transAxes)
            ax_img.axis("off")
            ax_hist.axis("off")
            continue
        ax_img.imshow(gray, cmap="gray", vmin=0, vmax=255)
        ax_img.set_title(
            f"{label}\nz = {s['z_mm']:.3f} mm  ·  "
            f"score = {s['scores'].get(primary_metric, np.nan):.3e}",
            fontsize=10)
        ax_img.axis("off")

        ax_hist.hist(gray.ravel(), bins=64, color=color,
                     alpha=0.8, density=True)
        ax_hist.axvline(float(gray.mean()), color="black",
                        linestyle="--", linewidth=1.2,
                        label=f"μ = {gray.mean():.1f}")
        ax_hist.set_xlabel("Intensidade")
        ax_hist.set_ylabel("Densidade")
        ax_hist.set_xlim(0, 255)
        ax_hist.legend(fontsize=8, loc="upper right")
        ax_hist.grid(alpha=0.3)

    fig.suptitle("Comparação visual + histograma (3 posições Z)",
                 fontsize=12, y=1.01)
    fig.tight_layout()
    return fig


# ---------------- tabela ----------------

def make_table(samples: List[dict], metric_names: List[str]) -> pd.DataFrame:
    rows = []
    for s in samples:
        row = {"Fase": s["phase"], "z (mm)": s["z_mm"]}
        for m in metric_names:
            row[DISPLAY[m]] = s["scores"][m]
        rows.append(row)
    return pd.DataFrame(rows)
