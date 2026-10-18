# app.py

import json
import math
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import streamlit as st
from streamlit.errors import StreamlitAPIException

from config import (N_TRAYS, SLIDES_PER_TRAY, DEFAULT_PARAMS,
                    DEFAULT_BORDER_COLOR, image_path, slide_key,
                    EXPORT_FILE)
from storage import load_state, get_slide, update_slide
from processing import detect_regions, draw_regions, magic_wand_flood_fill
from qr_utils import read_qr
from demo import generate_demo_slide
from clickable import drawable_image
from toolbar import toolbar

st.set_page_config(
    page_title="Preparação de Lâminas",
    layout="wide",
    page_icon="🔬",
)

DISPLAY_MAX_W = 1400   # largura máxima da imagem enviada ao navegador

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
#   CACHES E HELPERS
# ============================================================
@st.cache_data(show_spinner=False)
def _load_guia_pdf(path_str: str, mtime: float) -> bytes:
    return Path(path_str).read_bytes()


def _fit_width(img: np.ndarray, max_width: int) -> tuple[np.ndarray, float]:
    """Reduz img para caber em max_width. Retorna (img_reduzida, escala)."""
    h, w = img.shape[:2]
    if w <= max_width:
        return img, 1.0
    scale = max_width / w
    new_h = int(round(h * scale))
    return cv2.resize(img, (max_width, new_h),
                      interpolation=cv2.INTER_AREA), scale


def _scale_region(r: dict, scale: float) -> dict:
    """Escala uma região (x, y, w, h, contour, points) por `scale`."""
    out = {
        "x": int(r["x"] * scale),
        "y": int(r["y"] * scale),
        "w": max(1, int(r["w"] * scale)),
        "h": max(1, int(r["h"] * scale)),
    }
    if r.get("kind"):
        out["kind"] = r["kind"]
    if r.get("contour"):
        out["contour"] = [
            [int(px * scale), int(py * scale)] for px, py in r["contour"]
        ]
    if r.get("points"):
        out["points"] = [
            [int(px * scale), int(py * scale)] for px, py in r["points"]
        ]
    if "area_px" in r:
        out["area_px"] = int(r["area_px"] * (scale ** 2))
    return out


def _hex_to_bgr(hex_color: str) -> tuple:
    """Converte '#RRGGBB' em tupla BGR para o OpenCV."""
    h = hex_color.lstrip("#")
    return (int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16))


@st.cache_data(show_spinner="Carregando imagem...", max_entries=4)
def _load_slide_base(path_str: str, mtime: float, max_width: int):
    """Cache: lê a imagem uma única vez, reduz e detecta QR."""
    img = cv2.imread(path_str)
    if img is None:
        return None, None, 1.0
    qr_data, _ = read_qr(img)
    img_small, scale = _fit_width(img, max_width)
    return img_small, qr_data, scale


@st.cache_data(show_spinner="Detectando áreas...", max_entries=16)
def _detect_small(path_str: str, mtime: float, max_width: int,
                  params_items: tuple):
    """Cache: detecção automática na imagem reduzida."""
    img_small, _, scale = _load_slide_base(path_str, mtime, max_width)
    if img_small is None:
        return [], np.zeros((1, 1), np.uint8), 1.0

    params = dict(params_items)
    params["min_area"] = max(1, int(params["min_area"] * scale * scale))
    params["padding"] = int(params["padding"] * scale)
    k = max(1, int(round(params["morph_kernel"] * scale)))
    if k % 2 == 0:
        k += 1
    params["morph_kernel"] = k

    regions, mask = detect_regions(img_small, params)
    return regions, mask, scale


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


