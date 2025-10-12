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

st.title("Análise de Similaridade")

st.write("""
## Análise de Similaridade

Técnica que mede o quão similares são dois textos ou palavras.

### Métodos:
- **Similaridade semântica**: Significado similar
- **Similaridade léxica**: Palavras similares
- **Embeddings**: Representações vetoriais de texto
- **Transformers**: Modelos de linguagem contextual

### Aplicações:
- Sistemas de recomendação
- Detecção de plágio
- Agrupamento de documentos
- Busca semântica
""")