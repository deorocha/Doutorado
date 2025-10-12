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
