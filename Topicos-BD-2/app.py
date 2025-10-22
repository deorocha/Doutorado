# REFERÊNCIAS:
# https://ramondomingos.com.br/hello-spacy-processamento-de-linguagem-natural/

# DEPENDÊNCIAS:
# pip install -r requirements.txt
# python -m spacy download pt_core_news_lg
# python -m spacy download pt_core_news_sm
# python -m textblob.download_corpora

import streamlit as st
import base64
from pathlib import Path
import os
import sys

# Configuração da página - DEVE SER A PRIMEIRA COISA
st.set_page_config(
    page_title="WebMedia 2024",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded"
)

PROJECT_ROOT = Path(__file__).parent
CSS_PATH = PROJECT_ROOT / "styles" / "styles.css"
IMAGES_PATH = PROJECT_ROOT / "images"
PROGRAMS_PATH = PROJECT_ROOT / "programas"

webmedia_image_path = IMAGES_PATH / "webmedia2024.png"
background_image_path = IMAGES_PATH / "background.png"
current_dir = Path(__file__).parent if "__file__" in locals() else Path.cwd()

with st.sidebar:
    st.write(current_dir)
    
# Função para carregar CSS globalmente - CORRIGIDA
def load_global_css(css_path):
    try:
        if css_path.exists():
            with open(css_path, "r", encoding="utf-8") as f:
                css_content = f.read()
                st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
        else:
            st.warning(f"⚠️ Arquivo CSS não encontrado em: {css_path}")
            # CSS fallback básico
            st.markdown("""
            <style>
                h1 { color: #1f3a2d; }
                .stButton button { background-color: #4CAF50; color: white; }
            </style>
            """, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"❌ Erro ao carregar CSS: {e}")

# Carrega o CSS global
load_global_css(CSS_PATH)

# CSS adicional para correções específicas
st.markdown("""
<style>
    /* Remove qualquer overflow horizontal global */
    .appview-container {
        overflow-x: hidden;
    }
    
    /* Ajusta espaçamento dos botões */
    .stButton button {
        margin: 2px 0;
    }
    
    /* Remove scroll horizontal do sidebar */
    section[data-testid="stSidebar"] > div {
        overflow-x: hidden !important;
    }
    
    /* Ajusta espaçamento interno do sidebar */
    .sidebar-content .stButton {
        margin: 0.2rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Função para carregar imagem como base64
def get_base64_image(IMAGES_PATH):
    try:
        with open(IMAGES_PATH, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except:
        return None

# Inicializar estado da página se não existir
if 'current_page' not in st.session_state:
    st.session_state.current_page = "Home"

# Mapeamento das páginas
PAGE_MAPPING = {
    "📊 Fluxograma": "Fluxograma Diagrama do processo.py",
    "📚 Conceitos LLM": "Conceitos sobre LLM.py", 
    "🔍 Reconhecimento de Entidades": "Reconhecimento de Entidades Nomeadas.py",
    "😊 Análise de Sentimento": "Analise de Sentimento.py",
    "🖼 Geração de Imagem": "Geracao de Imagem.py",
    "✂️ Tokenização": "Tokenizacao.py",
    "📝 Classes Gramaticais": "Classes Gramaticais.py",
    "🔗 Análise de Dependências": "Analise de Dependencias.py",
    "📏 Limites de Frases": "Deteccao de Limites de Frases.py",
    "📐 Análise de Similaridade": "Analise de Similaridade.py",
    "☁️ Word Cloud": "Word Cloud.py"
}

# Função para executar páginas externas
def run_external_page(page_file):
    try:
        # Caminho corrigido para funcionar no Streamlit Cloud
        page_path = current_dir / "programas" / page_file
        
        if page_path.exists():
            # Lê o conteúdo do arquivo
            with open(page_path, 'r', encoding='utf-8') as f:
                page_content = f.read()
            
            # Executa o código da página
            exec(page_content, globals())
        else:
            st.error(f"Arquivo {page_file} não encontrado em: {page_path}")
    except Exception as e:
        st.error(f"Erro ao carregar a página: {e}")
        st.info("A página pode estar em desenvolvimento")

# Função para mostrar a página inicial
def show_home():
    st.title("Análise LLM dos anais do WebMedia 2024")

    try:
        st.image(background_image_path, use_container_width=True)
    except Exception as e:
        st.info("Imagem background.png não encontrada")

    st.write("""
    #### Esta aplicação demonstra diversos recursos de Processamento de Linguagem Natural (LLM), tendo como fonte de dados os artigos mostrados durante o evento.
    """)

# Sidebar - ESTRUTURA CORRIGIDA
with st.sidebar:
    # IMAGEM NO TOPO - COM ESPAÇAMENTO REDUZIDO
    st.markdown('<div class="sidebar-header">', unsafe_allow_html=True)
    
    try:
        with open(webmedia_image_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode()
        
        st.markdown(
            f'<img src="data:image/png;base64,{image_base64}" alt="WebMedia 2024" style="width:100%; max-width:250px; margin:0 auto; display:block;">',
            unsafe_allow_html=True
        )
    except Exception as e:
        st.markdown(
            '''
            <div style="background:linear-gradient(135deg, #4CAF50, #2E7D32); color:white; padding:1rem; text-align:center; margin-bottom:10px;">
                <h3 style="margin:0;">🌿 WebMedia 2024</h3>
            </div>
            ''',
            unsafe_allow_html=True
        )
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # CONTEÚDO DO SIDEBAR - COM ESPAÇAMENTO REDUZIDO
    st.markdown('<div class="sidebar-content">', unsafe_allow_html=True)
    
    # Botão Home
    if st.button("🏠 Página Inicial", use_container_width=True, 
                type="primary" if st.session_state.current_page == "Home" else "secondary",
                key="home_btn"):
        st.session_state.current_page = "Home"
        st.rerun()
    
    # Botões das funcionalidades
    for icon_name, page_file in PAGE_MAPPING.items():
        page_name = icon_name
        if st.button(icon_name, use_container_width=True,
                    type="primary" if st.session_state.current_page == page_name else "secondary",
                    key=f"btn_{page_name}"):
            st.session_state.current_page = page_name
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

# Conteúdo principal baseado na página selecionada
if st.session_state.current_page == "Home":
    show_home()
else:
    # Executa a página externa correspondente
    page_file = PROGRAMS_PATH / PAGE_MAPPING.get(st.session_state.current_page)
    if page_file:
        run_external_page(page_file)
    else:
        st.error("Página não encontrada")
        if st.button("Voltar para Home"):
            st.session_state.current_page = "Home"
            st.rerun()






