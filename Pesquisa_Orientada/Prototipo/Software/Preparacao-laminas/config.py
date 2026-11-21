# config.py

"""Configuração global do app de Preparação de Lâminas.

ESTRUTURA DOS ARQUIVOS
    Preparação de lâminas/
    ├── app.py
    ├── clickable.py          (componente iframe — CSS interno obrigatório)
    ├── config.py
    ├── demo.py
    ├── processing.py
    ├── qr_utils.py
    ├── storage.py
    ├── styles.css            (CSS da página Streamlit)
    ├── toolbar.py            (componente iframe — CSS interno obrigatório)
    ├── requirements.txt
    ├── data/
    │   ├── images/
    │   └── state.json
    └── images/
        └── icons/
            ├── rect.png
            ├── ellipse.png
            ├── freedraw.png
            ├── polygon.png
            ├── magic_wand.png
            └── zoom.png
"""

from pathlib import Path

# Estrutura do scanner
N_TRAYS = 8
SLIDES_PER_TRAY = 16

# Caminhos
DATA_DIR   = Path("data")
IMAGES_DIR = DATA_DIR / "images"
STATE_FILE = DATA_DIR / "state.json"
EXPORT_FILE = DATA_DIR / "scan_plan.json"

IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# Parâmetros padrão de detecção (ajustáveis na UI)
DEFAULT_PARAMS = {
    "sat_threshold": 25,   # saturação mínima para considerar tecido (corado)
    "val_threshold": 230,  # valor máximo p/ considerar "escuro" (contra-luz)
    "canny_low":     50,
    "canny_high":   150,
    "min_area":    2000,   # px²
    "morph_kernel":   7,
    "padding":       20,   # margem em volta da bbox
}

# Cor default dos color pickers (usada em render_manual e render_auto)
DEFAULT_BORDER_COLOR = "#FFFF00"


def image_path(tray: int, pos: int) -> Path:
    return IMAGES_DIR / f"B{tray:02d}-L{pos:02d}.png"


def slide_key(tray: int, pos: int) -> str:
    return f"B{tray:02d}-L{pos:02d}"
