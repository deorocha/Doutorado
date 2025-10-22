import streamlit as st
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).parent
CSS_PATH = PROJECT_ROOT / "styles" / "styles.css"
IMAGES_PATH = PROJECT_ROOT / "images"
PROGRAMS_PATH = PROJECT_ROOT / "programas"

fluxograma_image_path = IMAGES_PATH / "fluxograma.png"

def load_css(css_path):
    try:
        with open(css_path, "r", encoding="utf-8") as f:
            css_content = f.read()
            st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.error("Arquivo CSS não encontrado na pasta 'styles/'")
    except Exception as e:
        st.error(f"Erro ao carregar CSS: {e}")
load_css(CSS_PATH)

st.title("📊 Fluxograma da Atividade")

st.write("Diagrama do processo completo do WebMedia 2024:")

try:
    st.image(fluxograma_image_path, caption="", use_container_width=True)
except Exception as e:
    st.info("Imagem fluxograma.png não encontrada")
