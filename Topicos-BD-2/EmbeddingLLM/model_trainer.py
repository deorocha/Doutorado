# model_trainer.py - VERSÃO OTIMIZADA PARA STREAMLIT CLOUD

import os
import glob
import re
import numpy as np
import pandas as pd
from pathlib import Path
import scipy
import scipy.linalg
from gensim.models.doc2vec import Doc2Vec, TaggedDocument
from gensim.utils import simple_preprocess
import PyPDF2

PROJECT_ROOT = Path(__file__).parent
FILES_PDF = PROJECT_ROOT / "files_pdf"

class Doc2VecModelManager:
    """Gerencia treinamento e inferência de modelos Doc2Vec"""
    
    def __init__(self, pdf_folder=FILES_PDF):
        self.pdf_folder = pdf_folder
        self.models_cache = {}
        self.portuguese_stopwords = self._get_portuguese_stopwords()
    
    def _get_portuguese_stopwords(self):
        """Retorna uma lista de stopwords em português"""
        return {
            'de', 'a', 'o', 'que', 'e', 'do', 'da', 'em', 'um', 'para',
            'com', 'não', 'uma', 'os', 'no', 'se', 'na', 'por', 'mais',
            'as', 'dos', 'como', 'mas', 'ao', 'ele', 'das', 'à', 'seu',
            'sua', 'ou', 'quando', 'muito', 'nos', 'já', 'eu', 'também',
            'só', 'pelo', 'pela', 'até', 'isso', 'ela', 'entre', 'depois',
            'sem', 'mesmo', 'aos', 'seus', 'quem', 'nas', 'me', 'esse',
            'eles', 'você', 'essa', 'num', 'nem', 'suas', 'meu', 'às',
            'minha', 'numa', 'pelos', 'elas', 'qual', 'nós', 'lhe',
            'deles', 'essas', 'esses', 'pelas', 'este', 'dele', 'tu',
            'te', 'vocês', 'vos', 'lhes', 'meus', 'minhas', 'teu',
            'tua', 'teus', 'tuas', 'nosso', 'nossa', 'nossos', 'nossas',
            'dela', 'delas', 'esta', 'estes', 'estas', 'aquele', 'aquela',
            'aqueles', 'aquelas', 'isto', 'aquilo'
        }
    
    def list_pdf_files(self):
        """Lista todos os arquivos PDF na pasta especificada"""
        if not os.path.exists(self.pdf_folder):
            os.makedirs(self.pdf_folder, exist_ok=True)
            return []
        
        pdf_files = glob.glob(os.path.join(self.pdf_folder, "*.pdf"))
        return sorted(pdf_files)
    
    def extract_text_from_pdf(self, pdf_path):
        """Extrai texto de um arquivo PDF"""
        try:
            text = ""
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + " "
            return text.strip()
        except Exception as e:
            print(f"Erro ao extrair texto: {e}")
            return None
    
    def simple_sentence_tokenize(self, text):
        """Tokenização simples de sentenças"""
        if not text:
            return []
        
        # Dividir por pontuação de final de sentença
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        return sentences
    
    def preprocess_text(self, text, remove_stopwords=True):
        """Pré-processa o texto para o Doc2Vec"""
        if not text:
            return []
        
        sentences = self.simple_sentence_tokenize(text)
        processed_sentences = []
        
        for sentence in sentences:
            # Tokenização com gensim
            tokens = simple_preprocess(sentence, deacc=True, min_len=2)
            
            if remove_stopwords and self.portuguese_stopwords:
                tokens = [token for token in tokens if token not in self.portuguese_stopwords]
            
            if tokens:
                processed_sentences.append(tokens)
        
        return processed_sentences
    
    def create_tagged_documents(self, sentences, doc_id="document"):
        """Cria documentos taggeados para o Doc2Vec"""
        tagged_docs = []
        
        for i, sentence_tokens in enumerate(sentences):
            if sentence_tokens:
                tag = f"{doc_id}_sent_{i}"
                tagged_docs.append(TaggedDocument(sentence_tokens, [tag]))
        
        # Documento completo
        all_tokens = [token for sentence in sentences for token in sentence]
        if all_tokens:
            tagged_docs.append(TaggedDocument(all_tokens, [f"{doc_id}_full"]))
        
        return tagged_docs
    
    def train_model_for_document(self, pdf_path, vector_size=100, window=5, 
                                 min_count=2, epochs=40):
        """Treina um modelo Doc2Vec para um documento"""
        try:
            text = self.extract_text_from_pdf(pdf_path)
            if not text:
                print(f"Nenhum texto extraído de {pdf_path}")
                return None
            
            processed_sentences = self.preprocess_text(text)
            if not processed_sentences:
                print(f"Nenhuma sentença processada de {pdf_path}")
                return None
            
            tagged_docs = self.create_tagged_documents(processed_sentences, "doc")
            
            if not tagged_docs:
                print(f"Nenhum documento taggeado criado")
                return None
            
            # Configuração otimizada para documentos pequenos
            model = Doc2Vec(
                vector_size=vector_size,
                window=window,
                min_count=min_count,
                workers=1,  # Reduzido para evitar problemas no Streamlit Cloud
                dm=1,
                epochs=epochs,
                alpha=0.025,
                min_alpha=0.00025,
                seed=42
            )
            
            model.build_vocab(tagged_docs)
            model.train(
                tagged_docs,
                total_examples=model.corpus_count,
                epochs=model.epochs
            )
            
            return model
            
        except Exception as e:
            print(f"Erro ao treinar modelo: {e}")
            return None
    
    def infer_document_embedding(self, model, text):
        """Infere embedding para um novo documento"""
        try:
            processed_sentences = self.preprocess_text(text)
            if not processed_sentences:
                return None
            
            all_tokens = [token for sentence in processed_sentences for token in sentence]
            if not all_tokens:
                return None
            
            vector = model.infer_vector(all_tokens, epochs=30)
            return vector
            
        except Exception as e:
            print(f"Erro ao inferir embedding: {e}")
            return None
    
    def calculate_document_stats(self, pdf_path):
        """Calcula estatísticas de um documento"""
        text = self.extract_text_from_pdf(pdf_path)
        if not text:
            return None
        
        sentences = self.simple_sentence_tokenize(text)
        
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

