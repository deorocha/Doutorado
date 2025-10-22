from pathlib import Path
import os
import streamlit as st

def get_project_root():
    """Retorna o caminho raiz funcionando em qualquer ambiente"""
    try:
        # Tenta várias estratégias para encontrar a raiz
        paths_to_try = [
            Path(__file__).parent,  # Local
            Path.cwd(),             # Streamlit Cloud
            Path.cwd().parent,      # Alternativa
        ]
        
        for path in paths_to_try:
            # Verifica se existe a estrutura de pastas esperada
            if (path / "styles").exists() and (path / "styles" / "styles.css").exists():
                return path
            if (path / "programas").exists():
                return path
        
        # Último recurso: usa o diretório atual
        return Path.cwd()
    
    except Exception as e:
        st.error(f"Erro ao encontrar raiz do projeto: {e}")
        return Path.cwd()

PROJECT_ROOT = get_project_root()

# Caminhos absolutos
CSS_PATH = PROJECT_ROOT / "styles" / "styles.css"
IMAGES_PATH = PROJECT_ROOT / "images"
PROGRAMAS_PATH = PROJECT_ROOT / "programas"
ARQUIVOS_PATH = PROJECT_ROOT / "arquivos"

# Log para debug (aparece apenas no console do Streamlit Cloud)
print(f"PROJECT_ROOT: {PROJECT_ROOT}")
print(f"CSS_PATH: {CSS_PATH}")
print(f"CSS exists: {CSS_PATH.exists()}")
print(f"IMAGES_PATH: {IMAGES_PATH}")
print(f"Images exists: {IMAGES_PATH.exists()}")
