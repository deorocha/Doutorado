import streamlit as st
from pathlib import Path

# Obtém o diretório raiz do projeto (onde está o app.py)
# Este script está em uma subpasta, então precisamos subir um nível
current_dir = Path(__file__).parent if "__file__" in locals() else Path.cwd()
project_root = current_dir.parent  # Sobe um nível para a pasta raiz

# Constrói caminhos absolutos para os arquivos na pasta raiz
# css_path = project_root / "styles" / "styles.css"
css_path = project_root / "styles/styles.css"
fluxograma_image_path = project_root / "images/fluxograma.png"

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
