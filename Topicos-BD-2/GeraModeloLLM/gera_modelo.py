import os
import string
import random
import pdfplumber
from collections import Counter, defaultdict
import math
import re
import pickle
import json
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent
MODELS_PATH = PROJECT_ROOT / "saved_models"
PDF_PATH = PROJECT_ROOT / "pdf_path"

class SavableTextGenerator:
    def __init__(self, model_name="text_generator_model"):
        self.unigram_probs = {}
        self.bigram_cond = {}
        self.trigram_cond = {}
        self.vocab = set()
        self.model_name = model_name
        self.training_date = None
        self.corpus_stats = {}
        
    def extract_text_from_pdfs(self, pdf_folder):
        """Extrai texto dos PDFs"""
        texts = []
        for filename in sorted(os.listdir(pdf_folder)):
            if filename.endswith('.pdf'):
                path = os.path.join(pdf_folder, filename)
                try:
                    with pdfplumber.open(path) as pdf:
                        text = ''
                        for page in pdf.pages:
                            page_text = page.extract_text()
                            if page_text:
                                text += page_text + ' '
                        if text.strip():
                            texts.append(text)
                            print(f"✓ {filename} processado")
                except Exception as e:
                    print(f"✗ Erro em {filename}: {e}")
        return texts

    def preprocess_text(self, text):
        """Pré-processamento melhorado"""
        text = re.sub(r'[^\w\s.,!?;]', '', text)
        tokens = text.lower().split()
        tokens = [token for token in tokens if len(token) > 1]
        return tokens

    def build_ngram_models(self, tokens):
        """Constrói modelos de n-gramas"""
        # Estatísticas do corpus
        self.corpus_stats = {
            'total_tokens': len(tokens),
            'vocabulary_size': len(set(tokens)),
            'training_date': datetime.now().isoformat()
        }
        
        # Unigramas
        unigram_counts = Counter(tokens)
        total_unigrams = sum(unigram_counts.values())
        self.unigram_probs = { (word,): count/total_unigrams 
                              for word, count in unigram_counts.items() }
        
        # Bigramas
        bigrams = [(tokens[i], tokens[i+1]) for i in range(len(tokens)-1)]
        bigram_counts = Counter(bigrams)
        
        self.bigram_cond = defaultdict(dict)
        for (w1, w2), count in bigram_counts.items():
            if (w1,) not in self.bigram_cond:
                self.bigram_cond[(w1,)] = {}
            self.bigram_cond[(w1,)][(w2,)] = count / unigram_counts[w1]
        
        # Trigramas
        trigrams = [(tokens[i], tokens[i+1], tokens[i+2]) for i in range(len(tokens)-2)]
        trigram_counts = Counter(trigrams)
        
        self.trigram_cond = defaultdict(dict)
        for (w1, w2, w3), count in trigram_counts.items():
            context = (w1, w2)
            if context not in self.trigram_cond:
                self.trigram_cond[context] = {}
            bigram_context = (w1, w2)
            if bigram_context in bigram_counts:
                self.trigram_cond[context][(w3,)] = count / bigram_counts[bigram_context]
        
        self.vocab = set(tokens)
        self.training_date = datetime.now()

    def save_model(self, folder_path="./saved_models"):
        """Salva o modelo treinado em arquivos"""
        try:
            # Cria diretório se não existir
            os.makedirs(folder_path, exist_ok=True)
            
            # Nome do modelo com timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            model_filename = f"{self.model_name}_{timestamp}"
            
            # Salva os dados do modelo usando pickle
            model_data = {
                'unigram_probs': dict(self.unigram_probs),
                'bigram_cond': {str(k): v for k, v in self.bigram_cond.items()},
                'trigram_cond': {str(k): v for k, v in self.trigram_cond.items()},
                'vocab': list(self.vocab),
                'corpus_stats': self.corpus_stats,
                'training_date': self.training_date,
                'model_name': self.model_name
            }
            
            # Salva como pickle (preserva estrutura de dados)
            pickle_path = os.path.join(folder_path, f"{model_filename}.pkl")
            with open(pickle_path, 'wb') as f:
                pickle.dump(model_data, f)
            
            # Salva também como JSON (para inspeção humana)
            json_path = os.path.join(folder_path, f"{model_filename}.json")
            json_data = {
                'model_name': self.model_name,
                'training_date': self.training_date.isoformat() if self.training_date else None,
                'corpus_stats': self.corpus_stats,
                'vocabulary_size': len(self.vocab),
                'unigram_count': len(self.unigram_probs),
                'bigram_count': len(self.bigram_cond),
                'trigram_count': len(self.trigram_cond)
            }
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Modelo salvo com sucesso!")
            print(f"📁 Pickle: {pickle_path}")
            print(f"📁 JSON: {json_path}")
            
            return model_filename
            
        except Exception as e:
            print(f"❌ Erro ao salvar modelo: {e}")
            return None

    def load_model(self, filepath):
        """Carrega um modelo salvo"""
        try:
            with open(filepath, 'rb') as f:
                model_data = pickle.load(f)
            
            # Restaura os dados do modelo
            self.unigram_probs = model_data['unigram_probs']
            
            # Converte strings de volta para tuplas para bigram_cond
            self.bigram_cond = defaultdict(dict)
            for k_str, v in model_data['bigram_cond'].items():
                # Converte string de volta para tupla
                key = eval(k_str)  # Converte "(word,)" de volta para tupla
                self.bigram_cond[key] = v
            
            # Converte strings de volta para tuplas para trigram_cond
            self.trigram_cond = defaultdict(dict)
            for k_str, v in model_data['trigram_cond'].items():
                key = eval(k_str)  # Converte "(word1, word2)" de volta para tupla
                self.trigram_cond[key] = v
            
            self.vocab = set(model_data['vocab'])
            self.corpus_stats = model_data['corpus_stats']
            self.training_date = model_data['training_date']
            self.model_name = model_data.get('model_name', 'loaded_model')
            
            print(f"✅ Modelo carregado com sucesso: {filepath}")
            print(f"📊 Estatísticas: {len(self.vocab)} palavras, "
                  f"{len(self.trigram_cond)} trigramas")
            
            return True
            
        except Exception as e:
            print(f"❌ Erro ao carregar modelo: {e}")
            return False

    def list_saved_models(self, folder_path="./saved_models"):
        """Lista todos os modelos salvos"""
        if not os.path.exists(folder_path):
            print("❌ Pasta de modelos não encontrada")
            return []
        
        models = []
        for filename in os.listdir(folder_path):
            if filename.endswith('.pkl'):
                model_path = os.path.join(folder_path, filename)
                file_time = os.path.getctime(model_path)
                file_date = datetime.fromtimestamp(file_time)
                models.append({
                    'filename': filename,
                    'path': model_path,
                    'date': file_date,
                    'size': os.path.getsize(model_path)
                })
        
        # Ordena por data (mais recente primeiro)
        models.sort(key=lambda x: x['date'], reverse=True)
        
        print("\n📚 Modelos Salvos:")
        print("-" * 50)
        for i, model in enumerate(models, 1):
            print(f"{i}. {model['filename']}")
            print(f"   Data: {model['date'].strftime('%Y-%m-%d %H:%M')}")
            print(f"   Tamanho: {model['size'] / 1024:.1f} KB")
            print()
        
        return models

    def smart_generation(self, num_words=100):
        """Geração de texto inteligente"""
        if not self.vocab:
            return "Modelo não treinado ou carregado adequadamente."
        
        generated = []
        
        # Escolhe um início
        possible_starts = []
        for context in self.trigram_cond.keys():
            possible_starts.append(context)
        
        if possible_starts:
            start_context = random.choice(possible_starts)
            generated.extend(start_context)
        else:
            if self.bigram_cond:
                start_word = random.choice(list(self.bigram_cond.keys()))[0]
                generated.append(start_word)
            else:
                start_word = random.choice(list(self.unigram_probs.keys()))[0]
                generated.append(start_word)
        
        # Continua a geração
        while len(generated) < num_words:
            current_len = len(generated)
            
            # Tenta usar trigrama
            if current_len >= 2:
                context = tuple(generated[-2:])
                if context in self.trigram_cond:
                    next_options = self.trigram_cond[context]
                    if next_options:
                        next_word = self._weighted_choice(next_options)
                        generated.append(next_word[0])
                        continue
            
            # Tenta usar bigrama
            if current_len >= 1:
                context = (generated[-1],)
                if context in self.bigram_cond:
                    next_options = self.bigram_cond[context]
                    if next_options:
                        next_word = self._weighted_choice(next_options)
                        generated.append(next_word[0])
                        continue
            
            # Fallback para unigrama
            next_word = self._weighted_choice(self.unigram_probs)
            generated.append(next_word[0])
        
        return self.format_paragraph(generated)

    def _weighted_choice(self, options):
        """Escolha ponderada baseada em probabilidades"""
        if not options:
            return random.choice(list(self.unigram_probs.keys()))
        
        words = list(options.keys())
        probabilities = list(options.values())
        
        total = sum(probabilities)
        if total == 0:
            return random.choice(words)
        
        normalized_probs = [p/total for p in probabilities]
        return random.choices(words, weights=normalized_probs)[0]

    def format_paragraph(self, words):
        """Formata o parágrafo para melhor legibilidade"""
        if not words:
            return ""
        
        if words[0]:
            words[0] = words[0].capitalize()
        
        text = ' '.join(words)
        words_list = text.split()
        sentences = []
        current_sentence = []
        
        for i, word in enumerate(words_list):
            current_sentence.append(word)
            
            if (len(current_sentence) >= random.randint(8, 15) and 
                i < len(words_list) - 1):
                if i + 1 < len(words_list):
                    words_list[i + 1] = words_list[i + 1].capitalize()
                
                sentences.append(' '.join(current_sentence) + '.')
                current_sentence = []
        
        if current_sentence:
            sentences.append(' '.join(current_sentence) + '.')
        
        return ' '.join(sentences)

    def calculate_perplexity(self, test_tokens):
        """Calcula perplexidade"""
        if not test_tokens:
            return float('inf')
            
        log_sum = 0
        count = 0
        vocab_size = len(self.vocab)
        
        for i in range(len(test_tokens)):
            word = (test_tokens[i],)
            prob = 0
            
            if i >= 2:
                context = (test_tokens[i-2], test_tokens[i-1])
                if context in self.trigram_cond and word in self.trigram_cond[context]:
                    prob = self.trigram_cond[context][word]
            
            elif i >= 1 and prob == 0:
                context = (test_tokens[i-1],)
                if context in self.bigram_cond and word in self.bigram_cond[context]:
                    prob = self.bigram_cond[context][word]
            
            if prob == 0:
                prob = self.unigram_probs.get(word, 1/vocab_size)
            
            log_sum += math.log(prob) if prob > 0 else math.log(1e-10)
            count += 1
        
        return math.exp(-log_sum / count) if count > 0 else float('inf')

    def train_and_save(self, pdf_folder, save_folder="./saved_models"):
        """Treina e salva o modelo"""
        print("📚 Lendo e processando PDFs...")
        texts = self.extract_text_from_pdfs(pdf_folder)
        
        if not texts:
            print("❌ Nenhum PDF válido encontrado!")
            return None
        
        all_tokens = []
        for text in texts:
            all_tokens.extend(self.preprocess_text(text))
        
        print(f"📊 Corpus: {len(all_tokens)} palavras, {len(set(all_tokens))} palavras únicas")
        
        if len(all_tokens) < 50:
            print("❌ Texto insuficiente para treinamento!")
            return None
        
        print("🔨 Construindo modelos de n-gramas...")
        self.build_ngram_models(all_tokens)
        
        print("💾 Salvando modelo...")
        return self.save_model(save_folder)

    def generate_from_loaded_model(self, num_words=100):
        """Gera texto a partir de um modelo carregado"""
        if not self.vocab:
            print("❌ Nenhum modelo carregado!")
            return None
        
        print("🔄 Gerando texto...")
        paragraph = self.smart_generation(num_words)
        
        print("\n" + "="*60)
        print("📝 TEXTO GERADO:")
        print("="*60)
        print(paragraph)
        print("="*60)
        
        return paragraph

