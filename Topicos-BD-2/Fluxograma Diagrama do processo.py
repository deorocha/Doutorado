import streamlit as st
from pathlib import Path

# Tenta encontrar a raiz do projeto: sobe até encontrar a pasta 'styles' ou 'images'
def find_project_root(current_path):
    # Sobe até encontrar a raiz (onde estão as pastas styles e images)
    for parent in [current_path] + list(current_path.parents):
        if (parent / "styles").exists() and (parent / "images").exists():
            return parent
    return current_path  # fallback

# Obtém o diretório atual do script
current_dir = Path(__file__).parent if "__file__" in locals() else Path.cwd()
project_root = find_project_root(current_dir)

css_path = project_root / "styles" / "styles.css"
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
