# REFERÊNCIAS:
# https://ramondomingos.com.br/hello-spacy-processamento-de-linguagem-natural/

# DEPENDÊNCIAS:
# pip install -r requirements.txt
# python -m spacy download pt_core_news_lg
# python -m spacy download pt_core_news_sm
# python -m textblob.download_corpora

import streamlit as st
import base64

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
        with open("/styles/styles.css", "r", encoding="utf-8") as f:
            css_content = f.read()
            # Injeta o CSS globalmente em todas as páginas
            st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Erro ao carregar CSS: {e}")

# Carrega o CSS global
load_global_css()

# Função para carregar imagem como base64
def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except:
        return None

# Sidebar com imagem no topo absoluto
with st.sidebar:
    # Imagem no topo fixo
    try:
        with open("./images/webmedia2024.png", "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode()
        
        st.markdown(
            f'''
            <div class="sidebar-header">
                <img src="data:image/png;base64,{image_base64}" 
                     style="width:100%; margin:0; padding:0; display:block;">
            </div>
            ''',
            unsafe_allow_html=True
        )
    except:
        st.markdown(
            '''
            <div class="sidebar-header" style="background:linear-gradient(135deg, #4CAF50, #2E7D32); color:white; padding:1rem; text-align:center;">
                <h3 style="margin:0;">🌿 WebMedia 2024</h3>
            </div>
            ''',
            unsafe_allow_html=True
        )

# Conteúdo principal
st.title("Análise LLM dos anais do WebMedia 2024")

try:
    st.image("images/background.png", use_container_width=True)
except:
    st.info("Imagem background.png não encontrada")

st.write("""
#### Esta aplicação demonstra diversos recursos de Processamento de Linguagem Natural (LLM), tendo como fonte de dados os artigos mostrados durante o evento.
""")


