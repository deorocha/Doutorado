# model_loader_corrigido.py - Classe simplificada

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
import os
import logging
from pathlib import Path

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Definir caminhos raiz
PROJECT_ROOT = Path(__file__).parent
FILES_MODEL = PROJECT_ROOT / "fine_tuned_model"
FILES_JSON = PROJECT_ROOT / "json_files"

class LLMModelLoader:
    """Classe simplificada para carregar modelos"""
    
    def __init__(self, model_path: str = None):
        # Usar caminho padrão se não especificado
        if model_path is None:
            self.model_path = FILES_MODEL
        else:
            self.model_path = Path(model_path)
        
        # Garantir que é um Path object
        self.model_path = Path(self.model_path)
        
        self.model = None
        self.tokenizer = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
    def load_model(self) -> bool:
        """Carrega o modelo e tokenizer"""
        try:
            # Verificar se o caminho existe
            if not self.model_path.exists():
                logger.error(f"Diretório não encontrado: {self.model_path}")
                logger.info(f"Caminho absoluto: {self.model_path.absolute()}")
                logger.info(f"Caminho padrão: {FILES_MODEL.absolute()}")
                return False
            
            logger.info(f"Carregando modelo de: {self.model_path.absolute()}")
            
            # Carregar tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                str(self.model_path),
                local_files_only=True
            )
            
            # Configurar token de padding se necessário
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # Carregar modelo
            self.model = AutoModelForCausalLM.from_pretrained(
                str(self.model_path),
                local_files_only=True
            )
            
            # Mover para o dispositivo
            self.model.to(self.device)
            self.model.eval()  # Modo de avaliação
            
            logger.info(f"✅ Modelo carregado com sucesso! (Device: {self.device})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao carregar modelo: {e}")
            return False
    
    def generate(self, prompt: str, max_length: int = 150, 
                temperature: float = 0.8, top_p: float = 0.9, 
                repetition_penalty: float = 1.2) -> str:
        """Gera texto a partir de um prompt"""
        try:
            if self.model is None or self.tokenizer is None:
                raise ValueError("Modelo não carregado")
            
            # Tokenizar o prompt
            inputs = self.tokenizer.encode(prompt, return_tensors="pt").to(self.device)
            
            # Configurar parâmetros de geração
            generation_config = {
                "max_new_tokens": max_length,
                "temperature": temperature,
                "top_p": top_p,
                "do_sample": True,
                "num_return_sequences": 1,
                "pad_token_id": self.tokenizer.pad_token_id,
                "eos_token_id": self.tokenizer.eos_token_id,
                "repetition_penalty": repetition_penalty,
                "no_repeat_ngram_size": 3,
            }
            
            # Gerar texto
            with torch.no_grad():
                outputs = self.model.generate(inputs, **generation_config)
            
            # Decodificar o texto gerado
            generated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # Limpar texto
            generated_text = generated_text.replace("[INICIO]", "").replace("[FIM]", "")
            generated_text = ' '.join(generated_text.split())
            
            # Garantir que termina com pontuação
            if generated_text and generated_text[-1] not in ['.', '!', '?']:
                generated_text += '.'
            
            return generated_text.strip()
            
        except Exception as e:
            logger.error(f"Erro na geração: {e}")
            return f"Erro na geração: {str(e)}"
    
    def get_vocab_size(self):
        """Retorna o tamanho do vocabulário"""
        if self.tokenizer:
            return len(self.tokenizer)
        return None
    
    def get_model_info(self):
        """Retorna informações sobre o modelo carregado"""
        if self.model is None:
            return None
        
        info = {
            "model_path": str(self.model_path),
            "device": str(self.device),
            "vocab_size": self.get_vocab_size(),
            "model_type": type(self.model).__name__,
        }
        
        # Adicionar informações do modelo se disponível
        try:
            config = self.model.config
            info.update({
                "hidden_size": getattr(config, "hidden_size", None),
                "num_layers": getattr(config, "num_hidden_layers", None),
                "num_heads": getattr(config, "num_attention_heads", None),
            })
        except:
            pass
        
        return info
