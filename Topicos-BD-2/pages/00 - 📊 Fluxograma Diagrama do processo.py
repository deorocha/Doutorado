import streamlit as st
from pathlib import Path

# Obtém o diretório raiz do projeto (onde está o app.py)
# Este script está em uma subpasta, então precisamos subir um nível
current_dir = Path(__file__).parent if "__file__" in locals() else Path.cwd()
project_root = current_dir.parent  # Sobe um nível para a pasta raiz

# Constrói caminhos absolutos para os arquivos na pasta raiz
css_path = project_root / "styles" / "styles.css"
fluxograma_image_path = project_root / "images" / "fluxograma.png"

# CSS Global para todas as páginas
def load_global_css():
    try:
        with open(css_path, "r", encoding="utf-8") as f:
            css_content = f.read()
            st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
    except:
        # Fallback: CSS embutido básico
        st.markdown("""
        <style>
        .sidebar-header {
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            width: 340px !important;
            background: white !important;
            z-index: 9999 !important;
            margin: 0 !important;
            padding: 0 !important;
        }
        .sidebar-header img {
            width: 100% !important;
            height: auto !important;
            margin: 0 !important;
            padding: 0 !important;
        }
        section[data-testid="stSidebar"] > div:first-child {
            padding-top: 100px !important;
        }
        </style>
        """, unsafe_allow_html=True)

load_global_css()

st.title("Fluxograma da Atividade")

st.write("Diagrama do processo completo do WebMedia 2024:")

try:
    st.image(fluxograma_image_path, caption="", use_container_width=True)
except Exception as e:
    st.info("Imagem fluxograma.png não encontrada")
