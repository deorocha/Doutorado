# model_loader.py - Classe simplificada para carregar modelos leves

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
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
    """Classe simplificada para carregar modelos leves"""
    
    def __init__(self, model_path: str = None):
        # Usar caminho padrão se não especificado
        if model_path is None:
            self.model_path = FILES_MODEL
        else:
            self.model_path = Path(model_path)
        
        # Garantir que é um Path object
        self.model_path = Path(self.model_path)
        
        # Modelo leve padrão (GPT-2 pequeno em português ou similar)
        self.DEFAULT_LIGHT_MODEL = "pierreguillou/gpt2-small-portuguese"  # Modelo leve em português
        # Alternativas leves:
        # - "pierreguillou/gpt2-small-portuguese" (124M parâmetros)
        # - "neuralmind/bert-base-portuguese-cased" (110M parâmetros) - para tarefas específicas
        # - "microsoft/DialoGPT-small" (117M parâmetros)
        
        self.model = None
        self.tokenizer = None
        self.generator = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
    def load_model(self, use_local: bool = True) -> bool:
        """Carrega o modelo e tokenizer - modelo leve por padrão"""
        try:
            # Se não há modelo local ou use_local=False, usa modelo leve online
            if not use_local or not self.model_path.exists():
                logger.info(f"Usando modelo leve online: {self.DEFAULT_LIGHT_MODEL}")
                return self._load_online_model()
            
            logger.info(f"Tentando carregar modelo local de: {self.model_path.absolute()}")
            
            # Tentar carregar modelo local
            try:
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
                
                logger.info(f"✅ Modelo local carregado com sucesso! (Device: {self.device})")
                return True
                
            except Exception as e:
                logger.warning(f"Não foi possível carregar modelo local: {e}")
                logger.info("Usando modelo leve online...")
                return self._load_online_model()
            
        except Exception as e:
            logger.error(f"❌ Erro ao carregar modelo: {e}")
            return False
    
    def _load_online_model(self) -> bool:
        """Carrega um modelo leve online"""
        try:
            logger.info(f"Carregando modelo leve: {self.DEFAULT_LIGHT_MODEL}")
            
            # Carregar tokenizer e modelo
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.DEFAULT_LIGHT_MODEL
            )
            
            # Configurar token de padding
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # Carregar modelo leve
            self.model = AutoModelForCausalLM.from_pretrained(
                self.DEFAULT_LIGHT_MODEL,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
            )
            
            # Mover para o dispositivo
            self.model.to(self.device)
            self.model.eval()
            
            # Criar pipeline para geração mais simples (opcional)
            self.generator = pipeline(
                "text-generation",
                model=self.model,
                tokenizer=self.tokenizer,
                device=0 if torch.cuda.is_available() else -1
            )
            
            logger.info(f"✅ Modelo leve carregado com sucesso! (Device: {self.device})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao carregar modelo online: {e}")
            return False
    
    def generate(self, prompt: str, max_length: int = 150, 
                temperature: float = 0.8, top_p: float = 0.9, 
                repetition_penalty: float = 1.2) -> str:
        """Gera texto a partir de um prompt"""
        try:
            if self.model is None or self.tokenizer is None:
                raise ValueError("Modelo não carregado")
            
            # Usar pipeline se disponível (mais simples)
            if self.generator is not None:
                result = self.generator(
                    prompt,
                    max_new_tokens=max_length,
                    temperature=temperature,
                    top_p=top_p,
                    repetition_penalty=repetition_penalty,
                    do_sample=True,
                    num_return_sequences=1
                )
                generated_text = result[0]['generated_text']
            else:
                # Método manual
                inputs = self.tokenizer.encode(prompt, return_tensors="pt").to(self.device)
                
                generation_config = {
                    "max_new_tokens": max_length,
                    "temperature": temperature,
                    "top_p": top_p,
                    "do_sample": True,
                    "num_return_sequences": 1,
                    "pad_token_id": self.tokenizer.pad_token_id,
                    "eos_token_id": self.tokenizer.eos_token_id,
                    "repetition_penalty": repetition_penalty,
                }
                
                with torch.no_grad():
                    outputs = self.model.generate(inputs, **generation_config)
                
                generated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # Limpar texto
            generated_text = ' '.join(generated_text.split())
            
            # Se o texto for muito longo, cortar aproximadamente no número de palavras desejado
            words = generated_text.split()
            if len(words) > max_length * 1.5:  # max_length está em tokens, ajustar
                generated_text = ' '.join(words[:int(max_length * 1.5)])
            
            # Garantir que termina com pontuação
            if generated_text and generated_text[-1] not in ['.', '!', '?']:
                generated_text += '.'
            
            return generated_text.strip()
            
        except Exception as e:
            logger.error(f"Erro na geração: {e}")
            # Retornar texto padrão em caso de erro
            return f"{prompt}... [Texto gerado por modelo leve de linguagem. O sistema está funcionando, mas a geração encontrou um erro técnico: {str(e)[:50]}]"
    
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
            "model_type": "Modelo leve online" if not self.model_path.exists() else "Modelo local",
            "model_name": self.DEFAULT_LIGHT_MODEL if not self.model_path.exists() else str(self.model_path),
            "device": str(self.device),
            "vocab_size": self.get_vocab_size(),
        }
        
        # Adicionar informações do modelo se disponível
        try:
            config = self.model.config
            info.update({
                "hidden_size": getattr(config, "hidden_size", None),
                "num_layers": getattr(config, "num_hidden_layers", None),
                "num_heads": getattr(config, "num_attention_heads", None),
                "model_type": getattr(config, "model_type", None),
            })
        except:
            pass
        
        return info
    
    def is_light_model(self):
        """Verifica se está usando o modelo leve"""
        return not self.model_path.exists()
