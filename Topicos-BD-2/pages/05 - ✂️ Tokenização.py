import streamlit as st

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