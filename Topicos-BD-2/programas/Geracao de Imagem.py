import streamlit as st
from pathlib import Path
import requests
from PIL import Image
import io
import time

# Obtém o diretório raiz do projeto (onde está o app.py)
current_dir = Path(__file__).parent if "__file__" in locals() else Path.cwd()
project_root = current_dir.parent  # Sobe um nível para a pasta raiz

# Constrói caminhos absolutos para os arquivos
css_path = project_root / "styles" / "styles.css"

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
load_css(css_path)

st.title("🎨 Geração de Imagens")

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

def remove_watermark(image):
    """Remove automaticamente a parte inferior da imagem (marca d'água)"""
    width, height = image.size
    # Remove os últimos 8% da imagem onde geralmente fica a marca d'água
    crop_height = int(height * 0.92)
    cropped_image = image.crop((0, 0, width, crop_height))
    return cropped_image

def generate_image(prompt):
    """Gera imagem usando apenas Pollinations"""
    try:
        # URL do Pollinations
        url = "https://image.pollinations.ai/prompt/"
        encoded_prompt = prompt.replace(" ", "%20")
        full_url = f"{url}{encoded_prompt}?width=512&height=512&nofilter=true"
        
        response = requests.get(full_url, timeout=60)
        
        if response.status_code == 200:
            image = Image.open(io.BytesIO(response.content))
            
            # Verifica se a imagem é válida
            if image.size[0] > 50 and image.size[1] > 50:
                # Remove marca d'água automaticamente
                clean_image = remove_watermark(image)
                return clean_image
        
        return None
        
    except Exception as e:
        st.warning(f"Erro na geração: {str(e)[:50]}...")
        return None

# Interface
prompt = st.text_area(
    "Descreva sua imagem:",
    "gato laranja com traje espacial cinza no espaço com estrelas e planetas",
    height=80
)

if st.button("🚀 Gerar Imagem", type="primary"):
    if not prompt.strip():
        st.warning("⚠️ Digite uma descrição!")
    else:
        with st.spinner("🔄 Gerando imagem..."):
            image = generate_image(prompt)
            
            if image:
                st.success("✅ Imagem gerada com sucesso!")
                st.image(image, use_container_width=True)
                
                # Download
                buf = io.BytesIO()
                image.save(buf, format="PNG", optimize=True)
                st.download_button(
                    "💾 Baixar Imagem",
                    buf.getvalue(),
                    f"imagem_{int(time.time())}.png",
                    "image/png"
                )
            else:
                st.error("""
                ❌ Não foi possível gerar a imagem no momento.
                
                **Soluções:**
                - Tente novamente em 1-2 minutos
                - Use uma descrição mais simples
                - Verifique sua conexão com internet
                """)
