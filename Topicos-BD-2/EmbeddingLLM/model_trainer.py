# model_trainer.py - VERSÃO ATUALIZADA

import os
import glob
import numpy as np
import pandas as pd
from pathlib import Path
from gensim.models.doc2vec import Doc2Vec, TaggedDocument
from gensim.utils import simple_preprocess
import nltk
import ssl
import urllib.request
import zipfile
import io
from nltk.corpus import stopwords
from nltk.tokenize import sent_tokenize
import PyPDF2

PROJECT_ROOT = Path(__file__).parent
FILES_PDF = PROJECT_ROOT / "files_pdf"

class Doc2VecModelManager:
    """Gerencia treinamento e inferência de modelos Doc2Vec"""
    
    def __init__(self, pdf_folder=FILES_PDF):
        self.pdf_folder = pdf_folder
        self.models_cache = {}
        
        # Baixar recursos NLTK
        self._download_nltk_resources()
    
    def _download_nltk_resources(self):
        """Baixa recursos necessários do NLTK de forma robusta"""
        try:
            # Desativar verificação SSL se necessário
            try:
                _create_unverified_https_context = ssl._create_unverified_context
            except AttributeError:
                pass
            else:
                ssl._create_default_https_context = _create_unverified_https_context
            
            # Lista de recursos essenciais
            essential_resources = ['punkt', 'stopwords']
            
            # Criar diretório personalizado para NLTK data
            nltk_data_dir = os.path.join(os.getcwd(), 'nltk_data')
            os.makedirs(nltk_data_dir, exist_ok=True)
            nltk.data.path.append(nltk_data_dir)
            
            # Verificar e baixar cada recurso
            for resource in essential_resources:
                try:
                    nltk.data.find(resource)
                    print(f"Resource '{resource}' já disponível")
                except LookupError:
                    print(f"Baixando resource '{resource}'...")
                    nltk.download(resource, quiet=True, raise_on_error=True)
                    
        except Exception as e:
            print(f"Erro no download do NLTK: {e}")
            # Tentar fallback usando dados locais se disponíveis
            try:
                # Configurar caminhos alternativos
                nltk.data.path.append('/usr/share/nltk_data')
                nltk.data.path.append('/usr/local/share/nltk_data')
                nltk.data.path.append('/usr/lib/nltk_data')
                nltk.data.path.append('/usr/local/lib/nltk_data')
                nltk.data.path.append('/opt/nltk_data')
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
                    text += page.extract_text() or ""
            return text.strip()
        except Exception as e:
            print(f"Erro ao extrair texto do PDF {pdf_path}: {e}")
            return None
    
    def preprocess_text(self, text, remove_stopwords=True, language='portuguese'):
        """Pré-processa o texto: tokenização e limpeza com fallback"""
        if not text:
            return []
        
        try:
            # Tentar usar sent_tokenize do NLTK
            try:
                sentences = sent_tokenize(text, language='portuguese')
            except:
                # Fallback para inglês
                sentences = sent_tokenize(text, language='english')
        except Exception as e:
            print(f"Erro no sent_tokenize: {e}")
            # Fallback simples: dividir por pontuação
            import re
            sentences = re.split(r'[.!?]+', text)
            sentences = [s.strip() for s in sentences if s.strip()]
        
        # Obter stopwords
        stop_words = set()
        try:
            if language == 'portuguese':
                stop_words = set(stopwords.words('portuguese'))
            else:
                stop_words = set(stopwords.words('english'))
        except:
            # Lista básica de stopwords em português como fallback
            stop_words = {
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
            print(f"Texto não extraído de {pdf_path}")
            return None
        
        processed_sentences = self.preprocess_text(text)
        if not processed_sentences:
            print(f"Nenhuma sentença processada de {pdf_path}")
            return None
        
        tagged_docs = self.create_tagged_documents(processed_sentences, "base_document")
        
        if not tagged_docs:
            print(f"Nenhum documento taggeado criado de {pdf_path}")
            return None
        
        # Treinar modelo
        try:
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
        except Exception as e:
            print(f"Erro ao treinar modelo: {e}")
            return None
    
    def infer_document_embedding(self, model, text, remove_stopwords=True):
        """Infere embedding para um novo documento"""
        processed_sentences = self.preprocess_text(text, remove_stopwords)
        
        if not processed_sentences:
            return None
        
        all_tokens = [token for sentence in processed_sentences for token in sentence]
        
        if not all_tokens:
            return None
        
        try:
            vector = model.infer_vector(all_tokens, epochs=50)
            return vector
        except Exception as e:
            print(f"Erro ao inferir embedding: {e}")
            return None
    
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
        
        # Usar fallback para tokenização de sentenças
        try:
            sentences = sent_tokenize(text, language='portuguese')
        except:
            try:
                sentences = sent_tokenize(text, language='english')
            except:
                import re
                sentences = re.split(r'[.!?]+', text)
                sentences = [s.strip() for s in sentences if s.strip()]
        
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
