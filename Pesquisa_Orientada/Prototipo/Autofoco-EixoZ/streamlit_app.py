"""App principal: sidebar + varredura + delegação para views."""
from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Dict, List

import cv2
import matplotlib.pyplot as plt
import numpy as np
import streamlit as st

from autofocus import (
    DISPLAY, METRICS, ESP8266SerialZAxis, ESP8266WiFiZAxis,
    MockCamera, MockZAxis, OpenCVCamera, load_uploaded_image,
    make_fig, run_sweep,
)
from streamlit_views import VIEW_NAMES, render_result_view


# ======================================================================
# Helpers de sidebar
# ======================================================================

def _render_calibration_panel(mode: str, **kwargs) -> None:
    st.caption(
        "**`$102`** é o número de passos por milímetro do eixo Z. "
        "Valor errado = posições em mm erradas.")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("📊 Ler `$102`", use_container_width=True):
            try:
                z = (ESP8266SerialZAxis(kwargs["port"], int(kwargs["baud"]))
                     if mode == "serial"
                     else ESP8266WiFiZAxis(kwargs["host"], timeout_s=10.0))
                v = z.read_z_steps_per_mm()
                z.close()
                if v is not None:
                    st.session_state["spm_read"] = v
                    st.success(f"`$102 = {v}`")
                else:
                    st.warning("`$102` não respondeu.")
            except Exception as e:
                st.error(f"Falha: {e}")
    with col_b:
        if st.session_state.get("spm_read"):
            st.metric("Lido do firmware", f"{st.session_state['spm_read']:g}")

    st.markdown("**Calibrar**")
    default_spm = float(st.session_state.get("spm_read") or 400.0)
    new_102 = st.number_input("Novo valor (steps/mm Z)", 1.0, 10000.0,
                              default_spm, 1.0, key="new_102_input")
    if st.button("💾 Aplicar `$102`", use_container_width=True):
        try:
            z = (ESP8266SerialZAxis(kwargs["port"], int(kwargs["baud"]))
                 if mode == "serial"
                 else ESP8266WiFiZAxis(kwargs["host"], timeout_s=10.0))
            z.send_setting("$102", new_102)
            z.close()
            st.success(f"`$102 = {new_102:g}` gravado.")
        except Exception as e:
            st.error(f"Falha: {e}")
    st.caption("**Procedimento:** `$0` → `Z10` → mede D com paquímetro → "
               "`$102_novo = $102_atual × 10 / D` → aplicar → repetir.")


