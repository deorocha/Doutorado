"""plot_figures.py — gera as 4 figuras do artigo (4 métricas, sem MSCG).

Fig 1: curvas de foco sobrepostas (4 métricas normalizadas)
Fig 2: tempo por frame em 2 resoluções (4 métricas)
Fig 3: painéis individuais (coarse vs refine, 2×2)
Fig 4: tempo total de autofoco decomposto (CPU + settle)

Uso:
  python plot_figures.py                  # todas as 4
  python plot_figures.py --figure 1       # apenas a Fig 1
  python plot_figures.py --image outra.png

Saída: figures/ a 300 DPI.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from autofocus.metrics import METRICS, DISPLAY
from autofocus.sweep import run_sweep
from autofocus.hardware import MockZAxis, MockCamera


# ======================================================================
# Configuração — 4 métricas (sem MSCG)
# ======================================================================

COLORS = {
    "laplacian": "#1f77b4",
    "brenner":   "#2ca02c",
    "tenengrad": "#ff7f0e",
    "fft_hf":    "#9467bd",
}

ORDER = ["laplacian", "brenner", "tenengrad", "fft_hf"]

# Timing reportado no artigo (Tabela 4 e Tabela 6)
TIMING_PAPER = {
    # metric: (per_frame_3.9MP, per_frame_1.3MP, total_autofocus_ms)
    "laplacian": (31.27,  9.90, 2749),
    "brenner":   (41.97, 14.18, 2799),
    "tenengrad": (51.52, 17.88, 2837),
    "fft_hf":    (241.83, 55.02, 3338),
}
SETTLE_PER_FRAME_MS = 200.0
N_FRAMES_BRENT = 13


def setup_matplotlib():
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "DejaVu Serif", "serif"],
        "font.size": 11,
        "axes.labelsize": 12,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "legend.fontsize": 9,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "figure.dpi": 300,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "axes.grid": True,
        "grid.alpha": 0.3,
        "axes.axisbelow": True,
    })


# ======================================================================
# Carregamento e sweep
# ======================================================================

def load_image(path: str) -> np.ndarray:
    img = cv2.imread(path)
    if img is None:
        raise SystemExit(
            f"Não encontrei '{path}'. Coloque uma imagem H&E como "
            f"'sample_he.png' na raiz do projeto.")
    return cv2.resize(img, (1280, 1024), interpolation=cv2.INTER_AREA)


def run_fresh_sweep(base_img: np.ndarray,
                    true_focus_mm: float = 22.0) -> list[dict]:
    zaxis = MockZAxis()
    cam = MockCamera(zaxis, true_focus_mm=true_focus_mm,
                     size=(1024, 1280), base_image=base_img)
    cfg = {
        "z_min": 0.0, "z_max": 40.0, "n_coarse": 25,
        "n_refine": 11, "window_factor": 2.0,
        "refine_mode": "each",
        "metrics": {k: METRICS[k] for k in ORDER},
        "primary": "tenengrad",
        "settle_s": 0.0,
        "roi": None,
        "save_dir": None,
    }
    samples: list[dict] = []
    try:
        for _step, _total, _sample, all_samples in run_sweep(
                zaxis, cam, cfg):
            samples = all_samples
    finally:
        try: cam.close()
        except Exception: pass
        try: zaxis.close()
        except Exception: pass
    return samples


# ======================================================================
# Fig 1 — Curvas sobrepostas
# ======================================================================

def _normalize(vals: list[float]) -> list[float]:
    lo, hi = min(vals), max(vals)
    if hi - lo < 1e-12:
        return [0.0] * len(vals)
    return [(v - lo) / (hi - lo) for v in vals]


def fig1_curves(samples: list[dict], out_path: Path):
    fig, ax = plt.subplots(figsize=(8, 4.5))

    for metric in ORDER:
        data = sorted(
            [s for s in samples if not np.isnan(s["scores"][metric])],
            key=lambda s: s["z_mm"])
        if not data:
            continue
        zs = [s["z_mm"] for s in data]
        ys = _normalize([s["scores"][metric] for s in data])
        ax.plot(zs, ys, marker="o", markersize=4, linewidth=1.8,
                color=COLORS[metric], label=DISPLAY[metric], alpha=0.9)

    ax.set_xlabel("Posição Z (mm)")
    ax.set_ylabel("Score normalizado [0–1]")
    ax.set_title("Curvas de foco — 4 métricas "
                 "(varredura grossa + refinamento)")
    ax.set_xlim(0, 40)
    ax.set_ylim(-0.02, 1.05)
    ax.legend(loc="upper right", framealpha=0.95)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"  ✓ {out_path}")


# ======================================================================
# Fig 2 — Tempo por frame em 2 resoluções
# ======================================================================

def fig2_timing(out_path: Path):
    metrics_sorted = sorted(ORDER, key=lambda m: TIMING_PAPER[m][1])
    labels = [DISPLAY[m] for m in metrics_sorted]
    t_39 = [TIMING_PAPER[m][0] for m in metrics_sorted]
    t_13 = [TIMING_PAPER[m][1] for m in metrics_sorted]
    colors = [COLORS[m] for m in metrics_sorted]

    x = np.arange(len(labels))
    width = 0.38

    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars1 = ax.bar(x - width / 2, t_39, width,
                   label="3,9 MP (2385×1634)",
                   color=colors, alpha=0.45,
                   edgecolor="black", linewidth=0.5)
    bars2 = ax.bar(x + width / 2, t_13, width,
                   label="1,3 MP (scanner: 1280×1024)",
                   color=colors, alpha=1.0,
                   edgecolor="black", linewidth=0.5)

    for bars in (bars1, bars2):
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, h * 1.03,
                    f"{h:.1f}", ha="center", va="bottom", fontsize=8)

    ax.set_ylabel("Tempo de cálculo por frame (ms)")
    ax.set_title("Custo computacional por frame (menor = melhor)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_yscale("log")
    ax.legend(loc="upper left", framealpha=0.95)
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"  ✓ {out_path}")


# ======================================================================
# Fig 3 — Painéis individuais (2×2)
# ======================================================================

def fig3_panels(samples: list[dict], out_path: Path):
    fig, axes = plt.subplots(2, 2, figsize=(10, 8), squeeze=False)

    for i, metric in enumerate(ORDER):
        ax = axes[i // 2][i % 2]
        color = COLORS[metric]

        coarse = sorted(
            [s for s in samples
             if s["phase"] == "coarse"
             and not np.isnan(s["scores"][metric])],
            key=lambda s: s["z_mm"])
        if coarse:
            ax.plot([s["z_mm"] for s in coarse],
                    [s["scores"][metric] for s in coarse],
                    "o-", color=color, markersize=3.5, alpha=0.6,
                    label="coarse", linewidth=1.2)

        refine = sorted(
            [s for s in samples
             if s["phase"] == "refine"
             and not np.isnan(s["scores"][metric])],
            key=lambda s: s["z_mm"])
        if refine:
            ax.plot([s["z_mm"] for s in refine],
                    [s["scores"][metric] for s in refine],
                    "s--", color=color, markersize=4, alpha=1.0,
                    label="refine", linewidth=1.5)

        all_valid = [s for s in samples
                     if not np.isnan(s["scores"][metric])]
        if all_valid:
            peak = max(all_valid, key=lambda s: s["scores"][metric])
            ax.axvline(peak["z_mm"], color="red",
                       linestyle=":", alpha=0.8, linewidth=1.2,
                       label=f"ótimo z={peak['z_mm']:.2f}")

        ax.set_title(DISPLAY[metric], color=color, fontweight="bold")
        ax.set_xlabel("Posição Z (mm)")
        ax.set_ylabel("Score")
        ax.set_xlim(0, 40)
        ax.legend(loc="upper left", fontsize=8, framealpha=0.9)

    fig.suptitle("Painéis individuais por métrica "
                 "(grossa vs. refinamento)",
                 fontsize=13, fontweight="bold", y=1.00)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"  ✓ {out_path}")


# ======================================================================
# Fig 4 — Tempo total decomposto
# ======================================================================

def fig4_stacked(out_path: Path):
    metrics_sorted = sorted(ORDER, key=lambda m: TIMING_PAPER[m][2])
    labels = [DISPLAY[m] for m in metrics_sorted]
    totals = [TIMING_PAPER[m][2] for m in metrics_sorted]
    cpu = [t - (SETTLE_PER_FRAME_MS * N_FRAMES_BRENT) for t in totals]
    settle = [SETTLE_PER_FRAME_MS * N_FRAMES_BRENT] * len(totals)
    colors = [COLORS[m] for m in metrics_sorted]

    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(x, cpu, color=colors, alpha=0.9,
           edgecolor="black", linewidth=0.5,
           label="CPU (13 frames)")
    ax.bar(x, settle, bottom=cpu,
           color="#d3d3d3", alpha=0.9,
           edgecolor="black", linewidth=0.5,
           label="Settling mecânico (13 × 200 ms)")

    for i, (total, c) in enumerate(zip(totals, cpu)):
        ax.text(i, total + 40, f"{total} ms",
                ha="center", va="bottom", fontsize=9, fontweight="bold")
        if c > 100:
            ax.text(i, c / 2, f"{c:.0f} ms",
                    ha="center", va="center", fontsize=8,
                    color="white", fontweight="bold")

    ax.set_ylabel("Tempo total de autofoco (ms)")
    ax.set_title("Decomposição do tempo total (CPU + settling)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.legend(loc="upper left", framealpha=0.95)
    ax.set_ylim(0, max(totals) * 1.12)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"  ✓ {out_path}")


# ======================================================================
# Main
# ======================================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--figure", default="all",
                    choices=["1", "2", "3", "4", "all"])
    ap.add_argument("--image", default="./images/sample_he.png")
    ap.add_argument("--out-dir", default="figures")
    args = ap.parse_args()

    setup_matplotlib()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    needs_sweep = args.figure in ("1", "3", "all")
    samples = None
    if needs_sweep:
        print(f"Carregando {args.image} e rodando sweep com 4 métricas...")
        base = load_image(args.image)
        samples = run_fresh_sweep(base)
        print(f"  Sweep concluído: {len(samples)} amostras\n")

    print(f"Gerando figura(s) em {out_dir}/")
    if args.figure in ("1", "all"):
        fig1_curves(samples, out_dir / "fig1_curvas_sobrepostas.png")
    if args.figure in ("2", "all"):
        fig2_timing(out_dir / "fig2_tempo_por_frame.png")
    if args.figure in ("3", "all"):
        fig3_panels(samples, out_dir / "fig3_paineis_por_metrica.png")
    if args.figure in ("4", "all"):
        fig4_stacked(out_dir / "fig4_tempo_total_decomposto.png")

    print(f"\n✓ Figuras em: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
