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

st.title("Geração de Imagem")

st.write("""
## Geração de Imagem

Técnicas de IA para criar imagens a partir de descrições textuais.

### Modelos comuns:
- **GANs** (Generative Adversarial Networks)
- **VAEs** (Variational Autoencoders)
- **Diffusion Models**: Como DALL-E, Stable Diffusion
- **Transformers**: Modelos baseados em atenção

### Aplicações:
- Arte digital e design
- Publicidade e marketing
- Desenvolvimento de jogos
- Educação e pesquisa
""")