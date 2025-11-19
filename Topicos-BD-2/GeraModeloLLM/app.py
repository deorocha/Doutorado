import streamlit as st
import os
import pandas as pd
import plotly.express as px
import random
import math
import numpy as np

import nltk
from nltk.tokenize import word_tokenize
nltk.download('punkt')

# Importar a classe do modelo
from gera_modelo import SavableTextGenerator

def separar_palavras(texto):
    # Carrega o dicionário
    with open('dicionario.txt', 'r', encoding='utf-8') as f:
        palavras = set(linha.strip().lower() for linha in f)
    
    # Adiciona palavras específicas do seu texto que podem estar faltando
    # palavras_extras = {'180º', '90º', 'aos', 'apenas', 'api', 'aproximadamente', 'as', 'atender', 'ativa', 'bem', 'botão', 'bsn', 'buscando', 'como', 'computacional', 'configuração', 'correções', 'cotovelo', 'cria', 'criado', 'cuja', 'da', 'de', 'de', 'autoria', 'demanda', 'desta', 'deve', 'devem', 'disponíveis', 'disponível', 'do', 'dorso', 'em', 'encontra', 'encontrados', 'entre', 'esses', 'está', 'estar', 'excel', 'flexão', 'foi', 'foram', 'forma', 'função', 'gerados', 'gráficos', 'horizon', 'imagens', 'implementados', 'interesse', 'interface', 'invasiva', 'irão', 'jogo', 'local', 'mão', 'mas', 'menos', 'método', 'métodos', 'não', 'no', 'offset', 'os', 'os', 'ou', 'palma', 'para', 'participantes', 'pelo', 'pelos', 'plataforma', 'podendo', 'posicionado', 'possível', 'possui', 'principais', 'problemas', 'profissionais', 'programador', 'propostas', 'que', 'realiza', 'redes', 'requisitos', 'reset', 'rotação', 'são', 'se', 'ser', 'sintetizada', 'situado', 'software', 'sugestões', 'talmente', 'também', 'tivamente', 'um', 'usuário', 'utilizada', 'utilizando', 'variando', 'via', 'web'}
    # palavras.update(palavras_extras)
    
    texto_lower = texto.lower()
    n = len(texto)
    
    # DP: dp[i] = (custo, índice_anterior)
    # Custo: 0 para palavras conhecidas, comprimento para palavras desconhecidas
    dp = [(float('inf'), -1) for _ in range(n + 1)]
    dp[0] = (0, 0)  # Caso base
    
    for i in range(1, n + 1):
        # Tenta todas as substrings que terminam em i
        for j in range(i):
            substring = texto_lower[j:i]
            
            # Calcula o custo
            if substring in palavras:
                custo = dp[j][0]  # Palavra conhecida: custo 0 adicional
            else:
                custo = dp[j][0] + len(substring)  # Palavra desconhecida: penalidade pelo comprimento
            
            # Atualiza se encontrou um custo menor
            if custo < dp[i][0]:
                dp[i] = (custo, j)
    
    # Reconstruir a segmentação
    if dp[n][0] == float('inf'):
        return texto
    
    segments = []
    i = n
    while i > 0:
        prev = dp[i][1]
        segments.append(texto[prev:i])
        i = prev
    
    return ' '.join(reversed(segments))

def load_saved_models(models_folder="./saved_models"):
    """Carrega a lista de modelos salvos"""
    if not os.path.exists(models_folder):
        return []
    
    models = []
    for filename in os.listdir(models_folder):
        if filename.endswith('.pkl'):
            model_path = os.path.join(models_folder, filename)
            models.append({
                'filename': filename,
                'path': model_path,
                'name': filename.replace('.pkl', '')
            })
    
    return models

