import streamlit as st
from ultralytics import YOLO
from PIL import Image
import pandas as pd
from pathlib import Path

# Replace st.title("My Title") with st.markdown
st.markdown(
    '<h1 style="font-size: 30px;">🍅 Detector de doenças em folhas de tomateiros</h1>', 
    unsafe_allow_html=True
)

# Configurações da página
st.set_page_config(page_title="Detector de doenças em folhas de tomateiros", page_icon="🍅")

# Definir caminhos relativos à raiz do projeto
PROJECT_ROOT = Path(__file__).parent
MODELS_PATH = PROJECT_ROOT / "models"
MODEL_FILE = MODELS_PATH / "best.pt"

# 1. Carregar o modelo treinado
@st.cache_resource
def load_model():
    if not MODEL_FILE.exists():
        st.error(f"Modelo não encontrado em: {MODEL_FILE}")
        st.stop()
    model = YOLO(str(MODEL_FILE))
    return model

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

# 2. Upload da Imagem
uploaded_file = st.file_uploader("Faça o upload de uma foto da folha de tomateiro para identificar possíveis doenças.", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    image = Image.open(uploaded_file)

    col1, col2 = st.columns([1, 1])

    #with col1:
    #    st.image(image, caption='Imagem Carregada', use_container_width=True)

    # 3. Fazer a Predição
    with st.spinner('Analisando imagem...'):
        results = model.predict(image)

        probs = results[0].probs
        names = results[0].names  # {id: nome_ingles}

        # Criar dicionário com nome em português -> probabilidade (%)
        conf_dict_pt = {}
        for i, score in enumerate(probs.data.tolist()):
            nome_ingles = names[i]
            nome_portugues = TRADUCAO.get(nome_ingles, nome_ingles)
            conf_dict_pt[nome_portugues] = score * 100

        # Ordenar do maior para o menor
        sorted_probs = dict(sorted(conf_dict_pt.items(), key=lambda item: item[1], reverse=True))

    with col1:
         top_class = list(sorted_probs.keys())[0]
         top_score = list(sorted_probs.values())[0]

         st.success(f"**Diagnóstico Provável:** {top_class}")
         st.image(image, caption='Imagem Carregada', use_container_width=True)
    
    with col2:
         st.info(f"**Confiança:** #{top_score:.2f}%")

         # Gráfico de barras
         df_probs = pd.DataFrame(list(sorted_probs.items()), columns=['Doença', 'Probabilidade (%)'])
         st.bar_chart(df_probs.set_index('Doença'))

    # Tabela detalhada
    with st.expander("Ver todas as probabilidades"):
        st.table(df_probs)
