# split_icons.py — uso único

import cv2
from pathlib import Path

SRC = Path("images/toolbar_app.png")
OUT = Path("images/icons")
OUT.mkdir(parents=True, exist_ok=True)

# Mapeamento: índice no PNG → arquivo de destino
#   0 rect, 1 ellipse, 2 freedraw, 3 magic_wand, 4 ("T") → ignorado, 5 zoom
CROPS = {
    0: "rect.png",
    1: "ellipse.png",
    2: "freedraw.png",
    3: "magic_wand.png",
    5: "zoom.png",
}

img = cv2.imread(str(SRC))
if img is None:
    raise SystemExit(f"Não foi possível ler {SRC}")

h, w = img.shape[:2]
step = w // 6

for idx, name in CROPS.items():
    x1 = idx * step
    x2 = w if idx == 5 else (idx + 1) * step
    cv2.imwrite(str(OUT / name), img[:, x1:x2])
    print(f"  {name:20s} → {x2 - x1}×{h} px")

print(f"Pronto: {len(CROPS)} ícones em {OUT.resolve()}")
