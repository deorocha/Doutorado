import streamlit as st
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
CSS_PATH = PROJECT_ROOT / "styles" / "styles.css"
IMAGES_PATH = PROJECT_ROOT / "images"
conceitos_image_path = IMAGES_PATH / "conceitos_fluxograma.png"

# Carregar CSS externo com codificação correta
def load_css(css_path):
    try:
        with open(css_path, "r", encoding="utf-8") as f:
            css_content = f.read()
            st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.error("Arquivo CSS não encontrado na pasta 'styles/'")
    except Exception as e:
        st.error(f"Erro ao carregar CSS: {e}")
load_css(CSS_PATH)

st.title("📚 Conceitos sobre LLM")

st.write("""
### 1. 🤖 Linguagem (Language)
- **Conceito:** Capacidade humana inata de usar sistemas complexos de comunicação
- **Características:** Abstrata, universal, base de todas as línguas
- **No Contexto LLM:** Padrões profundos que os modelos imitam

### 2. 🗣️ Língua (Língua Natural)
- **Conceito:** Realização concreta da linguagem por uma comunidade
- **Exemplos:** Português, Inglês, Mandarim
- **No Contexto LLM:** Objeto específico de treinamento

### 3. 📚 Corpus (plural: Corpora)
- **Conceito:** Conjunto estruturado de textos representativos
- **Características:** Representativo, balanceado, frequentemente anotado
- **Exemplos:** Wikipedia, BrWaC, The Pile

### 4. ⚡ PLN - Processamento de Linguagem Natural
- **Conceito:** Campo da IA que une computação e linguística
- **Objetivo:** Máquinas entenderem e manipularem linguagem humana
- **Abreviação:** NLP (Natural Language Processing)

### 5. 🧠 NLU - Compreensão de Linguagem Natural
- **Conceito:** Foco em **entender** significado e intenção
- **Tarefas:** Análise de sentimentos, NER, resposta a perguntas
- **Abreviação:** Natural Language Understanding

### 6. ✍️ NLG - Geração de Linguagem Natural
- **Conceito:** Foco em **produzir** texto coerente
- **Tarefas:** Tradução, resumo, criação de conteúdo
- **Abreviação:** Natural Language Generation

### 7. 🔤 Token
- **Conceito:** Unidade básica de processamento do LLM
- **Exemplo:** "inacreditável" → ["in", "acredit", "ável"]
- **Função:** Representação granular do texto

### 8. 🧮 Embedding (Vetor de Palavras)
- **Conceito:** Representação numérica em espaço multidimensional
- **Analogia:** "GPS semântico" para palavras
- **Exemplo:** Palavras similares têm vetores próximos

### 9. 🏗️ Transformer
- **Conceito:** Arquitetura neural revolucionária
- **Inovação:** Mecanismo de atenção
- **Importância:** Base de GPT, BERT, T5

### 10. 🎯 Treinamento
- **Pré-treinamento:** Aprendizado em corpus massivo (não supervisionado)
- **Ajuste Fino:** Especialização para tarefas específicas
- **Custo:** Extremamente alto na fase inicial

### 11. 💬 Prompt e Engenharia de Prompt
- **Prompt:** Texto de entrada que orienta o LLM
- **Engenharia:** Arte de criar prompts eficazes
- **Impacto:** Pequenas mudanças = grandes diferenças

### 12. 👻 Alucinação (Hallucination)
- **Conceito:** Geração de informações incorretas/inventadas
- **Desafio:** Um dos maiores problemas atuais em LLMs
- **Causa:** Modelo "confiante" em informações erradas
""")

try:
    st.image(conceitos_image_path, use_container_width=True)
except Exception as e:
    st.info("Imagem conceitos_fluxograma.png não encontrada")
