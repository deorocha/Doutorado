# REFERÊNCIAS:
# https://ramondomingos.com.br/hello-spacy-processamento-de-linguagem-natural/

# DEPENDÊNCIAS:
# pip install -r requirements.txt
# python -m spacy download pt_core_news_lg
# python -m spacy download pt_core_news_sm
# python -m textblob.download_corpora

import streamlit as st
import base64
from PIL import Image

# Configuração da página - DEVE SER A PRIMEIRA COISA
st.set_page_config(
    page_title="WebMedia 2024",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Função para carregar CSS globalmente
def load_global_css():
    try:
        with open("styles/styles.css", "r", encoding="utf-8") as f:
            css_content = f.read()
            # Injeta o CSS globalmente em todas as páginas
            st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Erro ao carregar CSS: {e}")
load_global_css()

# Sidebar com imagem no topo absoluto
with st.sidebar.container():
    # Imagem no topo fixo

    image = Image.open("./images/webmedia2024.png")
    st.image(image, use_container_width=True)
    # st.image("./images/webmedia2024.png", use_container_width=True)
    
# Conteúdo principal
st.title("Análise LLM dos anais do WebMedia 2024")

try:
    st.image("images/background.png", use_container_width=True)
except:
    st.info("Imagem background.png não encontrada")

st.write("""
##### Esta aplicação demonstra diversos recursos de Processamento de Linguagem Natural (LLM), tendo como fonte de dados os artigos mostrados durante o evento.
""")