def main():
    generator = SavableTextGenerator("meu_modelo_ngram")
    
    if not os.path.exists(PDF_PATH):
        print(f"❌ Pasta '{PDF_PATH}' não encontrada!")
        return
    
    while True:
        print("\n" + "="*50)
        print("🤖 GERADOR DE TEXTO COM MODELOS SALVOS")
        print("="*50)
        print("1. Treinar novo modelo com PDFs")
        print("2. Carregar modelo existente")
        print("3. Listar modelos salvos")
        print("4. Gerar texto com modelo atual")
        print("5. Sair")
        
        choice = input("\nEscolha uma opção (1-5): ").strip()
        
        if choice == '1':
            # Treinar novo modelo
            model_filename = generator.train_and_save(pdf_folder, MODELS_PATH)
            if model_filename:
                print(f"✅ Modelo '{model_filename}' treinado e salvo com sucesso!")
        
        elif choice == '2':
            # Carregar modelo existente
            models = generator.list_saved_models(MODELS_PATH)
            if models:
                try:
                    model_num = int(input("Digite o número do modelo para carregar: ")) - 1
                    if 0 <= model_num < len(models):
                        generator.load_model(models[model_num]['path'])
                    else:
                        print("❌ Número inválido!")
                except ValueError:
                    print("❌ Por favor, digite um número válido!")
        
        elif choice == '3':
            # Listar modelos
            generator.list_saved_models(MODELS_PATH)
        
        elif choice == '4':
            # Gerar texto
            if not generator.vocab:
                print("❌ Nenhum modelo carregado! Treine ou carregue um modelo primeiro.")
            else:
                try:
                    num_words = int(input("Número de palavras para gerar (padrão 100): ") or "100")
                    generator.generate_from_loaded_model(num_words)
                except ValueError:
                    print("❌ Número inválido! Usando padrão de 100 palavras.")
                    generator.generate_from_loaded_model(100)
        
        elif choice == '5':
            print("👋 Saindo...")
            break
        
        else:
            print("❌ Opção inválida!")

if __name__ == "__main__":
    main()

