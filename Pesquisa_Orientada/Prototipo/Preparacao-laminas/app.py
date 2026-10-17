# app.py

import json
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import streamlit as st
from streamlit.errors import StreamlitAPIException

from config import (N_TRAYS, SLIDES_PER_TRAY, DEFAULT_PARAMS,
                    image_path, slide_key, EXPORT_FILE)
from storage import load_state, save_state, get_slide, update_slide
from processing import detect_regions, draw_regions, magic_wand_flood_fill
from qr_utils import read_qr
from demo import generate_demo_slide
from clickable import clickable_image

st.set_page_config(
    page_title="Preparação de Lâminas",
    layout="wide",
    page_icon="🔬",
)

# ============================================================
#                    CSS EXTERNO
# ============================================================
_css_path = Path(__file__).parent / "styles.css"
if _css_path.exists():
    st.markdown(
        f"<style>{_css_path.read_text(encoding='utf-8')}</style>",
        unsafe_allow_html=True,
    )

# ============================================================
#                    ESTADO DE SESSÃO
# ============================================================
if "state" not in st.session_state:
    st.session_state.state = load_state()
if "selected_tray" not in st.session_state:
    st.session_state.selected_tray = 1
if "current_slide" not in st.session_state:
    st.session_state.current_slide = None

STATUS_ICON = {"empty": "⬜", "loaded": "🟦", "prepared": "✅"}

# ============================================================
#   HELPERS (PDF e Toolbar)
# ============================================================
@st.cache_data
def _load_guia_pdf(path_str: str, mtime: float) -> bytes:
    return Path(path_str).read_bytes()


def _render_toolbar(width_px: int = 800):
    """Renderiza a barra de ferramentas ilustrativa acima da lâmina."""
    toolbar_path = Path(__file__).parent / "images" / "toolbar_app.png"
    if toolbar_path.exists():
        st.image(str(toolbar_path), width=width_px)


# ============================================================
#                    SIDEBAR
# ============================================================
st.sidebar.title("🔬 Preparação")
with st.sidebar:
    st.session_state.selected_tray = st.selectbox(
        "Bandeja",
        list(range(1, N_TRAYS + 1)),
        index=st.session_state.selected_tray - 1,
    )

    total = N_TRAYS * SLIDES_PER_TRAY
    prep = sum(
        1 for s in st.session_state.state["slides"].values()
        if s.get("status") == "prepared"
    )
    st.progress(prep / total, text=f"{prep}/{total} preparadas")

    if st.button("🏠 Início", use_container_width=True):
        st.session_state.current_slide = None
        st.rerun()

    st.divider()
    with st.expander("📖 Guia dos parâmetros", expanded=False):
        _pdf_path = Path(__file__).parent / "Preparação das lâminas.pdf"
        if not _pdf_path.exists():
            st.warning(
                "PDF não encontrado. Coloque "
                "`Preparação das lâminas.pdf` na mesma pasta do `app.py`."
            )
        else:
            pdf_bytes = _load_guia_pdf(
                str(_pdf_path), _pdf_path.stat().st_mtime,
            )
            _rendered = False
            try:
                st.pdf(pdf_bytes, height=520)
                _rendered = True
            except AttributeError:
                pass  # Streamlit < 1.49 — sem st.pdf
            except StreamlitAPIException:
                pass  # streamlit-pdf incompatível — fallback abaixo

            if not _rendered:
                import base64
                pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")
                st.components.v1.html(
                    f'<embed src="data:application/pdf;base64,{pdf_b64}" '
                    f'type="application/pdf" width="100%" height="520">',
                    height=540,
                )
                st.markdown(
                    f'<a href="data:application/pdf;base64,{pdf_b64}" '
                    f'download="Preparação das lâminas.pdf">'
                    f'⬇️ Baixar PDF</a>',
                    unsafe_allow_html=True,
                )


# ============================================================
#   DETECÇÃO AUTOMÁTICA CACHEADa
# ============================================================
@st.cache_data(show_spinner="Detectando áreas...", max_entries=16)
def _detect_cached(path_str: str, mtime: float, params_items: tuple):
    img = cv2.imread(path_str)
    params = dict(params_items)
    regions, mask = detect_regions(img, params)
    return regions, mask


