import streamlit as st
from pathlib import Path

# Obtém o diretório raiz do projeto (onde está o app.py)
current_dir = Path(__file__).parent if "__file__" in locals() else Path.cwd()
project_root = current_dir.parent  # Sobe um nível para a pasta raiz

# Constrói caminhos absolutos para os arquivos
css_path = project_root / "styles" / "styles.css"

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

st.title("Tokenização")

st.write("""
## Tokenização

Processo de dividir texto em unidades menores chamadas tokens.

### Tipos de tokenização:
- **Tokenização por palavras**: Divide em palavras
- **Tokenização por subpalavras**: BPE, WordPiece
- **Tokenização por caracteres**: Divide em caracteres individuais

### Aplicações:
- Pré-processamento para modelos de NLP
- Análise de frequência de palavras
- Preparação de dados para machine learning
""")
