from pathlib import Path
import os
import sys

def get_project_root():
    """Retorna o caminho raiz do projeto funcionando localmente e no Streamlit Cloud"""
    current_dir = Path(__file__).parent if "__file__" in locals() else Path.cwd()
    
    # No Streamlit Cloud, o diretório de trabalho é a raiz do repositório
    if "streamlit" in str(current_dir).lower():
        return current_dir
    else:
        return current_dir

PROJECT_ROOT = get_project_root()

# Caminhos absolutos
CSS_PATH = PROJECT_ROOT / "styles" / "styles.css"
IMAGES_PATH = PROJECT_ROOT / "images"
PROGRAMAS_PATH = PROJECT_ROOT / "programas"
ARQUIVOS_PATH = PROJECT_ROOT / "arquivos"

