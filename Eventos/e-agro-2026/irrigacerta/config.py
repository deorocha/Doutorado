import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
DB_PATH = DATA_DIR / "irrigacerta.db"

DATA_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)

# Modo demo: 1 = só cache (offline); 0 = busca dados reais
DEMO_MODE = os.getenv("IRRIGACERTA_DEMO_MODE", "1") == "1"

# Centro do mapa (Bahia / semiárido) — só posição inicial
DEFAULT_CENTER = (-9.40, -40.50)
DEFAULT_ZOOM = 10

# STAC
STAC_URL = "https://earth-search.aws.element84.com/v1"
STAC_COLLECTIONS = ("sentinel-2-c1-l2a", "sentinel-2-l2a")
MAX_NUVEM_DEFAULT = 70
MAX_CENAS_PROCESSAR = 3
DIAS_SATELITE_DEFAULT = 90

# APIs de clima
NASA_POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Rede
HTTP_TIMEOUT = 30

# Parâmetros agronômicos
KC = {
    # originais
    "milho":   {"ini": 0.30, "mid": 1.20, "fim": 0.35, "dur": [30, 40, 30, 25]},
    "tomate":  {"ini": 0.60, "mid": 1.15, "fim": 0.80, "dur": [30, 40, 40, 25]},
    "feijao":  {"ini": 0.40, "mid": 1.15, "fim": 0.35, "dur": [20, 30, 30, 20]},
    "uva":     {"ini": 0.30, "mid": 0.80, "fim": 0.45, "dur": [30, 60, 60, 30]},
    # Brasil: grãos e fibra
    "soja":    {"ini": 0.40, "mid": 1.15, "fim": 0.50, "dur": [25, 35, 50, 20]},
    "algodao": {"ini": 0.35, "mid": 1.15, "fim": 0.70, "dur": [30, 50, 60, 30]},
    "cana":    {"ini": 0.40, "mid": 1.25, "fim": 0.75, "dur": [60, 120, 150, 60]},
    # Brasil: fruticultura irrigada
    "banana":  {"ini": 0.50, "mid": 1.20, "fim": 0.90, "dur": [60, 90, 120, 60]},
    "manga":   {"ini": 0.50, "mid": 0.90, "fim": 0.75, "dur": [60, 90, 90, 60]},
    "melao":   {"ini": 0.50, "mid": 1.05, "fim": 0.75, "dur": [15, 25, 20, 15]},
    "cebola":  {"ini": 0.70, "mid": 1.05, "fim": 0.75, "dur": [15, 25, 40, 20]},
    # café (Kc debatido — validar com mentor ou remover da demo)
    "cafe":    {"ini": 0.90, "mid": 0.95, "fim": 0.95, "dur": [60, 90, 120, 60]},
}

TAW_POR_METRO = {
    "arenoso": 80,
    "franco-arenoso": 110,
    "franco": 150,
    "argiloso": 180,
}

ZR_M = {
    "milho": 0.60, "tomate": 0.40, "feijao": 0.40, "uva": 0.60,
    "soja": 0.50, "algodao": 0.70, "cana": 0.80,
    "banana": 0.60, "manga": 1.00, "melao": 0.40, "cebola": 0.35,
    "cafe": 0.80,
}

DEPLETION_FRACTION = 0.5
RAIN_WAIT_MM = 5.0
