import streamlit as st
import spacy
from spacy import displacy
from pathlib import Path

# Obtém o diretório raiz do projeto (onde está o app.py)
current_dir = Path(__file__).parent if "__file__" in locals() else Path.cwd()
project_root = current_dir.parent  # Sobe um nível para a pasta raiz

# Constrói caminhos absolutos para os arquivos
css_path = project_root / "styles" / "styles.css"

@st.cache_resource
def load_spacy_model():
    try:
        # Tenta carregar o modelo pequeno em português
        return spacy.load("pt_core_news_sm")
    except OSError:
        try:
            # Se falhar, tenta o modelo em inglês
            st.info("Modelo português não disponível. Usando modelo em inglês...")
            return spacy.load("en_core_web_sm")
        except OSError:
            # Último recurso: modelo mínimo
            st.warning("Usando modelo básico do spaCy (funcionalidades limitadas)")
            return spacy.blank("pt")

nlp = load_spacy_model()

# Carregar CSS externo com codificação correta
def load_css():
    try:
        with open(css_path, "r", encoding="utf-8") as f:
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