def _render_camera_sidebar():
    """Controles de câmera + ROI. Retorna (idx, w, h, roi)."""
    with st.expander("Câmera (OpenCV)", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            cam_index = st.number_input("Índice da câmera", 0, 10, 0,
                                key="camera_index")
        with col2:
            cam_w = st.number_input("Largura", 320, 4096, 1280, 64,
                                key="camera_w")
        with col3:
            cam_h = st.number_input("Altura", 240, 4096, 1024, 64,
                                key="camera_h")
        
    with st.expander("ROI (opcional)", expanded=False):
        use_roi = st.checkbox("Recortar região", False, key="roi_enabled")
        roi = None
        if use_roi:
            y0 = st.number_input("y0", 0, int(cam_h), 0, key="roi_y0")
            y1 = st.number_input("y1", 0, int(cam_h), int(cam_h),
                                 key="roi_y1")
            x0 = st.number_input("x0", 0, int(cam_w), 0, key="roi_x0")
            x1 = st.number_input("x1", 0, int(cam_w), int(cam_w),
                                 key="roi_x1")
            roi = (y0, y1, x0, x1)
    return int(cam_index), int(cam_w), int(cam_h), roi


def _render_mock_sidebar():
    """Controles do mock. Retorna (base_image, h, w, true_focus)."""
    true_focus = st.number_input("Foco verdadeiro simulado (mm)",
                                 0.0, 40.0, 22.0, 0.5)
    st.markdown("**Imagem base do mock**")
    uploaded = st.file_uploader(
        "Enviar imagem de referência (opcional)",
        type=["png", "jpg", "jpeg", "tif", "tiff"],
        help="Aplica o desfoque sobre esta imagem em vez da sintética. "
             "Redimensionada para ≤ 1280 px no maior lado.",
        key="mock_base_upload")

    if uploaded is not None:
        img = load_uploaded_image(uploaded)
        if img is None:
            st.error("❌ Não foi possível carregar a imagem.")
            size_str = st.selectbox("Resolução simulada",
                                    ["512x640", "768x1024"], index=0)
            h, w = [int(x) for x in size_str.split("x")]
            return None, h, w, true_focus
        h, w = img.shape[:2]
        st.success(f"✅ {w}×{h} ({'RGB' if img.ndim == 3 else 'grayscale'})")
        preview = cv2.cvtColor(img, cv2.COLOR_BGR2RGB) if img.ndim == 3 else img
        st.image(preview, caption="Imagem base", use_column_width=True)
        return img, h, w, true_focus

    size_str = st.selectbox("Resolução simulada (sintética)",
                            ["512x640", "768x1024"], index=0)
    h, w = [int(x) for x in size_str.split("x")]
    return None, h, w, true_focus


# ======================================================================
# Main
# ======================================================================

def main() -> None:
    st.set_page_config(page_title="Autofoco Z — Scanner histológico",
                       page_icon="🔬", layout="wide")
    st.title("🔬 Autofoco do eixo Z — Scanner histológico")
    st.caption("4 métricas: Laplaciano · Tenengrad · Brenner · FFT — "
               "hardware ESP8266 + Nema17 + DRV8825")

    for k, v in [("samples", []), ("best", {}), ("elapsed", None),
                 ("run_metrics", []), ("spm_read", None),
                 ("true_focus_used", None)]:
        st.session_state.setdefault(k, v)

    # ---------------- SIDEBAR ----------------
    with st.sidebar:
        st.header("Hardware")
        hw_mode = st.radio(
            "Modo",
            ["Mock (demo)", "ESP-USB", "ESP-WiFi"], horizontal=True)

        mock_image = None
        h_sim, w_sim, true_focus = 512, 640, 22.0
        port, baud, host = "COM5", 115200, "192.168.1.42"
        cam_index, cam_w, cam_h, roi = 0, 1280, 1024, None

        if hw_mode == "Mock (demo)":
            mock_image, h_sim, w_sim, true_focus = _render_mock_sidebar()

        elif hw_mode == "ESP8266 — Serial USB":
            try:
                from autofocus.serial_utils import HAS_PYSERIAL
            except ImportError:
                HAS_PYSERIAL = False
            if not HAS_PYSERIAL:
                st.error("`pyserial` não instalado. `pip install pyserial`")
            with st.expander("Eixo Z — Serial", expanded=True):
                port = st.text_input("Porta serial", "COM5")
                baud = st.number_input("Baudrate", 9600, 250000, 115200, 9600)
            with st.expander("⚙️ Calibração `$102`", expanded=False):
                _render_calibration_panel(mode="serial", port=port, baud=baud)
            cam_index, cam_w, cam_h, roi = _render_camera_sidebar()

        else:
            try:
                import requests  # noqa: F401
                HAS_REQUESTS = True
            except ImportError:
                HAS_REQUESTS = False
            if not HAS_REQUESTS:
                st.error("`requests` não instalado. `pip install requests`")
            with st.expander("Eixo Z — WiFi", expanded=True):
                    host = st.text_input("IP do ESP8266", "192.168.1.42")
            with st.expander("⚙️ Calibração `$102`", expanded=False):
                _render_calibration_panel(mode="wifi", host=host)
            cam_index, cam_w, cam_h, roi = _render_camera_sidebar()

        st.header("Varredura")
        col1, col2 = st.columns(2)
        with col1:
            z_min = st.number_input("Z mínimo (mm)", 0.0, 200.0, 0.0, 0.5)
        with col2:
            z_max = st.number_input("Z máximo (mm)", 0.0, 200.0, 40.0, 0.5)
            
        col1, col2 = st.columns(2)
        with col1:
            n_coarse = st.slider("Pontos na varredura grossa", 5, 60, 25)
        with col2:
            settle_s = st.number_input("Pausa após mover (s)", 0.0, 5.0, 0.2, 0.05)

        st.header("Refinamento")
        col1, col2 = st.columns(2)
        with col1:
            n_refine = st.slider("Pontos por métrica", 3, 25, 11)
        with col2:
            window_factor = st.slider("Janela (× passo grosso)", 0.5, 5.0, 2.0, 0.25)

        refine_choice = st.radio("Refinar em torno de",
                                 ["Cada métrica", "Apenas a primária"], horizontal=True)

        st.header("Métricas")
        metric_names = st.multiselect(
            "Selecionadas", list(METRICS.keys()),
            default=list(METRICS.keys()),
            format_func=lambda k: DISPLAY[k])
        primary = st.selectbox(
            "Primária", metric_names or ["tenengrad"],
            format_func=lambda k: DISPLAY.get(k, k))

        st.header("Saída")
        col1, col2 = st.columns(2)
        with col1:
            save_images = st.checkbox("Salvar imagens", True)
        with col2:
            save_dir_str = st.text_input("Diretório", "autofocus_images",
                                         disabled=not save_images)

        st.header("Preview ao vivo")
        col1, col2 = st.columns(2)
        with col1:
            preview_every = st.slider(
                "Frequência do preview", 1, 5, 1,
                help="1 = todo frame. Valores maiores reduzem tráfego em "
                     "acesso remoto, mas mostram menos frames intermediários.")
        with col2:
            show_final_preview = st.checkbox(
                "Manter frame final", True,
                help="Mostra o frame do pico da métrica primária acima das "
                     "views de resultado.")

        col1, col2 = st.columns(2)
        with col1:
            run_btn = st.button("▶️ Iniciar varredura", type="primary",
                            use_container_width=True,
                            disabled=not metric_names)
        with col2:
            if st.button("🧹 Limpar resultados", use_container_width=True):
                for k in ("samples", "best", "elapsed", "run_metrics",
                          "true_focus_used"):
                    st.session_state[k] = ([] if k in ("samples", "run_metrics")
                                           else ({} if k == "best" else None))
                st.rerun()

    # ---------------- mensagens de modo ----------------
    if hw_mode == "Mock (demo)":
        extra = (f" sobre a imagem enviada ({mock_image.shape[1]}×"
                 f"{mock_image.shape[0]})" if mock_image is not None else "")
        st.info(f"**Modo demo.** Foco verdadeiro em "
                f"**z = {true_focus:.1f} mm**{extra}.")
    else:
        st.warning(f"**Modo {hw_mode}.** Calibre `$102` antes do "
                   f"primeiro teste.")

    # ---------------- testar conexão ----------------
    if hw_mode != "Mock (demo)":
        if st.button("🔌 Testar conexão (câmera + ESP)"):
            cam = None
            try:
                cam = OpenCVCamera(cam_index, cam_w, cam_h)
                img = cam.capture()
                st.success(f"✅ Câmera OK — frame {img.shape}")
                st.image(cv2.cvtColor(img, cv2.COLOR_BGR2RGB),
                         caption="Preview", width=420)
            except Exception as e:
                st.error(f"❌ Câmera: {e}")
            finally:
                if cam is not None:
                    try: cam.close()
                    except Exception: pass

            z_t = None
            try:
                z_t = (ESP8266SerialZAxis(port, baud)
                       if hw_mode == "ESP8266 — Serial USB"
                       else ESP8266WiFiZAxis(host, timeout_s=10.0))
                st.success(f"✅ ESP OK — `$102 = "
                           f"{z_t.read_z_steps_per_mm()}`")
            except Exception as e:
                st.error(f"❌ ESP: {e}")
            finally:
                if z_t is not None:
                    try: z_t.close()
                    except Exception: pass

    # ---------------- execução ----------------
    if run_btn and metric_names:
        # --- inicializa hardware ---
        try:
            if hw_mode == "Mock (demo)":
                zaxis = MockZAxis()
                camera = MockCamera(zaxis, true_focus_mm=true_focus,
                                    size=(h_sim, w_sim),
                                    base_image=mock_image)
            elif hw_mode == "ESP8266 — Serial USB":
                zaxis = ESP8266SerialZAxis(port, baud)
                camera = OpenCVCamera(cam_index, cam_w, cam_h)
            else:
                zaxis = ESP8266WiFiZAxis(host, timeout_s=60.0)
                camera = OpenCVCamera(cam_index, cam_w, cam_h)
        except Exception as e:
            st.error(f"Não foi possível iniciar hardware: {e}")
            st.stop()

        st.session_state["true_focus_used"] = (
            true_focus if hw_mode == "Mock (demo)" else None)

        # --- diretório de saída ---
        if save_images:
            save_dir = Path(save_dir_str)
            save_dir.mkdir(parents=True, exist_ok=True)
        else:
            save_dir = Path(tempfile.mkdtemp(prefix="autofocus_"))

        cfg = {
            "z_min": z_min, "z_max": z_max, "n_coarse": n_coarse,
            "n_refine": n_refine, "window_factor": window_factor,
            "refine_mode": "each" if refine_choice == "Cada métrica" else "primary",
            "metrics": {k: METRICS[k] for k in metric_names},
            "primary": primary,
            "settle_s": settle_s, "roi": roi, "save_dir": save_dir,
        }

        st.session_state.samples = []
        st.session_state.best = {}
        st.session_state.elapsed = None
        st.session_state.run_metrics = metric_names

        # ============ ÁREA DE PROGRESSO + PREVIEW AO VIVO ============
        progress = st.progress(0.0, text="Iniciando…")

        with st.container(border=True):
            col_prev, col_info = st.columns([1, 1], gap="medium")
            with col_prev:
                st.markdown("##### 📷 Frame atual")
                preview_ph = st.empty()
            with col_info:
                st.markdown("##### 📊 Status da varredura")
                status_ph = st.empty()
                chart_ph = st.empty()

        collected: List[dict] = []
        t0 = time.time()
        try:
            for step, total, sample, all_samples in run_sweep(zaxis, camera, cfg):
                collected = all_samples
                progress.progress(
                    min(step / total, 0.99),
                    text=f"[{sample['phase']}] {step}/{total}  "
                         f"z={sample['z_mm']:.2f} mm")

                # Preview + status: a cada `preview_every` frames
                if step % preview_every == 0 or step == total:
                    if (sample["img_path"]
                            and Path(sample["img_path"]).exists()):
                        preview_ph.image(
                            sample["img_path"],
                            caption=f"**{sample['phase']}** @ "
                                    f"z = {sample['z_mm']:.2f} mm",
                            use_column_width=True)
                    scores_txt = "  \n".join(
                        f"- **{DISPLAY[k]}**: {v:.4g}"
                        for k, v in sample["scores"].items())
                    status_ph.markdown(
                        f"**Fase:** `{sample['phase']}`  \n"
                        f"**z = {sample['z_mm']:.3f} mm**\n\n"
                        f"{scores_txt}")

                # Mini-gráfico: menos frequente (renderização custosa)
                if step % max(1, preview_every * 3) == 0 or step == total:
                    fig = make_fig(collected, metric_names)
                    chart_ph.pyplot(fig)
                    plt.close(fig)
        finally:
            try: zaxis.close()
            except Exception: pass
            try: camera.close()
            except Exception: pass

        elapsed = time.time() - t0
        progress.progress(1.0, text=f"✅ Concluído em {elapsed:.1f} s")

        # --- calcula o melhor por métrica ---
        best: Dict[str, dict] = {}
        for m in metric_names:
            valid = [s for s in collected if not np.isnan(s["scores"][m])]
            if valid:
                best[m] = max(valid, key=lambda s: s["scores"][m])

        # --- preview final: mantém ou limpa ---
        if show_final_preview and primary in best and best[primary].get("img_path"):
            preview_ph.image(
                best[primary]["img_path"],
                caption=f"🏆 **Foco ótimo** @ z = "
                        f"{best[primary]['z_mm']:.3f} mm "
                        f"({DISPLAY[primary]})",
                use_column_width=True)
            status_ph.markdown(
                f"✅ Varredura concluída em **{elapsed:.1f} s**\n\n"
                f"**{len(collected)}** medidas  \n"
                f"Melhor z: **{best[primary]['z_mm']:.3f} mm**  \n"
                f"Métrica: **{DISPLAY[primary]}**")
            chart_ph.empty()
        else:
            preview_ph.empty()
            status_ph.empty()
            chart_ph.empty()
            st.success(f"✅ {len(collected)} medidas em {elapsed:.1f} s — "
                       f"veja os resultados abaixo")

        # --- persiste resultados ---
        st.session_state.samples = collected
        st.session_state.best = best
        st.session_state.elapsed = elapsed

        # --- reposiciona o Z no ótimo da métrica primária (só hardware real) ---
        if hw_mode != "Mock (demo)" and primary in best:
            try:
                z_final = (ESP8266SerialZAxis(port, baud)
                           if hw_mode == "ESP8266 — Serial USB"
                           else ESP8266WiFiZAxis(host, timeout_s=10.0))
                z_final.move_to_mm(best[primary]["z_mm"])
                z_final.wait_until_idle()
                z_final.close()
                st.success(f"Eixo Z posicionado em "
                           f"**{best[primary]['z_mm']:.3f} mm** "
                           f"({DISPLAY[primary]})")
            except Exception as e:
                st.warning(f"Não reposicionei o Z: {e}")

    # ---------------- resultados ----------------
    if st.session_state.samples:
        st.divider()
        st.subheader("📊 Resultados")
        samples = st.session_state.samples
        best = st.session_state.best
        metric_names = st.session_state.run_metrics or list(METRICS.keys())

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Medidas", len(samples))
        if st.session_state.elapsed is not None:
            c2.metric("Tempo total", f"{st.session_state.elapsed:.1f} s")
        if primary in best:
            c3.metric(f"Ótimo — {DISPLAY[primary]}",
                      f"{best[primary]['z_mm']:.2f} mm")
        if len(best) > 1:
            zs_opt = [b["z_mm"] for b in best.values()]
            c4.metric("Spread", f"{(max(zs_opt) - min(zs_opt)):.2f} mm")

        view = st.radio(
            "Seção de resultados", VIEW_NAMES, horizontal=True,
            key="results_view", label_visibility="collapsed")

        render_result_view(view, samples=samples, metric_names=metric_names,
                           best=best, primary=primary)


if __name__ == "__main__":
    main()
