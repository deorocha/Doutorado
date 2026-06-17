import streamlit as st
from ultralytics import YOLO
from PIL import Image
import pandas as pd
from pathlib import Path
import re
import base64

# 1. Configurações da página (Deve ser o primeiro comando Streamlit)
st.set_page_config(page_title="Detector de Doenças: Tomate", page_icon="🍅", layout="wide")

# Definir caminhos estruturados
PROJECT_ROOT = Path(__file__).parent
MODELS_PATH = PROJECT_ROOT / "models"
MODEL_FILE = MODELS_PATH / "best.pt"
SAMPLES_PATH = PROJECT_ROOT / "samples"   # Pasta para imagens de exemplo
README_FILE = PROJECT_ROOT / "README.md"    # Caminho do seu arquivo README.md

# Função Auxiliar: Converte caminhos de imagens locais do README em Base64 para o Streamlit
def render_markdown_with_local_images(markdown_text, root_path):
    # 1. Regex para sintaxe Markdown: ![alt](caminho)
    md_img_regex = r'!\[(.*?)\]\((.*?)\)'
    
    def replace_md_img(match):
        alt_text = match.group(1)
        img_path = match.group(2)
        # Ignorar URLs externas ou Base64 já existentes
        if not img_path.startswith(('http://', 'https://', 'data:')):
            full_path = Path(root_path) / img_path
            if full_path.exists():
                with open(full_path, "rb") as f:
                    encoded = base64.b64encode(f.read()).decode()
                mime_type = "image/png" if img_path.lower().endswith(".png") else "image/jpeg"
                return f'<img src="data:{mime_type};base64,{encoded}" alt="{alt_text}" style="max-width:100%;">'
        return match.group(0)

    # 2. Regex para sintaxe HTML dentro do markdown: <img src="caminho" ...>
    html_img_regex = r'<img\s+[^>]*src="([^"]+)"[^>]*>'
    
    def replace_html_img(match):
        full_tag = match.group(0)
        img_path = match.group(1)
        if not img_path.startswith(('http://', 'https://', 'data:')):
            full_path = Path(root_path) / img_path
            if full_path.exists():
                with open(full_path, "rb") as f:
                    encoded = base64.b64encode(f.read()).decode()
                mime_type = "image/png" if img_path.lower().endswith(".png") else "image/jpeg"
                return full_tag.replace(img_path, f"data:{mime_type};base64,{encoded}")
        return full_tag

    text = re.sub(md_img_regex, replace_md_img, markdown_text)
    text = re.sub(html_img_regex, replace_html_img, text)
    return text

# 2. Carregar o modelo treinado com cache
@st.cache_resource
def load_model():
    if not MODEL_FILE.exists():
        st.error(f"Modelo não encontrado em: {MODEL_FILE}")
        st.stop()
    return YOLO(str(MODEL_FILE))

try:
    model = load_model()
except Exception as e:
    st.error(f"Erro ao carregar o modelo: {e}")
    st.stop()

# Dicionário de tradução (inglês -> português)
TRADUCAO = {
    "Bacterial_spot": "Mancha bacteriana",
    "Early_blight": "Pinta preta",
    "healthy": "Saudável",
    "Late_blight": "Requeima",
    "Leaf_Mold": "Mofo-da-folha",
    "powdery_mildew": "Oídio",
    "Septoria_leaf_spot": "Mancha-de-septória",
    "Spider_mites Two-spotted_spider_mite": "Ácaro-rajado",
    "Target_Spot": "Mancha-alvo",
    "Tomato_mosaic_virus": "Vírus do mosaico",
    "Tomato_Yellow_Leaf_Curl_Virus": "Vírus do enrolamento amarelo"
}

