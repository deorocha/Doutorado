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

st.title("Detecção de Limites de Frases")

st.write("""
## Detecção de Limites de Frases

Técnica que identifica onde começam e terminam as frases em um texto.

### Desafios:
- **Abreviações**: "Dr." não deve quebrar a frase
- **Pontuação múltipla**: "!!!" ou "???"
- **Citações**: Frases dentro de aspas
- **Listas**: Itens numerados ou com marcadores

### Aplicações:
- Processamento de documentos longos
- Análise de discursos
- Preparação para outras tarefas de NLP
- Sumarização de texto
""")