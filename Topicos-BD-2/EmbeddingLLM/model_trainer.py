# model_trainer.py

import os
import glob
import pickle
import numpy as np
import pandas as pd
from pathlib import Path
from gensim.models.doc2vec import Doc2Vec, TaggedDocument
from gensim.utils import simple_preprocess
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import sent_tokenize
import PyPDF2

class Doc2VecModelManager:
    """Gerencia treinamento e inferência de modelos Doc2Vec"""
    
    def __init__(self, pdf_folder="./files_pdf"):
        self.pdf_folder = pdf_folder
        self.models_cache = {}
        
        # Baixar recursos NLTK
        self._download_nltk_resources()
    
    def _download_nltk_resources(self):
        """Baixa recursos necessários do NLTK"""
        try:
            nltk.download('punkt', quiet=True)
            nltk.download('stopwords', quiet=True)
        except:
            pass
    
    def list_pdf_files(self):
        """Lista todos os arquivos PDF na pasta especificada"""
        if not os.path.exists(self.pdf_folder):
            os.makedirs(self.pdf_folder, exist_ok=True)
            return []
        
        pdf_files = glob.glob(os.path.join(self.pdf_folder, "*.pdf"))
        return sorted(pdf_files)
    
    def extract_text_from_pdf(self, pdf_path):
        """Extrai texto de um arquivo PDF"""
        text = ""
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    text += page.extract_text()
            return text.strip()
        except Exception as e:
            print(f"Erro ao extrair texto do PDF {pdf_path}: {e}")
            return None
    
    def preprocess_text(self, text, remove_stopwords=True, language='portuguese'):
        """Pré-processa o texto: tokenização e limpeza"""
        if not text:
            return []
        
        try:
            sentences = sent_tokenize(text, language='portuguese')
        except:
            sentences = sent_tokenize(text)
        
        try:
            if language == 'portuguese':
                stop_words = set(stopwords.words('portuguese'))
            else:
                stop_words = set(stopwords.words('english'))
        except:
            stop_words = set()
        
        processed_sentences = []
        
        for sentence in sentences:
            tokens = simple_preprocess(sentence, deacc=True, min_len=2)
            
            if remove_stopwords and stop_words:
                tokens = [token for token in tokens if token not in stop_words]
            
            if tokens:
                processed_sentences.append(tokens)
        
        return processed_sentences
    
    def create_tagged_documents(self, sentences, doc_id="document"):
        """Cria documentos taggeados para o Doc2Vec"""
        tagged_docs = []
        
        for i, sentence_tokens in enumerate(sentences):
            if sentence_tokens:
                tag = f"{doc_id}_para_{i}"
                tagged_docs.append(TaggedDocument(sentence_tokens, [tag]))
        
        all_tokens = [token for sentence in sentences for token in sentence]
        if all_tokens:
            tagged_docs.append(TaggedDocument(all_tokens, [f"{doc_id}_full"]))
        
        return tagged_docs
    
    def train_model_for_document(self, pdf_path, vector_size=100, window=5, 
                                 min_count=2, epochs=40, model_name=None):
        """Treina um modelo Doc2Vec para um documento específico"""
        if model_name is None:
            model_name = f"model_{Path(pdf_path).stem}"
        
        # Extrair e pré-processar texto
        text = self.extract_text_from_pdf(pdf_path)
        if not text:
            return None
        
        processed_sentences = self.preprocess_text(text)
        tagged_docs = self.create_tagged_documents(processed_sentences, "base_document")
        
        # Treinar modelo
        model = Doc2Vec(
            vector_size=vector_size,
            window=window,
            min_count=min_count,
            workers=4,
            dm=1,
            epochs=epochs
        )
        
        model.build_vocab(tagged_docs)
        model.train(
            tagged_docs,
            total_examples=model.corpus_count,
            epochs=model.epochs
        )
        
        # Cache do modelo
        self.models_cache[model_name] = model
        
        return model
    
    def infer_document_embedding(self, model, text, remove_stopwords=True):
        """Infere embedding para um novo documento"""
        processed_sentences = self.preprocess_text(text, remove_stopwords)
        
        if not processed_sentences:
            return None
        
        all_tokens = [token for sentence in processed_sentences for token in sentence]
        
        if not all_tokens:
            return None
        
        vector = model.infer_vector(all_tokens, epochs=50)
        return vector
    
    def save_model(self, model, filename):
        """Salva modelo em arquivo"""
        model.save(filename)
    
    def load_model(self, filename):
        """Carrega modelo de arquivo"""
        return Doc2Vec.load(filename)
    
    def calculate_document_stats(self, pdf_path):
        """Calcula estatísticas de um documento"""
        text = self.extract_text_from_pdf(pdf_path)
        if not text:
            return None
        
        sentences = sent_tokenize(text, language='portuguese')
        
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                num_pages = len(pdf_reader.pages)
        except:
            num_pages = 0
        
        return {
            'text': text,
            'num_sentences': len(sentences),
            'text_length': len(text),
            'num_pages': num_pages
        }
