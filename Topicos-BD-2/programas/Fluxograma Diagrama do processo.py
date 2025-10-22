import streamlit as st
from pathlib import Path
import sys

# Adiciona o diretório raiz ao path do Python
current_dir = Path(__file__).parent if "__file__" in locals() else Path.cwd()
project_root = current_dir.parent

# Tenta importar a configuração
try:
    sys.path.append(str(project_root))
    from config import PROJECT_ROOT, CSS_PATH, IMAGES_PATH
except ImportError:
    # Fallback se o config não existir
    PROJECT_ROOT = project_root
    CSS_PATH = PROJECT_ROOT / "styles" / "styles.css"
    IMAGES_PATH = PROJECT_ROOT / "images"

# Constrói caminhos absolutos para os arquivos
css_path = PROJECT_ROOT / "styles" / "styles.css"
fluxograma_image_path = PROJECT_ROOT / "images" / "fluxograma.png"

def load_css(css_path):
    try:
        with open(css_path, "r", encoding="utf-8") as f:
            css_content = f.read()
            st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.error("Arquivo CSS não encontrado na pasta 'styles/'")
    except Exception as e:
        st.error(f"Erro ao carregar CSS: {e}")
load_css(css_path)

st.title("📊 Fluxograma da Atividade")

st.write("Diagrama do processo completo do WebMedia 2024:")

try:
    st.image(fluxograma_image_path, caption="", use_container_width=True)
except Exception as e:
    st.info("Imagem fluxograma.png não encontrada")