def _render_guia_pdf():
    """Renderiza o PDF do guia no expander do sidebar."""
    _pdf_path = Path(__file__).parent / "Preparação das lâminas.pdf"
    if not _pdf_path.exists():
        st.warning(
            "PDF não encontrado. Coloque "
            "`Preparação das lâminas.pdf` na mesma pasta do `app.py`."
        )
        return

    pdf_bytes = _load_guia_pdf(
        str(_pdf_path), _pdf_path.stat().st_mtime,
    )
    try:
        st.pdf(pdf_bytes, height=520)
        return
    except (AttributeError, StreamlitAPIException):
        pass

    # fallback: <embed> via data URL
    import base64
    pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")
    st.components.v1.html(
        f'<embed src="data:application/pdf;base64,{pdf_b64}" '
        f'type="application/pdf" width="100%" height="520">',
        height=540,
    )
    st.markdown(
        f'<a href="data:application/pdf;base64,{pdf_b64}" '
        f'download="Preparação das lâminas.pdf">⬇️ Baixar PDF</a>',
        unsafe_allow_html=True,
    )


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
        _render_guia_pdf()


# ============================================================
#        TELA 1 · GRADE 8×2
# ============================================================
def render_tray_grid():
    tray = st.session_state.selected_tray
    st.header(f"Bandeja {tray} — selecione uma lâmina")
    st.caption(
        "Fundo verde = **configurada** · fundo vermelho = "
        "**não configurada**.  "
        "Ícone: ⬜ vazia · 🟦 carregada · ✅ preparada."
    )

    with st.container(key="slide_grid"):
        for row in range(2):
            cols = st.columns(8, gap="small")
            for col_idx in range(8):
                pos = row * 8 + col_idx + 1
                slide = get_slide(st.session_state.state, tray, pos)
                status = slide["status"]
                icon = STATUS_ICON.get(status, "⬜")
                with cols[col_idx]:
                    with st.container(key=f"sb_{status}_{tray}_{pos}"):
                        if st.button(
                            f"{icon} {pos:02d}",
                            key=f"b_{tray}_{pos}",
                            use_container_width=False,
                        ):
                            st.session_state.current_slide = (tray, pos)
                            st.rerun()


# ============================================================
#                TELA 2 · PREPARAÇÃO
# ============================================================
def render_slide_prep():
    tray, pos = st.session_state.current_slide
    slide = get_slide(st.session_state.state, tray, pos)

    path = image_path(tray, pos)
    if not path.exists():
        st.warning("Nenhuma imagem capturada ainda para esta lâmina.")
        cc1, cc2 = st.columns(2)
        if cc1.button("🎲 Gerar imagem de demonstração"):
            cv2.imwrite(
                str(path),
                generate_demo_slide(slide_key(tray, pos)),
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

    _mtime = path.stat().st_mtime
    img_small, qr_data, scale = _load_slide_base(
        str(path), _mtime, DISPLAY_MAX_W,
    )
    if img_small is None:
        st.error("Não foi possível carregar a imagem.")
        return

    if qr_data and slide.get("qr_id") != qr_data:
        update_slide(
            st.session_state.state, tray, pos,
            {"qr_id": qr_data, "status": "loaded"},
        )
        st.session_state.state = load_state()
        slide = get_slide(st.session_state.state, tray, pos)

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

    col_ctrl, col_vis = st.columns([1, 2], gap="medium")

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
                ["manual", "auto"],
                format_func=lambda v: (
                    "🖌️ Manual (barra de ferramentas)" if v == "manual"
                    else "🤖 Detecção automática"
                ),
                horizontal=True,
                key=f"selmode_{tray}_{pos}",
            )
        else:
            method = None

    if scan_mode == "whole":
        with col_vis:
            st.image(cv2.cvtColor(img_small, cv2.COLOR_BGR2RGB),
                     use_container_width=True)
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

    regions_key = f"regions_{tray}_{pos}"
    if regions_key not in st.session_state:
        st.session_state[regions_key] = list(slide.get("regions", []))

    if method == "manual":
        render_manual(tray, pos, img_small, scale, regions_key, slide,
                      col_ctrl, col_vis)
    else:
        render_auto(tray, pos, path, _mtime, img_small, scale,
                    regions_key, slide, col_ctrl, col_vis)


