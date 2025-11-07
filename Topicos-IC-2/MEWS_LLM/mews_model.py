# mews_model.py
import json
import numpy as np
from sentence_transformers import SentenceTransformer
import pickle

class MEWSModel:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.data = []
        self.embeddings = None
        self.text_to_info = {}
    
    def load_and_preprocess_data(self, json_data):
        """Extrai e processa todo o conteúdo do JSON"""
        documents = []
        
        for faixa in json_data.get("faixas_mews", []):
            for ator in faixa.get("atores", []):
                for conduta in ator.get("condutas", []):
                    for procedimento in conduta.get("procedimentos", []):
                        # Texto principal do procedimento
                        texto_procedimento = procedimento.get("procedimento", "")
                        
                        # Adiciona motivos
                        motivos = procedimento.get("motivos", {})
                        texto_motivos = " ".join([f"{k}: {v}" for k, v in motivos.items() if v])
                        
                        # Adiciona ações se existirem
                        texto_acoes = ""
                        for acao in procedimento.get("acoes", []):
                            if isinstance(acao, dict):
                                texto_acao = acao.get("acao", "")
                                motivos_acao = acao.get("motivos", {})
                                texto_motivos_acao = " ".join([f"{k}: {v}" for k, v in motivos_acao.items() if v])
                                texto_acoes += f" {texto_acao} {texto_motivos_acao}"
                        
                        # Texto completo
                        texto_completo = f"""
                        Procedimento: {texto_procedimento}
                        Faixa MEWS: {faixa.get('nome', '')}
                        Ator Responsável: {ator.get('ator', '')}
                        Conduta: {conduta.get('conduta', '')}
                        Motivos: {texto_motivos}
                        Ações: {texto_acoes}
                        """
                        
                        # Remove espaços extras e quebras desnecessárias
                        texto_completo = ' '.join(texto_completo.split())
                        
                        # Armazena informações
                        doc_id = len(self.data)
                        self.data.append(texto_completo)
                        self.text_to_info[doc_id] = {
                            "procedimento": texto_procedimento,
                            "motivos": motivos,
                            "faixa": faixa.get("nome", ""),
                            "ator": ator.get("ator", ""),
                            "conduta": conduta.get("conduta", ""),
                            "acoes": procedimento.get("acoes", [])
                        }
        
        return self.data
    
    def train(self, json_data):
        """Treina o modelo criando embeddings"""
        print("Carregando e processando dados...")
        documents = self.load_and_preprocess_data(json_data)
        
        if not documents:
            raise ValueError("Nenhum documento foi processado do JSON")
        
        print("Criando embeddings...")
        self.embeddings = self.model.encode(documents, convert_to_tensor=False)
        
        print(f"✅ Modelo treinado com {len(documents)} documentos")
        return self

def save_model(model, model_path):
    """Salva o modelo treinado"""
    model_data = {
        'embeddings': model.embeddings,
        'data': model.data,
        'text_to_info': model.text_to_info
    }
    
    with open(model_path, 'wb') as f:
        pickle.dump(model_data, f)
    
    # Salva o modelo do SentenceTransformer separadamente
    transformer_path = model_path.parent / (model_path.name + "_transformer")
    model.model.save(str(transformer_path))
    
    print(f"✅ Modelo salvo em: {model_path}")
    print(f"✅ Transformer salvo em: {transformer_path}")

def load_model(model_path):
    """Carrega o modelo salvo"""
    # Carrega o modelo SentenceTransformer
    transformer_path = model_path.parent / (model_path.name + "_transformer")
    transformer_model = SentenceTransformer(str(transformer_path))
    
    # Carrega os dados
    with open(model_path, 'rb') as f:
        model_data = pickle.load(f)
    
    # Recria o objeto
    mews_model = MEWSModel()
    mews_model.model = transformer_model
    mews_model.embeddings = model_data['embeddings']
    mews_model.data = model_data['data']
    mews_model.text_to_info = model_data['text_to_info']
    
    print(f"✅ Modelo carregado: {len(mews_model.data)} documentos")
    return mews_model

