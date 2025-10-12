import streamlit as st
import spacy
from spacy import displacy

@st.cache_resource
def load_spacy_model(model_name):
    return spacy.load(model_name)

nlp = load_spacy_model("pt_core_news_sm")

# Carregar CSS externo com codificação correta
def load_css():
    try:
        with open("styles/styles.css", "r", encoding="utf-8") as f:
            css_content = f.read()
            st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.error("Arquivo CSS não encontrado na pasta 'styles/'")
    except Exception as e:
        st.error(f"Erro ao carregar CSS: {e}")

load_css()

st.title("Marcação de Classes Gramaticais")

st.write("""
## Marcação de Classes Gramaticais (POS Tagging)

Técnica que atribui etiquetas gramaticais a cada palavra em um texto.

### Categorias comuns:
- **Substantivos** (NN): pessoas, lugares, coisas
- **Verbos** (VB): ações e estados
- **Adjetivos** (JJ): qualidades e características
- **Advérbios** (RB): modificação de verbos, adjetivos

### Aplicações:
- Análise sintática
- Tradução automática
- Correção gramatical
- Análise de estilo literário
""")