# ============================================================
#          MODO MANUAL (barra de ferramentas + magic wand)
# ============================================================
def render_manual(tray, pos, img_small, scale, regions_key, slide,
                  col_ctrl, col_vis):
    tool_k     = f"tool_{tray}_{pos}"
    tool_ts_k  = f"tool_ts_{tray}_{pos}"
    pending_k  = f"wand_pending_{tray}_{pos}"
    consumed_k = f"manual_consumed_{tray}_{pos}"

    thr_k   = f"wand_thr_{tray}_{pos}"
    pad_k   = f"wand_pad_{tray}_{pos}"
    cont_k  = f"wand_cont_{tray}_{pos}"
    clahe_k = f"wand_clahe_{tray}_{pos}"
    thick_k = f"wand_thick_{tray}_{pos}"
    color_k = f"wand_color_{tray}_{pos}"
    sig_k   = f"wand_sig_{tray}_{pos}"

    if tool_k not in st.session_state:    st.session_state[tool_k]    = "magic_wand"
    if thr_k not in st.session_state:     st.session_state[thr_k]     = 40
    if pad_k not in st.session_state:     st.session_state[pad_k]     = 0
    if cont_k not in st.session_state:    st.session_state[cont_k]    = True
    if clahe_k not in st.session_state:   st.session_state[clahe_k]   = False
    if thick_k not in st.session_state:   st.session_state[thick_k]   = 1
    if color_k not in st.session_state:   st.session_state[color_k]   = DEFAULT_BORDER_COLOR

    with col_vis:
        clicked = toolbar(
            selected=st.session_state[tool_k],
            key=f"tbar_{tray}_{pos}",
        )
        if clicked and clicked.get("ts") != st.session_state.get(tool_ts_k):
            st.session_state[tool_ts_k] = clicked["ts"]
            st.session_state[tool_k]    = clicked["tool"]
            st.session_state[pending_k] = None
            st.rerun()

    current_tool = st.session_state[tool_k]

    with col_ctrl:
        if current_tool == "magic_wand":
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
            padding_small  = max(0, int(round(padding * scale)))
        else:
            threshold, padding = 40, 0
            contiguous, preprocess_val = True, None
            padding_small = 0
            st.caption(
                "🖌️ Desenhe sobre a imagem. "
                "`Zoom` = roda do mouse para ampliar; arrastar para mover."
            )

        cc1, cc2 = st.columns(2)
        with cc1:
            with st.container(key=f"cp_wrap_{tray}_{pos}"):
                border_color = st.color_picker(
                    "Cor da borda", key=color_k,
                    help="Cor das bordas tracejadas das regiões já aceitas.",
                )
        with cc2:
            thickness = st.slider(
                "Espessura da borda (px)", 1, 5, key=thick_k,
                help="Espessura das linhas tracejadas que marcam as regiões.",
            )

    # ---------- recomputa pendente se slider mudou ----------
    pending = st.session_state.get(pending_k)
    old_sig = st.session_state.get(sig_k)
    if pending and old_sig:
        new_sig = (old_sig[0], old_sig[1], threshold, padding,
                   contiguous, preprocess_val)
        if old_sig != new_sig:
            region_small, _ = magic_wand_flood_fill(
                img_small, old_sig[0], old_sig[1], threshold,
                padding_small, contiguous, preprocess_val,
            )
            if region_small:
                rf = _scale_region(region_small, 1.0 / scale)
                rf["kind"]    = "contour"
                rf["area_px"] = int(
                    region_small.get("area_px", 0) / (scale * scale)
                )
                st.session_state[pending_k] = rf
                pending = rf
            else:
                st.session_state[pending_k] = None
                pending = None
            st.session_state[sig_k] = new_sig

    regions_small = [_scale_region(r, scale)
                     for r in st.session_state[regions_key]]
    pending_small = _scale_region(pending, scale) if pending else None

    with col_vis:
        action = drawable_image(
            img_small,
            key=f"draw_comp_{tray}_{pos}",
            tool=current_tool,
            existing_regions=regions_small,
            pending_region=pending_small,
            thickness=thickness,
            border_color=border_color,
        )

    if action and action.get("ts") != st.session_state.get(consumed_k):
        st.session_state[consumed_k] = action["ts"]
        kind = action.get("action")

        if kind == "magic_wand":
            x, y = action["x"], action["y"]
            sig = (x, y, threshold, padding, contiguous, preprocess_val)
            region_small, _ = magic_wand_flood_fill(
                img_small, x, y, threshold, padding_small,
                contiguous, preprocess_val,
            )
            if region_small:
                rf = _scale_region(region_small, 1.0 / scale)
                rf["kind"]    = "contour"
                rf["area_px"] = int(
                    region_small.get("area_px", 0) / (scale * scale)
                )
                st.session_state[pending_k] = rf
            else:
                st.session_state[pending_k] = None
            st.session_state[sig_k] = sig
            st.rerun()

        elif kind == "region":
            rkind = action.get("kind")
            if rkind == "point":
                r_full = {
                    "kind": "point",
                    "x": int(action["x"] / scale),
                    "y": int(action["y"] / scale),
                    "w": 1, "h": 1, "area_px": 1,
                }
            else:
                r_full = {
                    "kind": rkind,
                    "x": int(action["x"] / scale),
                    "y": int(action["y"] / scale),
                    "w": max(1, int(action["w"] / scale)),
                    "h": max(1, int(action["h"] / scale)),
                }
                if "points" in action:
                    pts = [[int(px / scale), int(py / scale)]
                           for px, py in action["points"]]
                    r_full["contour"] = pts
                    r_full["points"]  = pts
                elif rkind == "rect":
                    r_full["contour"] = [
                        [r_full["x"], r_full["y"]],
                        [r_full["x"] + r_full["w"], r_full["y"]],
                        [r_full["x"] + r_full["w"],
                         r_full["y"] + r_full["h"]],
                        [r_full["x"], r_full["y"] + r_full["h"]],
                    ]
                elif rkind == "ellipse":
                    cx = int(action["cx"] / scale)
                    cy = int(action["cy"] / scale)
                    rx = int(action["rx"] / scale)
                    ry = int(action["ry"] / scale)
                    pts = []
                    for ang in range(0, 360, 10):
                        a = math.radians(ang)
                        pts.append([
                            int(cx + rx * math.cos(a)),
                            int(cy + ry * math.sin(a)),
                        ])
                    r_full["contour"] = pts
            st.session_state[regions_key].append(r_full)
            st.rerun()

    # ---------- ações + Salvar + lista ----------
    with col_ctrl:
        st.divider()
        if pending:
            area = pending.get("area_px", 0)
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
            st.caption(f"🖌️ Ferramenta ativa: **{current_tool}**")

        if st.button(
            "💾 Salvar preparação", type="primary",
            use_container_width=True, key=f"save_m_{tray}_{pos}",
        ):
            _save_preparation(tray, pos, regions_key)

        st.divider()
        render_regions_list(tray, pos, regions_key)


