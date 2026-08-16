"""
[15:13, 06/08/2026] Luciano Rebouças: eu quero um método que receba um input em low resolution e me entregue um output em high resolution
[15:13, 06/08/2026] Luciano Rebouças: Você pode usar o modelo EDSR ou MSRResNet para dados que exigem fidelidade médica/científica,
                                      ou ESRGAN para fotos e texturas realistas.

Dependências:
    pip install super-image
    pip install transformers
"""

import torch
import torchvision.transforms as T
from PIL import Image
from super_image import EdsrModel
from pathlib import Path

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# Carrega o EDSR (foco em fidelidade)
model = EdsrModel.from_pretrained('eugenesiow/edsr-base', scale=4)
model = model.to(device)
model.eval()

def processar_patch_biopsia(caminho_entrada):
    img = Image.open(caminho_entrada).convert('RGB')
    img_tensor = T.ToTensor()(img).unsqueeze(0).to(device)
    with torch.no_grad():
        output = model(img_tensor)
    output = output.squeeze(0).clamp(0, 1).cpu()
    return T.ToPILImage()(output)

if __name__ == "__main__":
    entrada = Path('images/0_Image_2746.jpg')  # ajuste o caminho
    img_hr = processar_patch_biopsia(str(entrada))
    saida = entrada.parent / f"{entrada.stem}_EDSR_x4.jpg"
    img_hr.save(saida)
    print(f"Salvo em: {saida}")

"""
Critério			EDSR (super-image)			Real‑ESRGAN
Fidelidade científica/médica	Excelente (preserva detalhes finos)	Pode inventar texturas (alucinações)
Aparência visual (fotos)	Pode parecer suave demais		Muito realista e nítido
Instalação			Simples, poucas dependências		Mais pesado, sujeito a conflitos
Desempenho			Rápido					Moderado (pesado)
"""