def get_suggestions_with_details(text, model, max_suggestions=5):
    """Obtém sugestões baseadas no texto digitado com informações detalhadas"""
    if not text.strip() or not model.vocab:
        return []
    
    tokens = model.preprocess_text(text)
    if not tokens:
        return []
    
    suggestions = []
    
    # Tenta usar trigrama (últimas 2 palavras)
    if len(tokens) >= 2:
        context = tuple(tokens[-2:])
        if context in model.trigram_cond:
            next_options = model.trigram_cond[context]
            for word, prob in sorted(next_options.items(), key=lambda x: x[1], reverse=True)[:max_suggestions]:
                suggestions.append({
                    'word': word[0],
                    'probability': prob,
                    'type': 'T'
                })
    
    # Tenta usar bigrama (última palavra)
    if len(suggestions) < max_suggestions and len(tokens) >= 1:
        context = (tokens[-1],)
        if context in model.bigram_cond:
            for word, prob in sorted(model.bigram_cond[context].items(), key=lambda x: x[1], reverse=True):
                if not any(s['word'] == word[0] for s in suggestions):
                    suggestions.append({
                        'word': word[0],
                        'probability': prob,
                        'type': 'B'
                    })
                    if len(suggestions) >= max_suggestions:
                        break
    
    # Completa com unigramas se necessário
    if len(suggestions) < max_suggestions:
        for word_prob in sorted(model.unigram_probs.items(), key=lambda x: x[1], reverse=True):
            word = word_prob[0][0]
            if not any(s['word'] == word for s in suggestions):
                suggestions.append({
                    'word': word,
                    'probability': word_prob[1],
                    'type': 'U'
                })
                if len(suggestions) >= max_suggestions:
                    break
    
    return suggestions[:max_suggestions]

def calculate_model_statistics(model):
    """Calcula estatísticas do modelo incluindo perplexidade"""
    stats = {}
    
    stats['pdfs_processados'] = 20
    stats['total_tokens'] = model.corpus_stats.get('total_tokens', 0)
    stats['tamanho_vocabulario'] = model.corpus_stats.get('vocabulary_size', 0)
    stats['unigramas_unicos'] = len(model.unigram_probs)
    stats['bigramas_unicos'] = len(model.bigram_cond)
    stats['trigramas_unicos'] = len(model.trigram_cond)
    stats['data_treinamento'] = model.training_date.strftime('%Y-%m-%d %H:%M') if model.training_date else 'N/A'
    
    # Calcular perplexidade CORRIGIDA
    try:
        if hasattr(model, 'unigram_probs') and model.unigram_probs:
            # Método 1: Baseado na entropia do modelo
            log_prob_sum = 0
            count = 0
            
            # Usar uma amostra do corpus de treinamento para calcular perplexidade
            # Ou usar as probabilidades dos unigramas como aproximação
            total_prob = sum(prob for _, prob in model.unigram_probs.items())
            
            if total_prob > 0:
                # Calcular entropia cruzada
                cross_entropy = -sum(prob * math.log(prob) for _, prob in model.unigram_probs.items() if prob > 0) / total_prob
                stats['perplexidade'] = math.exp(cross_entropy)
            else:
                stats['perplexidade'] = float('inf')
        else:
            stats['perplexidade'] = float('inf')
    except Exception as e:
        print(f"Erro no cálculo da perplexidade: {e}")
        stats['perplexidade'] = float('inf')
    
    return stats

def create_statistics_charts(stats):
    """Cria gráficos para as estatísticas do modelo"""
    charts = {}
    
    # Gráfico de n-gramas
    ngram_df = pd.DataFrame({
        'Tipo': ['Unigramas', 'Bigramas', 'Trigramas'],
        'Quantidade': [stats['unigramas_unicos'], stats['bigramas_unicos'], stats['trigramas_unicos']]
    })
    
    charts['ngram_chart'] = px.bar(
        ngram_df, x='Tipo', y='Quantidade', title='Distribuição de N-gramas',
        color='Tipo', text='Quantidade'
    )
    charts['ngram_chart'].update_traces(textposition='inside')
    charts['ngram_chart'].update_layout(showlegend=False, height=400)
    
    # Gráfico de estatísticas gerais - AGORA COM PERPLEXIDADE
    general_metrics = ['Tokens', 'Vocabulário', 'Perplexidade']
    
    # Tratar valor infinito da perplexidade para exibição no gráfico
    perplexity_value = stats.get('perplexidade', 0)
    if perplexity_value == float('inf'):
        perplexity_display = 0  # Ou um valor muito alto para visualização
    else:
        perplexity_display = perplexity_value
    
    general_values = [stats['total_tokens'], stats['tamanho_vocabulario'], perplexity_display]
    
    general_df = pd.DataFrame({'Métrica': general_metrics, 'Valor': general_values})
    
    # Formatar labels de forma diferente para cada métrica
    def format_label(metrica, valor):
        if metrica == 'Perplexidade':
            if stats.get('perplexidade', 0) == float('inf'):
                return "Infinito"
            else:
                return f"{valor:.2f}"
        else:
            return f"{valor:,}"
    
    general_df['Label'] = general_df.apply(lambda row: format_label(row['Métrica'], row['Valor']), axis=1)
    
    charts['general_chart'] = px.bar(
        general_df, x='Métrica', y='Valor', title='Estatísticas do Corpus',
        color='Métrica', text='Label'
    )
    charts['general_chart'].update_traces(textposition='inside')
    charts['general_chart'].update_layout(showlegend=False, height=400)
    
    return charts

