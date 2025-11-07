# mews_chatbot.py
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from mews_model import load_model
from pathlib import Path

class MEWSChatbot:
    def __init__(self):
        self.model = None
        self.embeddings = None
        self.data = []
        self.text_to_info = {}
        self.similarity_threshold = 0.4
        
    def load_model(self, model_path=None):
        """Carrega o modelo treinado"""
        if model_path is None:
            model_path = Path(__file__).parent / "models" / "mews_model.pkl"
        
        try:
            if model_path.exists():
                loaded_model = load_model(model_path)
                self.model = loaded_model.model
                self.embeddings = loaded_model.embeddings
                self.data = loaded_model.data
                self.text_to_info = loaded_model.text_to_info
                return True
            else:
                print(f"❌ Arquivo do modelo não encontrado: {model_path}")
                return False
        except Exception as e:
            print(f"❌ Erro ao carregar modelo: {e}")
            return False
    
    def find_best_match(self, query):
        """Encontra o melhor procedimento correspondente à pergunta"""
        if not self.model or self.embeddings is None or len(self.embeddings) == 0:
            return None
        
        try:
            # Gera embedding da consulta
            query_embedding = self.model.encode([query], convert_to_tensor=False)
            
            # Calcula similaridade
            similarities = cosine_similarity(query_embedding, self.embeddings)[0]
            
            # Encontra o índice do melhor match
            best_match_idx = np.argmax(similarities)
            best_similarity = similarities[best_match_idx]
            
            # Retorna apenas se estiver acima do threshold
            if best_similarity > self.similarity_threshold:
                info = self.text_to_info.get(best_match_idx, {})
                return {
                    **info,
                    "similarity": float(best_similarity)
                }
            else:
                return None
                
        except Exception as e:
            print(f"❌ Erro na busca: {e}")
            return None
    
    def format_detailed_response(self, result):
        """Formata a resposta no formato especificado"""
        if not result:
            return "❌ **Este assunto não faz parte da minha base de dados**"
        
        motivos = result.get('motivos', {})
        response = ""
        
        # Fundamento Fisiológico
        if motivos.get('fundamento'):
            response += f"**Fundamento Fisiológico:** {motivos['fundamento']}\n\n"
        
        # Riscos da Omissão
        if motivos.get('riscos'):
            response += f"**Riscos da Omissão:** {motivos['riscos']}\n\n"
        
        # Evidências Clínicas
        if motivos.get('evidencias'):
            response += f"**Evidências Clínicas:** {motivos['evidencias']}\n\n"
        
        # Impacto no Paciente
        if motivos.get('impacto'):
            response += f"**Impacto no Paciente:** {motivos['impacto']}\n\n"
        
        # Se não encontrou motivos específicos, retorna informações básicas
        if not response:
            response = f"**Procedimento:** {result.get('procedimento', '')}\n"
            response += f"**Faixa MEWS:** {result.get('faixa', '')}\n"
            response += f"**Responsável:** {result.get('ator', '')}\n"
            response += f"**Conduta:** {result.get('conduta', '')}\n\n"
            response += "ℹ️ *Informações detalhadas não disponíveis para este procedimento*"
        
        return response
    
    def get_answer(self, question):
        """Busca e formata a resposta para uma pergunta"""
        best_match = self.find_best_match(question)
        
        if best_match:
            return self.format_detailed_response(best_match)
        else:
            return "❌ **Este assunto não faz parte da minha base de dados**"
    
    def set_similarity_threshold(self, threshold):
        """Define o limiar de similaridade"""
        self.similarity_threshold = threshold
    
    def get_model_info(self):
        """Retorna informações sobre o modelo carregado"""
        if self.model:
            return {
                "documentos_carregados": len(self.data),
                "threshold_similaridade": self.similarity_threshold,
                "modelo_carregado": True
            }
        else:
            return {
                "documentos_carregados": 0,
                "threshold_similaridade": self.similarity_threshold,
                "modelo_carregado": False
            }
