"""
python -m venv venv
source venv/bin/activate      # Linux/Mac
venv\Scripts\activate         # Windows
pip install -r requirements.txt
streamlit run app.py
"""

import streamlit as st
import torch
import torchvision.transforms as T
from PIL import Image
import os
import tempfile
import numpy as np
from super_image.edsr.model import EdsrModel

st.html(
    """
    <style>
    h1 {
        font-size: 32px !important;
    }
    </style>
    """
)


device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ------------------- Carregadores de modelos -------------------
def load_edsr():
    model = EdsrModel.from_pretrained('eugenesiow/edsr-base', scale=4)
    model = model.to(device).eval()
    return model

def load_msrresnet():
    # Força recarregamento do repositório
    model = torch.hub.load(
        'xinntao/ESRGAN',
        'msrresnet',
        pretrained=True,
        force_reload=True
    )
    return model.to(device).eval()

def load_esrgan():
    model = torch.hub.load(
        'xinntao/ESRGAN',
        'esrgan',
        pretrained=True,
        force_reload=True
    )
    return model.to(device).eval()

MODELS = {
    "EDSR": {"loader": load_edsr, "desc": "Fidelidade científica/médica."},
    "MSRResNet": {"loader": load_msrresnet, "desc": "Bom equilíbrio."},
    "ESRGAN": {"loader": load_esrgan, "desc": "Texturas realistas."}
}

# ------------------- Interface Streamlit -------------------
st.set_page_config(page_title="Super‑Resolução 4x", layout="centered")
st.title("🖼️ Super‑Resolução de Imagens (4x)")
st.markdown("Selecione o modelo, faça upload e clique em **Ampliar**.")

modelo = st.selectbox("Escolha o modelo:", list(MODELS.keys()))
st.caption(MODELS[modelo]["desc"])

img_file = st.file_uploader("Carregue uma imagem (JPG, PNG, WEBP):",
                            type=["jpg", "jpeg", "png", "webp"])

if img_file is not None:
    img = Image.open(img_file).convert("RGB")
    st.image(img, caption="Original (baixa resolução)", use_container_width=True)

    if st.button("🚀 Ampliar"):
        with st.spinner("Carregando modelo e processando..."):
            @st.cache_resource
            def get_model(name):
                return MODELS[name]["loader"]()

            model = get_model(modelo)

            # Todos os modelos usam tensores (EDSR, MSRResNet, ESRGAN)
            transform = T.ToTensor()
            img_tensor = transform(img).unsqueeze(0).to(device)

            with torch.no_grad():
                out_tensor = model(img_tensor)

            out_tensor = out_tensor.squeeze(0).clamp(0, 1).cpu()
            img_hr = T.ToPILImage()(out_tensor)

            st.image(img_hr, caption="Ampliada (4x)", use_container_width=True)

            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                img_hr.save(tmp.name)
                with open(tmp.name, "rb") as f:
                    st.download_button(
                        label="📥 Baixar",
                        data=f,
                        file_name=f"highres_{os.path.basename(img_file.name)}",
                        mime="image/png"
                    )
                os.unlink(tmp.name)

st.caption("EDSR (super-image) | MSRResNet / ESRGAN (torch.hub)")
