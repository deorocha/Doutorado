"""Views de resultado — cada função renderiza uma seção."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

from autofocus.metrics import DISPLAY
from autofocus.plotting import (
    make_accuracy_fig, make_fig, make_fig_per_metric,
    make_histogram_comparison_fig, make_histogram_fig,
    make_histogram_gallery_fig, make_table,
)

VIEW_NAMES = [
    "📈 Curvas sobrepostas",
    "📊 Painéis por métrica",
    "🎯 Acurácia + Tempo",
    "📊 Histogramas",
    "📋 Tabela",
    "🖼️ Melhores imagens",
]


def _st_fig(fig: plt.Figure) -> None:
    st.pyplot(fig)
    plt.close(fig)


# ---------------- views ----------------

def view_curves(samples: List[dict], metric_names: List[str],
                best: Dict[str, dict], **_) -> None:
    _st_fig(make_fig(samples, metric_names, best=best))


def view_per_metric(samples: List[dict], metric_names: List[str],
                    best: Dict[str, dict], **_) -> None:
    _st_fig(make_fig_per_metric(samples, metric_names, best))


def view_accuracy(samples: List[dict], metric_names: List[str],
                  best: Dict[str, dict], primary: str, **_) -> None:
    true_focus_used = st.session_state.get("true_focus_used")

    if true_focus_used is not None:
        st.markdown(
            f"**Acurácia + tempo** — erro absoluto entre o pico de cada "
            f"métrica e o foco verdadeiro simulado (**z = "
            f"{true_focus_used:.2f} mm**), junto com o tempo médio."
        )
        st.info(
            "ℹ️ **Sobre a convergência:** em imagens sintéticas "
            "(desfoque Gaussiano simétrico), as 4 métricas tendem a "
            "convergir no mesmo pico. Com **imagem de referência real** "
            "(H&E, foto), as métricas podem divergir — refletindo "
            "diferenças espectrais que o sintético não captura. Neste "
            "caso, o diferenciador é **acurácia × custo computacional**."
        )
    else:
        st.markdown(
            "**Sem ground truth** — posição Z ótima de cada métrica "
            "(mediana = proxy de consenso) + tempo médio de cálculo."
        )

    _st_fig(make_accuracy_fig(best, metric_names, samples,
                              true_focus=true_focus_used))

    st.markdown("**Detalhamento**")
    rows = []
    for m in metric_names:
        if m not in best:
            continue
        b = best[m]
        valid_t = [s["times"][m] for s in samples
                   if m in s.get("times", {})
                   and not np.isnan(s["times"][m])]
        row = {
            "Métrica": DISPLAY[m],
            "z_ótimo (mm)": b["z_mm"],
            "Tempo médio (ms)": float(np.mean(valid_t) * 1000) if valid_t else None,
            "Tempo total (ms)": float(np.sum(valid_t) * 1000) if valid_t else None,
        }
        if true_focus_used is not None:
            row["Erro (µm)"] = abs(b["z_mm"] - true_focus_used) * 1000
        rows.append(row)

    df = pd.DataFrame(rows)
    if true_focus_used is not None and "Erro (µm)" in df.columns:
        df = df.sort_values("Erro (µm)")
    else:
        df = df.sort_values("Tempo médio (ms)")
    df = df.reset_index(drop=True)
    df.index = df.index + 1
    df.index.name = "Rank"

    df_disp = df.copy()
    df_disp["z_ótimo (mm)"] = df_disp["z_ótimo (mm)"].map(lambda x: f"{x:.3f}")
    df_disp["Tempo médio (ms)"] = df_disp["Tempo médio (ms)"].map(
        lambda x: "—" if pd.isna(x) else f"{x:.2f}")
    df_disp["Tempo total (ms)"] = df_disp["Tempo total (ms)"].map(
        lambda x: "—" if pd.isna(x) else f"{x:.1f}")
    if "Erro (µm)" in df_disp.columns:
        df_disp["Erro (µm)"] = df_disp["Erro (µm)"].map(lambda x: f"{x:.1f}")

    st.dataframe(df_disp, use_container_width=True)
    st.download_button(
        "⬇️ Baixar CSV de acurácia + tempo",
        data=df.to_csv().encode("utf-8"),
        file_name="accuracy_comparison.csv", mime="text/csv")


def view_histograms(samples: List[dict], metric_names: List[str],
                    best: Dict[str, dict], primary: str, **_) -> None:
    st.markdown(
        "Histogramas das imagens capturadas em diferentes posições do "
        "eixo Z. **(1)** imagens no pico de cada métrica; **(2)** por "
        "que histogramas globais **não** discriminam foco."
    )

    modo = st.radio(
        "Visualização:",
        ["Histograma no pico de cada métrica",
         "Comparação: foco vs. desfoque (métrica primária)",
         "Galeria visual + histograma (3 posições)"],
        horizontal=True, key="hist_mode",
    )
    st.divider()

    if modo == "Histograma no pico de cada métrica":
        use_color = st.checkbox(
            "Mostrar canais RGB (requer imagem colorida)", False,
            help="Se a imagem for cinza, ignora esta opção.")
        disponiveis = sum(
            1 for m in metric_names if m in best
            and Path(best[m].get("img_path") or "").exists())
        if disponiveis == 0:
            st.warning(
                "⚠️ Nenhuma imagem em disco. Verifique se "
                "**'Salvar imagens permanentemente'** está marcado.")
            return
        _st_fig(make_histogram_fig(samples, metric_names, best,
                                   use_color=use_color))
        st.caption(
            f"**{disponiveis}/{len(metric_names)}** imagens disponíveis. "
            f"Eixo X = intensidade (0–255); Eixo Y = densidade.")

    elif modo == "Comparação: foco vs. desfoque (métrica primária)":
        st.subheader("Por que histogramas globais não discriminam foco")
        st.markdown(
            "Os **três histogramas abaixo** correspondem à mesma cena "
            f"em **z_min**, **z_ótimo** (pico de *{DISPLAY[primary]}*) e "
            "**z_max**. Se as distribuições forem quase idênticas, o "
            "**histograma global não é bom indicador de foco** — é "
            "preciso uma **métrica espacial**.")
        fig = make_histogram_comparison_fig(samples, primary)
        if fig is None:
            st.warning("⚠️ Não foi possível gerar a comparação.")
        else:
            _st_fig(fig)

    else:
        st.subheader("Galeria visual + histograma")
        st.markdown(
            f"Miniaturas em **z_min**, **pico ({DISPLAY[primary]})** e "
            "**z_max**, cada uma com histograma abaixo.")
        fig = make_histogram_gallery_fig(samples, primary)
        if fig is None:
            st.warning("⚠️ Não foi possível carregar as imagens.")
        else:
            _st_fig(fig)


def view_table(samples: List[dict], metric_names: List[str], **_) -> None:
    st.caption(
        "**Fase** — `coarse` = varredura grossa uniforme; `refine` = "
        "refinamento ao redor do pico de cada métrica. Scores em "
        "notação científica; `z` em mm com 3 casas.")
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


def view_best_images(best: Dict[str, dict], **_) -> None:
    imgs = list(best.items())
    if not imgs:
        st.info("Sem imagens para exibir.")
        return
    for i in range(0, len(imgs), 2):
        cols = st.columns(2)
        for j, (m, s) in enumerate(imgs[i:i + 2]):
            with cols[j]:
                st.markdown(f"### {DISPLAY[m]}")
                st.caption(f"z = **{s['z_mm']:.3f} mm** · "
                           f"score = {s['scores'][m]:.3e}")
                if s.get("img_path") and Path(s["img_path"]).exists():
                    st.image(s["img_path"], use_column_width=True)


# ---------------- dispatcher ----------------

VIEW_FUNCS = {
    "📈 Curvas sobrepostas":       view_curves,
    "📊 Painéis por métrica":      view_per_metric,
    "🎯 Acurácia + Tempo":         view_accuracy,
    "📊 Histogramas":              view_histograms,
    "📋 Tabela":                   view_table,
    "🖼️ Melhores imagens":         view_best_images,
}


def render_result_view(view: str, **kwargs) -> None:
    VIEW_FUNCS[view](**kwargs)