def generate_random_text(model, num_words, with_spaces=True):
    """Gera texto aleatório"""
    random.seed()
    
    generated_words = []
    
    for i in range(num_words):
        if i == 0 and model.unigram_probs:
            # Começar com unigrama
            words, probs = zip(*model.unigram_probs.items())
            word = random.choices([w[0] for w in words], weights=probs)[0]
            generated_words.append(word)
        elif len(generated_words) >= 2:
            # Tentar trigrama
            context = tuple(generated_words[-2:])
            if context in model.trigram_cond:
                next_words, probs = zip(*model.trigram_cond[context].items())
                word = random.choices([w[0] for w in next_words], weights=probs)[0]
                generated_words.append(word)
            elif len(generated_words) >= 1:
                # Fallback para bigrama
                context = (generated_words[-1],)
                if context in model.bigram_cond:
                    next_words, probs = zip(*model.bigram_cond[context].items())
                    word = random.choices([w[0] for w in next_words], weights=probs)[0]
                    generated_words.append(word)
                elif model.unigram_probs:
                    # Fallback para unigrama
                    words, probs = zip(*model.unigram_probs.items())
                    word = random.choices([w[0] for w in words], weights=probs)[0]
                    generated_words.append(word)
        elif len(generated_words) >= 1 and model.bigram_cond:
            # Usar bigrama
            context = (generated_words[-1],)
            if context in model.bigram_cond:
                next_words, probs = zip(*model.bigram_cond[context].items())
                word = random.choices([w[0] for w in next_words], weights=probs)[0]
                generated_words.append(word)
        elif model.unigram_probs:
            # Fallback para unigrama
            words, probs = zip(*model.unigram_probs.items())
            word = random.choices([w[0] for w in words], weights=probs)[0]
            generated_words.append(word)
    
    # Formatar texto final
    if with_spaces:
        return " ".join(generated_words)
    else:
        return "".join(generated_words)

def add_spaces_to_text(text, model):
    """Adiciona espaços entre palavras usando o vocabulário do modelo"""
    if not text or not hasattr(model, 'vocab') or not model.vocab:
        return text
    
    text_lower = text.lower()
    vocab_words = sorted(list(model.vocab), key=len, reverse=True)
    
    result = []
    i = 0
    n = len(text_lower)
    
    while i < n:
        found_word = None
        for word in vocab_words:
            if text_lower.startswith(word, i):
                if not found_word or len(word) > len(found_word):
                    found_word = word
        
        if found_word:
            result.append(text[i:i+len(found_word)])
            i += len(found_word)
        else:
            result.append(text[i])
            i += 1
    
    return " ".join(result)