# ============================================================
#          MODO DETECÇÃO AUTOMÁTICA
# ============================================================
def render_auto(tray, pos, path, mtime, img_small, scale,
                regions_key, slide, col_ctrl, col_vis):
    sk = {
        "sat_threshold": f"p_sat_threshold_{tray}_{pos}",
        "val_threshold": f"p_val_threshold_{tray}_{pos}",
        "canny_low":     f"p_canny_low_{tray}_{pos}",
        "canny_high":    f"p_canny_high_{tray}_{pos}",
        "min_area":      f"p_min_area_{tray}_{pos}",
        "morph_kernel":  f"p_morph_kernel_{tray}_{pos}",
    }
    thick_k = f"auto_thick_{tray}_{pos}"
    color_k = f"auto_color_{tray}_{pos}"
    if thick_k not in st.session_state:
        st.session_state[thick_k] = 1
    if color_k not in st.session_state:
        st.session_state[color_k] = DEFAULT_BORDER_COLOR

    saved_params = slide.get("params") or DEFAULT_PARAMS.copy()
    for k, key in sk.items():
        if key not in st.session_state:
            st.session_state[key] = saved_params.get(k, DEFAULT_PARAMS[k])

    with col_ctrl:
        if st.button("🔄 Valores padrão", use_container_width=True,
                     key=f"reset_{tray}_{pos}"):
            for k, key in sk.items():
                st.session_state[key] = DEFAULT_PARAMS[k]
            st.rerun()

        c1, c2 = st.columns(2)
        with c1:
            st.slider("Saturação", 0, 120, key=sk["sat_threshold"])
        with c2:
            st.slider("Valor máx.", 0, 255, key=sk["val_threshold"])

        c3, c4 = st.columns(2)
        with c3:
            st.slider("Canny low", 0, 255, key=sk["canny_low"])
        with c4:
            st.slider("Canny high", 0, 255, key=sk["canny_high"])

        c5, c6 = st.columns(2)
        with c5:
            st.slider("Área mín. (px²)", 100, 60000, step=100,
                      key=sk["min_area"])
        with c6:
            st.slider("Kernel", 1, 25, step=2, key=sk["morph_kernel"])

        cc1, cc2 = st.columns(2)
        with cc1:
            with st.container(key=f"cp_wrap_{tray}_{pos}"):
                border_color = st.color_picker(
                    "Cor da borda", key=color_k,
                    help="Cor das bordas tracejadas das regiões detectadas.",
                )
        with cc2:
            thickness = st.slider(
                "Espessura da borda (px)", 1, 5, key=thick_k,
                help="Espessura das linhas tracejadas que marcam as regiões.",
            )

    current = {k: st.session_state[key] for k, key in sk.items()}
    current["padding"] = saved_params.get(
        "padding", DEFAULT_PARAMS["padding"]
    )

    params_items = tuple(sorted(current.items()))
    regions_small, mask_small, _ = _detect_small(
        str(path), mtime, DISPLAY_MAX_W, params_items,
    )

    bgr = _hex_to_bgr(border_color)
    vis_small = draw_regions(img_small.copy(), regions_small,
                             color=bgr, thickness=thickness)

    with col_vis:
        col_i, col_m = st.columns(2, gap="small")
        with col_i:
            st.image(
                cv2.cvtColor(vis_small, cv2.COLOR_BGR2RGB),
                caption=f"{len(regions_small)} área(s)",
                use_container_width=True,
            )
        with col_m:
            st.image(
                mask_small, caption="Máscara",
                use_container_width=True, clamp=True,
            )

    with col_ctrl:
        st.divider()
        if not regions_small:
            st.caption("Nenhuma área acima do limiar.")
        else:
            st.caption(f"**{len(regions_small)} área(s) detectada(s)**")
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
                for r_small in regions_small:
                    r_full = _scale_region(r_small, 1.0 / scale)
                    bbox = (r_full["x"], r_full["y"],
                            r_full["w"], r_full["h"])
                    if bbox not in existing:
                        st.session_state[regions_key].append(r_full)
                        added += 1
                st.success(f"{added} adicionada(s).")
                st.rerun()
            if st.button(
                "♻️ Substituir lista", use_container_width=True,
                key=f"auto_sub_{tray}_{pos}",
            ):
                st.session_state[regions_key] = [
                    _scale_region(r, 1.0 / scale) for r in regions_small
                ]
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
            kind = r.get("kind", "contour")
            c1.write(
                f"**#{i+1}** ({kind}) · x={r['x']} y={r['y']} "
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
                if r.get("kind") != "point"
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