# ============================================================
#   SALVAR PREPARAÇÃO (compartilhado entre wand e auto)
# ============================================================
def _save_preparation(tray: int, pos: int, regions_key: str):
    regs = st.session_state[regions_key]
    if not regs:
        st.error("Adicione pelo menos uma região.")
        return
    sk_names = ["sat_threshold", "val_threshold", "canny_low",
                "canny_high", "min_area", "morph_kernel"]
    params = {
        k: st.session_state.get(f"p_{k}_{tray}_{pos}", DEFAULT_PARAMS[k])
        for k in sk_names
    }
    params["padding"] = DEFAULT_PARAMS["padding"]
    update_slide(st.session_state.state, tray, pos, {
        "scan_mode": "specific",
        "status": "prepared",
        "regions": regs,
        "params": params,
    })
    st.session_state.state = load_state()
    st.success(f"Salvo! {len(regs)} região(ões).")


# ============================================================
#        TELA 1 · GRADE 8×2 (lâminas verticais 1"×3")
# ============================================================
def render_tray_grid():
    tray = st.session_state.selected_tray
    st.header(f"Bandeja {tray} — selecione uma lâmina")
    st.caption(
        "⬜ vazia · 🟦 carregada · ✅ preparada  "
        "(lâminas exibidas em proporção real 1\" × 3\")"
    )

    with st.container(key="slide_grid"):
        for row in range(2):
            cols = st.columns(8, gap="small")
            for col_idx in range(8):
                pos = row * 8 + col_idx + 1
                slide = get_slide(st.session_state.state, tray, pos)
                icon = STATUS_ICON.get(slide["status"], "⬜")
                with cols[col_idx]:
                    if st.button(
                        f"{icon} {pos:02d}",
                        key=f"b_{tray}_{pos}",
                        use_container_width=False,
                    ):
                        st.session_state.current_slide = (tray, pos)
                        st.rerun()


# ============================================================
#                TELA 2 · PREPARAÇÃO DA LÂMINA
# ============================================================
def render_slide_prep():
    tray, pos = st.session_state.current_slide
    slide = get_slide(st.session_state.state, tray, pos)

    # ---------- imagem disponível? ----------
    path = image_path(tray, pos)
    if not path.exists():
        st.warning("Nenhuma imagem capturada ainda para esta lâmina.")
        cc1, cc2 = st.columns(2)
        if cc1.button("🎲 Gerar imagem de demonstração"):
            cv2.imwrite(
                str(path),
                generate_demo_slide(f"T{tray:02d}-S{pos:02d}"),
            )
            st.rerun()
        uploaded = cc2.file_uploader(
            "Ou envie uma imagem", type=["png", "jpg", "jpeg"],
        )
        if uploaded:
            buf = np.frombuffer(uploaded.read(), np.uint8)
            img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
            cv2.imwrite(str(path), img)
            st.rerun()
        return

    img = cv2.imread(str(path))

    # ---------- QR ----------
    qr_data, _ = read_qr(img)
    if qr_data and slide.get("qr_id") != qr_data:
        update_slide(
            st.session_state.state, tray, pos,
            {"qr_id": qr_data, "status": "loaded"},
        )
        st.session_state.state = load_state()
        slide = get_slide(st.session_state.state, tray, pos)

    # ---------- cabeçalho compacto ----------
    c1, c2, c3 = st.columns([1, 3, 3])
    with c1:
        if st.button("← Voltar", use_container_width=True):
            st.session_state.current_slide = None
            st.rerun()
    with c2:
        st.markdown(f"### Lâmina {slide_key(tray, pos)}")
    with c3:
        qr_badge = f"QR: `{qr_data}`" if qr_data else "QR: **não detectado**"
        st.markdown(f"{qr_badge} · Status: **{slide['status']}**")

    # ========================================================
    #    COLUNAS PRINCIPAIS: controles (1/3) | imagem (2/3)
    # ========================================================
    col_ctrl, col_vis = st.columns([1, 2], gap="medium")

    # ---------- controles de nível superior ----------
    with col_ctrl:
        current_mode = slide.get("scan_mode") or "whole"
        scan_mode = st.radio(
            "Modo de varredura",
            ["whole", "specific"],
            format_func=lambda v: (
                "🖼️ Lâmina inteira" if v == "whole"
                else "🎯 Áreas específicas"
            ),
            index=0 if current_mode == "whole" else 1,
            horizontal=True,
            key=f"mode_{tray}_{pos}",
        )
        
        if scan_mode == "specific":
            method = st.radio(
                "Método",
                ["wand", "auto"],
                format_func=lambda v: (
                    "🪄 Magic Wand" if v == "wand"
                    else "🤖 Detecção automática"
                ),
                horizontal=True,
                key=f"selmode_{tray}_{pos}",
            )
            #toolbar_width = st.slider(
            #    "Largura da barra (px)",
            #    min_value=100, max_value=1500, value=800, step=50,
            #    key=f"tbar_w_{tray}_{pos}",
            #    help="Ajusta o tamanho da barra de ferramentas acima da imagem."
            #)
            toolbar_width = 300
            
        else:
            method = None
            toolbar_width = None

    # ---------- modo "lâmina inteira" ----------
    if scan_mode == "whole":
        with col_vis:
            st.image(
                cv2.cvtColor(img, cv2.COLOR_BGR2RGB),
                use_container_width=True,
            )
        with col_ctrl:
            st.divider()
            if st.button(
                "💾 Salvar configuração", type="primary",
                use_container_width=True,
            ):
                update_slide(st.session_state.state, tray, pos, {
                    "scan_mode": "whole",
                    "status": "prepared",
                    "regions": [],
                    "params": {},
                })
                st.session_state.pop(f"regions_{tray}_{pos}", None)
                st.session_state.state = load_state()
                st.success("Configurado para lâmina inteira.")
        return

    # ---------- modo "áreas específicas" ----------
    regions_key = f"regions_{tray}_{pos}"
    if regions_key not in st.session_state:
        st.session_state[regions_key] = list(slide.get("regions", []))

    if method == "wand":
        render_wand(tray, pos, img, regions_key, col_ctrl, col_vis, toolbar_width)
    else:
        render_auto(tray, pos, img, regions_key, slide, path,
                    col_ctrl, col_vis, toolbar_width)