def main():
    st.set_page_config(page_title="Autocompletar com LLM", page_icon="✍️", layout="wide")
    
    st.header("✍️ Geração de textos com modelos probabilísticos")
    st.markdown("Digite texto abaixo e pressione **Ctrl + Enter** para ver sugestões da próxima palavra!")
    
    # Inicializar estados da sessão
    session_defaults = {
        'model_loaded': False,
        'model_stats': {},
        'charts': {},
        'text_input': "",
        'suggestions': [],
        'show_suggestions': False,
        'generated_text': "",
        'generation_counter': 0
    }
    
    for key, default in session_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default
    
    # Sidebar para gerenciamento de modelos
    with st.sidebar:
        st.header("🔧 Configurações do Modelo")
        
        saved_models = load_saved_models()
        
        if not saved_models:
            st.warning("⚠️ Nenhum modelo salvo encontrado!")
            st.info("Execute primeiro o `gera_modelo.py` para treinar um modelo.")
        else:
            selected_model_name = st.selectbox("📁 Selecione um modelo:", [model['name'] for model in saved_models])
            
            if st.button("🚀 Carregar Modelo Selecionado"):
                selected_model_path = next(model['path'] for model in saved_models if model['name'] == selected_model_name)
                generator = SavableTextGenerator()
                
                if generator.load_model(selected_model_path):
                    st.session_state.model = generator
                    st.session_state.model_loaded = True
                    st.session_state.model_name = selected_model_name
                    st.session_state.model_stats = calculate_model_statistics(generator)
                    st.session_state.charts = create_statistics_charts(st.session_state.model_stats)
                else:
                    st.error("❌ Erro ao carregar o modelo!")
        
        # Mostrar estatísticas do modelo carregado
        if st.session_state.get('model_loaded') and st.session_state.get('model_stats'):
            st.markdown("---")
            st.header("📊 Estatísticas do Modelo")
            
            if st.session_state.get('charts'):
                st.plotly_chart(st.session_state.charts['ngram_chart'], use_container_width=True)
                st.plotly_chart(st.session_state.charts['general_chart'], use_container_width=True)
            
            # MOSTRAR PERPLEXIDADE ABAIXO DO GRÁFICO (agora como destaque adicional)
            stats = st.session_state.model_stats
            if 'perplexidade' in stats:
                perplexity_value = stats['perplexidade']
                if perplexity_value == float('inf'):
                    st.metric(
                        label="🧠 Perplexidade do Modelo",
                        value="Infinito",
                        help="Não foi possível calcular a perplexidade. O modelo pode não ter probabilidades válidas."
                    )
                else:
                    st.metric(
                        label="🧠 Perplexidade do Modelo",
                        value=f"{perplexity_value:.2f}",
                        delta=f"Geração #{st.session_state.get('generation_counter', 0)}",
                        help="Quanto menor a perplexidade, melhor o modelo. Mede o quão 'surpreso' o modelo fica com novos dados."
                    )
            
            with st.expander("📅 Informações Adicionais"):
                st.write(f"**Data de Treinamento:** {stats['data_treinamento']}")
                st.write(f"**Modelo Carregado:** {st.session_state.model_name}")
                st.write(f"**PDFs Processados:** {stats['pdfs_processados']}")
                st.write(f"**Total de Tokens:** {stats['total_tokens']:,}")
                st.write(f"**Tamanho do Vocabulário:** {stats['tamanho_vocabulario']:,}")
                st.write(f"**Unigramas Únicos:** {stats['unigramas_unicos']:,}")
                st.write(f"**Bigramas Únicos:** {stats['bigramas_unicos']:,}")
                st.write(f"**Trigramas Únicos:** {stats['trigramas_unicos']:,}")
                
                perplexity_value = stats.get('perplexidade', 0)
                if perplexity_value == float('inf'):
                    st.write(f"**Perplexidade:** Infinito (não calculável)")
                else:
                    st.write(f"**Perplexidade:** {perplexity_value:.2f}")
                
                if st.session_state.model.vocab:
                    vocab_sample = list(st.session_state.model.vocab)[:10]
                    st.write(f"**Amostra do Vocabulário:** {', '.join(vocab_sample)}...")
    
    # Área principal do aplicativo
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📝 Editor de Texto")
        
        text_input = st.text_area(
            "Digite seu texto:", value=st.session_state.text_input, height=200,
            placeholder="Comece a digitar... Pressione espaço para ver sugestões!",
            key="main_text_input", label_visibility="collapsed"
        )
        
        st.session_state.text_input = text_input
        
        # Detectar espaço para sugestões
        if (st.session_state.model_loaded and len(text_input) > 0 and text_input.endswith(' ')):
            current_text = text_input.rstrip()
            if current_text:
                st.session_state.suggestions = get_suggestions_with_details(current_text, st.session_state.model)
                st.session_state.show_suggestions = True
        
        if st.button("🗑️ Limpar Texto"):
            st.session_state.text_input = ""
            st.session_state.suggestions = []
            st.session_state.show_suggestions = False
            st.rerun()
    
    with col2:
        st.subheader("💡 Sugestões")
        
        if not st.session_state.model_loaded:
            st.info("👈 Carregue um modelo para começar!")
        elif st.session_state.show_suggestions and st.session_state.suggestions:
            st.success("T=Trigrama, B=Bigrama, U=Unigrama")
            
            suggestions_data = []
            for suggestion in st.session_state.suggestions:
                suggestions_data.append({
                    'Palavra': suggestion['word'],
                    'Probabilidade': f"{suggestion['probability'] * 100:.3f}%",
                    'Tipo': suggestion['type']
                })
            
            df = pd.DataFrame(suggestions_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            if st.button("🙅‍♂️ Ignorar Sugestões", use_container_width=True):
                st.session_state.show_suggestions = False
                st.rerun()
        elif st.session_state.model_loaded:
            st.info("💡 Pressione **espaço** após digitar uma palavra para ver sugestões!")
    
    # Seção de geração de texto
    if st.session_state.model_loaded:
        st.markdown("---")
        st.subheader("🎲 Geração de Texto")
        
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            num_words = st.slider("Número de palavras:", 10, 200, 50, key="num_words_slider")
        
        with col2:
            gerar_com_espacos = st.checkbox("Com espaços", value=True, key="gerar_com_espacos_checkbox")
            
        #with col3:
        #    if st.button("✨ Gerar Texto", key="gerar_texto_btn", use_container_width=True):
        #        with st.spinner("Gerando texto..."):
        #            st.session_state.generation_counter += 1
        #            st.session_state.generated_text = generate_random_text(
        #                st.session_state.model, num_words, gerar_com_espacos
        #            )
        #            st.rerun()
        with col3:
            if st.button("✨ Gerar Texto", key="gerar_texto_btn", use_container_width=True):
                with st.spinner("Gerando texto..."):
                    st.session_state.generation_counter += 1
                    texto = generate_random_text(st.session_state.model, num_words, gerar_com_espacos)
                    st.session_state.generated_text = separar_palavras(texto)
                    st.rerun()

        # Controles para texto gerado
        if st.session_state.generated_text:
            col_copy, col_clear = st.columns(2)
            
            with col_copy:
                if st.button("📋 Copiar texto", use_container_width=True, key="copiar_editor_btn"):
                    st.session_state.text_input = st.session_state.generated_text
                    st.success("✅ Texto copiado para o editor!")
                    st.rerun()
            
            with col_clear:
                if st.button("🗑️ Limpar texto", use_container_width=True, key="limpar_gerado_btn"):
                    st.session_state.generated_text = ""
                    st.rerun()
            
            # Adicionar espaços se necessário
            if not gerar_com_espacos:
                st.markdown("---")
                st.subheader("🔤 Adicionar Espaços ao Texto")
                
                if st.button("🔄 Adicionar Espaços", use_container_width=True):
                    with st.spinner("Adicionando espaços..."):
                        st.session_state.generated_text = add_spaces_to_text(
                            st.session_state.generated_text, st.session_state.model
                        )
                        st.rerun()
            
            # Mostrar texto gerado
            formato = "com espaços" if gerar_com_espacos else "sem espaços"
            st.caption(f"Texto gerado {formato} ({num_words} palavras) - Geração #{st.session_state.generation_counter}")
            
            st.text_area("Texto Gerado:", value=st.session_state.generated_text, height=150, key="display_generated")

if __name__ == "__main__":
    main()

## Exemplo de uso
#texto_sem_espaco = "scenfigura3médiaembleudodesempenhodastécnicasde"
#texto_com_espacos = inserir_espacos_automatico(texto_sem_espaco)
#print(texto_com_espacos)

