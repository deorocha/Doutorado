# model_trainer.py - VERSÃO SEM NLTK, APENAS COM GENSIM

import os
import glob
import re
import numpy as np
import pandas as pd
from pathlib import Path
from gensim.models.doc2vec import Doc2Vec, TaggedDocument
from gensim.utils import simple_preprocess
import PyPDF2

PROJECT_ROOT = Path(__file__).parent
FILES_PDF = PROJECT_ROOT / "files_pdf"

class Doc2VecModelManager:
    """Gerencia treinamento e inferência de modelos Doc2Vec SEM NLTK"""
    
    def __init__(self, pdf_folder=FILES_PDF):
        self.pdf_folder = pdf_folder
        self.models_cache = {}
        self.portuguese_stopwords = self._get_portuguese_stopwords()
    
    def _get_portuguese_stopwords(self):
        """Retorna uma lista de stopwords em português (sem dependência do NLTK)"""
        stopwords = {
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
            'aqueles', 'aquelas', 'isto', 'aquilo',
            # Palavras comuns adicionais
            'ser', 'estar', 'ter', 'haver', 'fazer', 'poder', 'dizer',
            'ir', 'ver', 'vir', 'saber', 'querer', 'ficar', 'dar',
            'passar', 'dever', 'ficar', 'deixar', 'parecer', 'levar',
            'encontrar', 'começar', 'pensar', 'entrar', 'trabalhar',
            'escrever', 'permitir', 'aparecer', 'falar', 'sentir',
            'tornar', 'viver', 'acabar', 'precisar', 'conhecer',
            'considerar', 'abrir', 'ouvir', 'ganhar', 'comprar',
            'tentar', 'mudar', 'oferecer', 'esquecer', 'entender',
            'reconhecer', 'correr', 'procurar', 'receber', 'tratar',
            'ajudar', 'mostrar', 'continuar', 'acreditar', 'servir'
        }
        return stopwords
    
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
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text.strip()
        except Exception as e:
            print(f"Erro ao extrair texto do PDF {pdf_path}: {e}")
            return None
    
    def simple_sentence_tokenize(self, text):
        """Tokenização simples de sentenças sem NLTK"""
        # Dividir por pontuação de final de sentença
        sentences = re.split(r'[.!?]+', text)
        # Limpar espaços em branco
        sentences = [s.strip() for s in sentences if s.strip()]
        return sentences
    
    def preprocess_text(self, text, remove_stopwords=True):
        """Pré-processa o texto para o Doc2Vec"""
        if not text:
            return []
        
        # Tokenização de sentenças simples
        sentences = self.simple_sentence_tokenize(text)
        
        processed_sentences = []
        
        for sentence in sentences:
            # Tokenização com gensim (remove acentos, minúsculas, mínimo 2 chars)
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
                tag = f"{doc_id}_para_{i}"
                tagged_docs.append(TaggedDocument(sentence_tokens, [tag]))
        
        # Adicionar documento completo
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
                dm=1,  # Distributed Memory (PV-DM)
                epochs=epochs,
                alpha=0.025,
                min_alpha=0.00025
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
            print(f"Erro ao treinar modelo Doc2Vec: {e}")
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
            # Inferir vetor com mais épocas para melhor qualidade
            vector = model.infer_vector(all_tokens, epochs=50, alpha=0.025, min_alpha=0.0001)
            return vector
        except Exception as e:
            print(f"Erro ao inferir embedding: {e}")
            return None
    
    def calculate_document_stats(self, pdf_path):
        """Calcula estatísticas de um documento"""
        text = self.extract_text_from_pdf(pdf_path)
        if not text:
            return None
        
        # Tokenizar sentenças
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
    
    def calculate_similarity_between_docs(self, model, text1, text2):
        """Calcula similaridade entre dois textos usando o modelo Doc2Vec"""
        vector1 = self.infer_document_embedding(model, text1)
        vector2 = self.infer_document_embedding(model, text2)
        
        if vector1 is None or vector2 is None:
            return 0.0
        
        # Calcular similaridade cosseno
        from sklearn.metrics.pairwise import cosine_similarity
        similarity = cosine_similarity([vector1], [vector2])[0][0]
        
        # Garantir que a similaridade esteja entre 0 e 1
        return max(0.0, min(1.0, similarity))