# ============================================================
#          MODO MAGIC WAND
# ============================================================
def render_wand(tray, pos, img, regions_key, col_ctrl, col_vis, toolbar_width):
    thr_k      = f"wand_thr_{tray}_{pos}"
    pad_k      = f"wand_pad_{tray}_{pos}"
    cont_k     = f"wand_cont_{tray}_{pos}"
    clahe_k    = f"wand_clahe_{tray}_{pos}"
    thick_k    = f"wand_thick_{tray}_{pos}"
    pending_k  = f"wand_pending_{tray}_{pos}"
    consumed_k = f"wand_consumed_{tray}_{pos}"
    sig_k      = f"wand_sig_{tray}_{pos}"

    if thr_k   not in st.session_state: st.session_state[thr_k]   = 40
    if pad_k   not in st.session_state: st.session_state[pad_k]   = 0
    if cont_k  not in st.session_state: st.session_state[cont_k]  = True
    if clahe_k not in st.session_state: st.session_state[clahe_k] = False
    if thick_k not in st.session_state: st.session_state[thick_k] = 1

    # ---------- controles ----------
    with col_ctrl:
        s1, s2 = st.columns(2)
        with s1:
            threshold = st.slider(
                "Limiar (threshold)", 1, 200, key=thr_k,
                help=("Distância máx. de cor (CIELAB). "
                      "Baixo = estrito; alto = permissivo."),
            )
        with s2:
            padding = st.slider(
                "Margem (px)", 0, 50, key=pad_k,
                help="Expande a borda da seleção em N pixels.",
            )

        ck1, ck2 = st.columns(2)
        with ck1:
            preprocess_ok = st.checkbox(
                "CLAHE (realce)", key=clahe_k,
                help="Útil para tecido esmaecido.",
            )
        with ck2:
            contiguous = st.checkbox(
                "Contíguo", key=cont_k,
                help="Só o blob conectado ao clique.",
            )
        preprocess_val = "clahe" if preprocess_ok else None

        thickness = st.slider(
            "Espessura da borda (px)", 1, 5, key=thick_k,
            help="Espessura das linhas tracejadas que marcam as regiões.",
        )

    # ---------- visualização + click ----------
    pending = st.session_state.get(pending_k)
    vis = img.copy()
    vis = draw_regions(
        vis, st.session_state[regions_key],
        color=(0, 180, 0), thickness=thickness,
    )
    if pending:
        vis = draw_regions(
            vis, [pending], color=(0, 0, 255), thickness=thickness,
        )

    with col_vis:
        _render_toolbar(toolbar_width)
        coords = clickable_image(
            vis, key=f"wand_comp_{tray}_{pos}",
        )

    # ---------- processa clique / recomputa pendente ----------
    old_sig = st.session_state.get(sig_k)
    needs_rerun = False

    if coords and coords.get("ts") != st.session_state.get(consumed_k):
        st.session_state[consumed_k] = coords["ts"]
        sig = (coords["x"], coords["y"], threshold, padding,
               contiguous, preprocess_val)
        region, _ = magic_wand_flood_fill(
            img, coords["x"], coords["y"], threshold,
            padding, contiguous, preprocess_val,
        )
        st.session_state[pending_k] = region
        st.session_state[sig_k] = sig
        needs_rerun = True
    elif pending and old_sig:
        new_sig = (old_sig[0], old_sig[1], threshold, padding,
                   contiguous, preprocess_val)
        if old_sig != new_sig:
            region, _ = magic_wand_flood_fill(
                img, old_sig[0], old_sig[1], threshold,
                padding, contiguous, preprocess_val,
            )
            st.session_state[pending_k] = region
            st.session_state[sig_k] = new_sig
            needs_rerun = True

    if needs_rerun:
        st.rerun()

    # ---------- ações + Salvar + lista ----------
    with col_ctrl:
        st.divider()
        pending = st.session_state.get(pending_k)
        if pending:
            area = pending.get("area_px", pending["w"] * pending["h"])
            st.caption(f"🔴 Pendente · {area:,} px²")
            if st.button(
                "✅ Adicionar", type="primary", use_container_width=True,
                key=f"add_{tray}_{pos}",
            ):
                st.session_state[regions_key].append(pending)
                st.session_state[pending_k] = None
                st.rerun()
            if st.button(
                "❌ Descartar", use_container_width=True,
                key=f"disc_{tray}_{pos}",
            ):
                st.session_state[pending_k] = None
                st.rerun()
        else:
            st.caption("👆 Clique sobre o tecido na imagem.")

        if st.button(
            "💾 Salvar preparação", type="primary",
            use_container_width=True, key=f"save_w_{tray}_{pos}",
        ):
            _save_preparation(tray, pos, regions_key)

        st.divider()
        render_regions_list(tray, pos, regions_key)


