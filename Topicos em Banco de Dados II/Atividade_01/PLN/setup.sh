#!/bin/bash

# Atualizar pip
pip install --upgrade pip

# Instalar pacotes Python (se houver um requirements.txt)
pip install -r requirements.txt

# Download dos modelos do spaCy
python -m spacy download pt_core_news_lg
python -m spacy download pt_core_news_sm

# Download dos corpora do TextBlob
python -m textblob.download_corpora
