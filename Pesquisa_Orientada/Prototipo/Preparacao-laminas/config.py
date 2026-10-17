# config.py

"""
histo_slide_prep/
├── requirements.txt
├── app.py
├── config.py
├── storage.py
├── processing.py
├── qr_utils.py
└── demo.py
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

def image_path(tray: int, pos: int) -> Path:
    return IMAGES_DIR / f"T{tray:02d}-S{pos:02d}.png"

def slide_key(tray: int, pos: int) -> str:
    return f"T{tray:02d}-S{pos:02d}"