# ============================================================
#          MODO DETECÇÃO AUTOMÁTICA
# ============================================================
def render_auto(tray, pos, img, regions_key, slide, path,
                col_ctrl, col_vis, toolbar_width):
    sk = {
        "sat_threshold": f"p_sat_threshold_{tray}_{pos}",
        "val_threshold": f"p_val_threshold_{tray}_{pos}",
        "canny_low":     f"p_canny_low_{tray}_{pos}",
        "canny_high":    f"p_canny_high_{tray}_{pos}",
        "min_area":      f"p_min_area_{tray}_{pos}",
        "morph_kernel":  f"p_morph_kernel_{tray}_{pos}",
    }
    thick_k = f"auto_thick_{tray}_{pos}"
    if thick_k not in st.session_state:
        st.session_state[thick_k] = 1

    saved_params = slide.get("params") or DEFAULT_PARAMS.copy()
    for k, key in sk.items():
        if key not in st.session_state:
            st.session_state[key] = saved_params.get(k, DEFAULT_PARAMS[k])

    # ---------- controles ----------
    with col_ctrl:
        if st.button("🔄 Valores padrão", use_container_width=True,
                     key=f"reset_{tray}_{pos}"):
            for k, key in sk.items():
                st.session_state[key] = DEFAULT_PARAMS[k]
            st.rerun()

        st.slider("Saturação", 0, 120, key=sk["sat_threshold"])
        st.slider("Valor máx.", 0, 255, key=sk["val_threshold"])
        st.slider("Canny low", 0, 255, key=sk["canny_low"])
        st.slider("Canny high", 0, 255, key=sk["canny_high"])
        st.slider("Área mín. (px²)", 100, 60000, step=100,
                  key=sk["min_area"])
        st.slider("Kernel", 1, 25, step=2, key=sk["morph_kernel"])
        thickness = st.slider(
            "Espessura da borda (px)", 1, 5, key=thick_k,
            help="Espessura das linhas tracejadas que marcam as regiões.",
        )

    current = {k: st.session_state[key] for k, key in sk.items()}
    current["padding"] = saved_params.get(
        "padding", DEFAULT_PARAMS["padding"]
    )

    # ---------- detecção ----------
    params_items = tuple(sorted(current.items()))
    mtime = path.stat().st_mtime
    regions_detected, mask = _detect_cached(str(path), mtime, params_items)

    # ---------- imagem + máscara lado a lado ----------
    vis = draw_regions(img, regions_detected, thickness=thickness)
    with col_vis:
        _render_toolbar(toolbar_width)
        col_i, col_m = st.columns(2, gap="small")
        with col_i:
            st.image(
                cv2.cvtColor(vis, cv2.COLOR_BGR2RGB),
                caption=f"{len(regions_detected)} área(s)",
                use_container_width=True,
            )
        with col_m:
            st.image(
                mask, caption="Máscara",
                use_container_width=True, clamp=True,
            )

    # ---------- ações + Salvar + lista ----------
    with col_ctrl:
        st.divider()
        if not regions_detected:
            st.caption("Nenhuma área acima do limiar.")
        else:
            st.caption(f"**{len(regions_detected)} área(s) detectada(s)**")
            if st.button(
                "➕ Adicionar todas", type="primary",
                use_container_width=True,
                key=f"auto_add_{tray}_{pos}",
            ):
                existing = {
                    (r["x"], r["y"], r["w"], r["h"])
                    for r in st.session_state[regions_key]
                }
                added = 0
                for r in regions_detected:
                    bbox = (r["x"], r["y"], r["w"], r["h"])
                    if bbox not in existing:
                        st.session_state[regions_key].append(r)
                        added += 1
                st.success(f"{added} adicionada(s).")
                st.rerun()
            if st.button(
                "♻️ Substituir lista", use_container_width=True,
                key=f"auto_sub_{tray}_{pos}",
            ):
                st.session_state[regions_key] = list(regions_detected)
                st.rerun()

        if st.button(
            "💾 Salvar preparação", type="primary",
            use_container_width=True, key=f"save_a_{tray}_{pos}",
        ):
            _save_preparation(tray, pos, regions_key)

        st.divider()
        render_regions_list(tray, pos, regions_key)