# --- SIDEBAR (Configurações e Entrada de Mídia) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/1202/1202125.png", width=100)
    st.title("Configurações")
    
    st.subheader("Seleção de Imagem")
    app_mode = st.radio("Escolha a origem da imagem:", ["Fazer Upload", "Usar Exemplo"])
    
    image_to_predict = None

    if app_mode == "Fazer Upload":
        uploaded_file = st.file_uploader("Upload da foto da folha:", type=["jpg", "jpeg", "png"])
        if uploaded_file:
            image_to_predict = Image.open(uploaded_file)
    else:
        if SAMPLES_PATH.exists():
            sample_files = [f.name for f in SAMPLES_PATH.glob("*") if f.suffix.lower() in [".jpg", ".jpeg", ".png"]]
            if sample_files:
                selected_sample = st.selectbox("Selecione uma imagem de exemplo:", sample_files)
                image_to_predict = Image.open(SAMPLES_PATH / selected_sample)
            else:
                st.warning("Nenhuma imagem encontrada na pasta 'samples'.")
        else:
            st.error("Pasta 'samples' não encontrada no diretório raiz.")

    st.divider()
    st.subheader("Parâmetros da Interface")
    show_chart = st.checkbox("Mostrar gráfico de barras", value=True)
    min_conf = st.slider("Limiar de Confiança Mínimo (%)", 0, 100, 20)

# --- ÁREA PRINCIPAL (Interface baseada em Abas) ---
st.markdown('<h1 style="font-size: 35px;">🍅 Doenças de Tomateiros</h1>', unsafe_allow_html=True)

tab_detector, tab_info, tab_instrucoes = st.tabs(["🎯 Detector", "📄 Sobre o Projeto", "📖 Instruções"])

# --- ABA 1: DETECTOR ---
with tab_detector:
    if image_to_predict:
        col1, col2 = st.columns([1, 2])

        with st.spinner('IA analisando a saúde da folha...'):
            results = model.predict(image_to_predict)
            probs = results[0].probs
            names = results[0].names

            conf_dict_pt = {}
            for i, score in enumerate(probs.data.tolist()):
                nome_ingles = names[i]
                nome_portugues = TRADUCAO.get(nome_ingles, nome_ingles)
                conf_dict_pt[nome_portugues] = score * 100

            sorted_probs = dict(sorted(conf_dict_pt.items(), key=lambda item: item[1], reverse=True))
            top_class = list(sorted_probs.keys())[0]
            top_score = list(sorted_probs.values())[0]

        with col1:
            if top_score >= min_conf:
                st.success(f"**Resultado do Diagnóstico:** {top_class}")
            else:
                st.warning("A confiança do maior resultado está abaixo do limiar mínimo definido.")
            
            # st.image(image_to_predict, caption='Imagem Analisada', use_container_width=True)
            st.image(image_to_predict, caption='Imagem Analisada', width=400)
        
        with col2:
            st.info(f"**Grau de Certeza:** {top_score:.2f}%")
            if show_chart:
                df_probs = pd.DataFrame(list(sorted_probs.items()), columns=['Doença', 'Probabilidade (%)'])
                st.bar_chart(df_probs.set_index('Doença'))

        with st.expander("📊 Detalhamento Estatístico Completo"):
            df_full = pd.DataFrame(list(sorted_probs.items()), columns=['Condição', 'Confiança (%)'])
            st.table(df_full)
    else:
        st.info("Aguardando imagem para análise. Utilize o menu lateral (Sidebar) para carregar ou escolher um arquivo.")

# --- ABA 2: SOBRE O PROJETO (Injeção do README.md com imagens locais tratadas) ---
with tab_info:
    if README_FILE.exists():
        try:
            with open(README_FILE, "r", encoding="utf-8") as f:
                readme_markdown = f.read()
            
            # Executa a varredura e converte caminhos locais (como './images/correlation_matrix.png') em dados embutidos
            processed_markdown = render_markdown_with_local_images(readme_markdown, PROJECT_ROOT)
            
            st.markdown(processed_markdown, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Erro ao processar o arquivo README.md: {e}")
    else:
        st.error("Arquivo 'README.md' não encontrado no diretório do projeto.")

# --- ABA 3: INSTRUÇÕES ---
with tab_instrucoes:
    st.markdown("""
    ### 📖 Guia de Utilização do Sistema
    1. **Escolha do Modo de Entrada:** No menu lateral esquerdo, selecione "Fazer Upload" ou "Usar Exemplo".
    2. **Envio do Arquivo:** Caso opte pelo upload, use uma foto nítida focada em uma única folha.
    3. **Ajuste de Filtros:** Modifique o *Limiar de Confiança Mínimo* para omitir resultados muito incertos.
    4. **Análise:** Veja as predições geradas em tempo real na aba **Detector**.
    """)