# ============================================================
#          LISTA DE REGIÕES PREPARADAS
# ============================================================
def render_regions_list(tray, pos, regions_key):
    regions = st.session_state[regions_key]
    label = f"📋 Regiões preparadas ({len(regions)})"
    with st.expander(label, expanded=False):
        if not regions:
            st.caption("Nenhuma região na lista.")
            return
        for i, r in enumerate(list(regions)):
            c1, c2 = st.columns([4, 1])
            c1.write(
                f"**#{i+1}** · x={r['x']} y={r['y']} "
                f"w={r['w']} h={r['h']}"
            )
            if c2.button("🗑️", key=f"rm_{tray}_{pos}_{i}"):
                st.session_state[regions_key].pop(i)
                st.rerun()
        if st.button(
            "🗑️ Limpar todas", use_container_width=True,
            key=f"clr_{tray}_{pos}",
        ):
            st.session_state[regions_key] = []
            st.rerun()


# ============================================================
#                TELA 3 · EXPORTAR
# ============================================================
def render_export():
    st.header("Exportar plano de varredura")
    st.write("Gera o `scan_plan.json` que o scanner consumirá.")

    plan = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "trays": [],
    }
    prepared = 0
    for t in range(1, N_TRAYS + 1):
        slides_out = []
        for p in range(1, SLIDES_PER_TRAY + 1):
            s = get_slide(st.session_state.state, t, p)
            if s.get("status") != "prepared":
                continue
            prepared += 1
            regions_export = [
                {"x": r["x"], "y": r["y"], "w": r["w"], "h": r["h"]}
                for r in s.get("regions", [])
            ]
            slides_out.append({
                "position": p,
                "qr_id": s.get("qr_id"),
                "scan_mode": s.get("scan_mode"),
                "regions": regions_export,
                "params": s.get("params", {}),
            })
        if slides_out:
            plan["trays"].append({"tray_id": t, "slides": slides_out})

    st.metric(
        "Lâminas preparadas",
        f"{prepared}/{N_TRAYS * SLIDES_PER_TRAY}",
    )
    st.code(json.dumps(plan, indent=2), language="json")

    if st.button(
        "💾 Gerar arquivo", type="primary", disabled=prepared == 0,
    ):
        EXPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
        EXPORT_FILE.write_text(json.dumps(plan, indent=2))
        st.success(f"Arquivo salvo em `{EXPORT_FILE.resolve()}`")

    st.download_button(
        "⬇️ Baixar scan_plan.json",
        data=json.dumps(plan, indent=2),
        file_name="scan_plan.json",
        mime="application/json",
        disabled=prepared == 0,
    )


# ============================================================
#                ROTEAMENTO
# ============================================================
if st.session_state.current_slide is not None:
    render_slide_prep()
else:
    tab_grid, tab_export = st.tabs(["🗂️ Bandejas", "📤 Exportar"])
    with tab_grid:
        render_tray_grid()
    with tab_export:
        render_export()
