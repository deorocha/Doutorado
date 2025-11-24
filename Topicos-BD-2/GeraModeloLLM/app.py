import streamlit as st
import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import random
import math
import numpy as np
import re
from collections import defaultdict

import nltk
from nltk.tokenize import word_tokenize
nltk.download('punkt')

# Importar a classe do modelo
from gera_modelo import SavableTextGenerator

PROJECT_ROOT = Path(__file__).parent
MODELS_PATH = PROJECT_ROOT / "saved_models"
DICT_PATH = PROJECT_ROOT / "dicionario.txt"

def separar_palavras(texto):
    # Carrega o dicionário
    with open('dicionario.txt', 'r', encoding='utf-8') as f:
        palavras = set(linha.strip().lower() for linha in f)
    
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

def generate_cooccurrence_matrix(model, matrix_size=10, stopwords=None, remove_numbers=True):
    """Gera uma matriz de coocorrência termo a termo baseada em distância entre palavras"""
    if not hasattr(model, 'unigram_probs') or not model.unigram_probs:
        return None, None
    
    # Definir stopwords padrão se não fornecidas
    if stopwords is None:
        stopwords = set()
    
    # Obter as palavras mais frequentes
    all_words = sorted(model.unigram_probs.items(), key=lambda x: x[1], reverse=True)
    
    # Filtrar stopwords e números
    filtered_words = []
    for word_prob in all_words:
        word = word_prob[0][0]
        
        # Pular se for stopword
        if word in stopwords:
            continue
            
        # Pular se for número (quando remove_numbers é True)
        if remove_numbers and (word.isdigit() or (word.replace(',', '').replace('.', '').isdigit() and len(word) <= 6)):
            continue
            
        # Pular anos comuns (4 dígitos)
        if remove_numbers and re.match(r'^\d{4}$', word):
            continue
            
        filtered_words.append(word_prob)
    
    # Pegar as palavras mais frequentes após filtrar stopwords e números
    top_words = filtered_words[:matrix_size]
    words = [word[0][0] for word in top_words]
    
    # Inicializar matriz de coocorrência com zeros
    cooccurrence_matrix = np.zeros((matrix_size, matrix_size), dtype=int)
    
    # Calcular coocorrência baseada em bigramas
    # Para cada par de palavras, contar quantas vezes aparecem juntas em bigramas
    for i, word1 in enumerate(words):
        context = (word1,)
        if context in model.bigram_cond:
            # Para cada palavra que segue word1, incrementar a coocorrência
            for word2_tuple, prob in model.bigram_cond[context].items():
                word2 = word2_tuple[0]
                if word2 in words:
                    j = words.index(word2)
                    # A coocorrência é baseada na frequência (convertemos probabilidade para contagem aproximada)
                    count = int(prob * 1000)  # Multiplicamos por 1000 para ter valores inteiros significativos
                    cooccurrence_matrix[i][j] += count
    
    return cooccurrence_matrix, words

def create_cooccurrence_heatmap(matrix, words, title="Matriz de Coocorrência"):
    """Cria um heatmap da matriz de coocorrência mostrando TODOS os valores"""
    if matrix is None or words is None:
        return None
    
    # Criar DataFrame para melhor visualização
    df = pd.DataFrame(matrix, index=words, columns=words)
    
    # Criar heatmap
    fig = px.imshow(
        matrix,
        x=words,
        y=words,
        title=title,
        aspect="auto",
        color_continuous_scale="Blues"
    )
    
    # Personalizar o layout
    fig.update_layout(
        xaxis_title="Palavra",
        yaxis_title="Palavra",
        height=600
    )
    
    # Adicionar anotações para TODOS os valores, incluindo zeros
    for i in range(len(words)):
        for j in range(len(words)):
            # Sempre adicionar anotação, independente do valor
            fig.add_annotation(
                x=j, y=i,
                text=f"{matrix[i][j]}",
                showarrow=False,
                font=dict(
                    size=10,
                    color="black" if matrix[i][j] == 0 or matrix[i][j] < np.max(matrix) / 2 else "white"
                )
            )
    
    return fig, df

def parse_stopwords(stopwords_text):
    """Converte texto de stopwords separadas por vírgula em um conjunto"""
    if not stopwords_text:
        return set()
    
    # Dividir por vírgula, remover espaços extras e converter para minúsculas
    stopwords_list = [word.strip().lower() for word in stopwords_text.split(',')]
    # Remover entradas vazias
    return set(word for word in stopwords_list if word)

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
        'generation_counter': 0,
        'cooccurrence_matrix': None,
        'cooccurrence_words': None,
        'matrix_size': 10,
        'stopwords_text': "as, da, de, do, em, que, os, um, uma, para, no, na, não, com, por, se, mais, mas, como, ou, ser, seu, sua, seus, suas, ao, aos, pela, pelas, isto, isso, aquilo, este, esta, estes, estas, esse, essa, esses, essas, aquele, aquela, aqueles, aquelas, todo, todos, toda, todas, outro, outros, outra, outras, mesmo, mesma, mesmos, mesmas, tal, tais, cada, qual, quais, qualquer, quaisquer, certo, certa, certos, certas, vários, várias, muito, muita, muitos, muitas, pouco, pouca, poucos, poucas, algo, alguém, algum, alguma, alguns, algumas, nenhum, nenhuma, nenhuns, nenhumas, todo, todos, toda, todas, outro, outros, outra, outras, mesmo, mesma, mesmos, mesmas, tal, tais, cada, qual, quais, qualquer, quaisquer, certo, certa, certos, certas, vários, várias, muito, muita, muitos, muitas, pouco, pouca, poucos, poucas, algo, alguém, algum, alguma, alguns, algumas, nenhum, nenhuma, nenhuns, nenhumas",
        'remove_numbers': True,
        'sidebar_initialized': False
    }
    
    for key, default in session_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default
    
    # Sidebar para gerenciamento de modelos - AGORA COM CACHE
    with st.sidebar:
        st.header("🔧 Configurações do Modelo")
        
        # Inicializar a sidebar apenas uma vez
        if not st.session_state.sidebar_initialized:
            # saved_models = load_saved_models()
            saved_models = load_saved_models(MODELS_PATH)
            st.session_state.saved_models = saved_models
            st.session_state.sidebar_initialized = True
        else:
            saved_models = st.session_state.saved_models
        
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
                    st.success(f"✅ Modelo '{selected_model_name}' carregado com sucesso!")
                else:
                    st.error("❌ Erro ao carregar o modelo!")
        
        # Mostrar estatísticas do modelo carregado - SEPARADO E COM CACHE
        if st.session_state.get('model_loaded') and st.session_state.get('model_stats'):
            st.markdown("---")
            st.header("📊 Estatísticas do Modelo")
            
            # Usar container para isolar as estatísticas
            stats_container = st.container()
            
            with stats_container:
                if st.session_state.get('charts'):
                    st.plotly_chart(st.session_state.charts['ngram_chart'], use_container_width=True, key="ngram_chart")
                    st.plotly_chart(st.session_state.charts['general_chart'], use_container_width=True, key="general_chart")
                
                # MOSTRAR PERPLEXIDADE
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
                
                with st.expander("📅 Informações Adicionais", expanded=False):
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
        
        # Usar um key único para o text_area para evitar recriação
        text_input = st.text_area(
            "Digite seu texto:", 
            value=st.session_state.text_input, 
            height=200,
            placeholder="Comece a digitar... Pressione espaço para ver sugestões!",
            key="main_text_input", 
            label_visibility="collapsed"
        )
        
        # Atualizar o estado apenas se o texto mudou
        if text_input != st.session_state.text_input:
            st.session_state.text_input = text_input
        
        # Detectar espaço para sugestões
        if (st.session_state.model_loaded and len(text_input) > 0 and text_input.endswith(' ')):
            current_text = text_input.rstrip()
            if current_text:
                st.session_state.suggestions = get_suggestions_with_details(current_text, st.session_state.model)
                st.session_state.show_suggestions = True
        
        if st.button("🗑️ Limpar Texto", key="limpar_texto_btn"):
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
            st.dataframe(df, use_container_width=True, hide_index=True, key="suggestions_df")
            
            if st.button("🙅‍♂️ Ignorar Sugestões", use_container_width=True, key="ignorar_sugestoes_btn"):
                st.session_state.show_suggestions = False
                st.rerun()
        elif st.session_state.model_loaded:
            st.info("💡 Pressione **espaço** após digitar uma palavra para ver sugestões!")
    
    # Seção de geração de texto
    if st.session_state.model_loaded:
        st.markdown("---")
        st.subheader("🎲 Geração de Texto")
        
        # Usar um formulário para evitar refresh completo da página
        with st.form("geracao_texto_form", clear_on_submit=False):
            col1, col2, col3 = st.columns([1, 1, 1])
            
            with col1:
                num_words = st.slider("Número de palavras:", 10, 200, 50, key="num_words_slider")
            
            with col2:
                gerar_com_espacos = st.checkbox("Com espaços", value=True, key="gerar_com_espacos_checkbox")
                
            with col3:
                gerar_texto_submit = st.form_submit_button("✨ Gerar Texto", use_container_width=True)
            
            if gerar_texto_submit:
                with st.spinner("Gerando texto..."):
                    try:
                        # Usar o método smart_generation do modelo
                        texto_gerado = st.session_state.model.smart_generation(num_words)
                        
                        # Aplicar separação de palavras se necessário
                        if not gerar_com_espacos:
                            # Se não for com espaços, remover os espaços do texto gerado
                            texto_gerado = texto_gerado.replace(" ", "")
                        else:
                            # Se for com espaços, garantir que o texto está bem formatado
                            texto_gerado = separar_palavras(texto_gerado)
                        
                        st.session_state.generated_text = texto_gerado
                        st.session_state.generation_counter += 1
                        
                    except Exception as e:
                        st.error(f"❌ Erro ao gerar texto: {e}")
                        st.session_state.generated_text = ""

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
                
                if st.button("🔄 Adicionar Espaços", use_container_width=True, key="adicionar_espacos_btn"):
                    with st.spinner("Adicionando espaços..."):
                        st.session_state.generated_text = add_spaces_to_text(
                            st.session_state.generated_text, st.session_state.model
                        )
                        st.rerun()
            
            # Mostrar texto gerado
            formato = "com espaços" if gerar_com_espacos else "sem espaços"
            st.caption(f"Texto gerado {formato} ({num_words} palavras) - Geração #{st.session_state.generation_counter}")
            
            st.text_area("Texto Gerado:", value=st.session_state.generated_text, height=150, key="display_generated")
        
        # SEÇÃO: Geração de Matriz de Coocorrência
        st.markdown("---")
        st.subheader("📊 Geração de Matriz de Coocorrência")
        
        st.markdown("""
        Esta matriz mostra a frequência com que as palavras aparecem juntas no corpus.
        **Todos os valores são mostrados**, incluindo zeros (sem coocorrência).
        Valores mais altos indicam que as palavras coocorrem com mais frequência.
        """)
        
        # Usar formulário para a matriz também
        with st.form("matriz_coocorrencia_form", clear_on_submit=False):
            # Controles para a matriz
            col_size, col_stopwords = st.columns([1, 2])
            
            with col_size:
                matrix_size = st.slider(
                    "Tamanho da matriz (n x n):",
                    min_value=5,
                    max_value=20,
                    value=st.session_state.matrix_size,
                    key="matrix_size_slider"
                )
                
                # Checkbox para remover números
                remove_numbers = st.checkbox(
                    "Remover números",
                    value=st.session_state.remove_numbers,
                    help="Exclui números (0, 1, 2, 10, 2024, etc.) da matriz",
                    key="remove_numbers_checkbox"
                )
            
            with col_stopwords:
                stopwords_text = st.text_area(
                    "Stopwords (separadas por vírgula):",
                    value=st.session_state.stopwords_text,
                    height=100,
                    help="Palavras que devem ser excluídas da matriz. Separe por vírgulas.",
                    key="stopwords_text_area"
                )
            
            # Botão para gerar matriz dentro do formulário
            gerar_matriz_submit = st.form_submit_button("🔢 Gerar Matriz de Coocorrência", use_container_width=True)
            
            if gerar_matriz_submit:
                with st.spinner(f"Gerando matriz {matrix_size}x{matrix_size}..."):
                    # Atualizar estados
                    st.session_state.matrix_size = matrix_size
                    st.session_state.remove_numbers = remove_numbers
                    st.session_state.stopwords_text = stopwords_text
                    
                    # Parse das stopwords
                    stopwords_set = parse_stopwords(stopwords_text)
                    
                    # Gerar matriz excluindo stopwords e números
                    matrix, words = generate_cooccurrence_matrix(
                        st.session_state.model, 
                        matrix_size, 
                        stopwords_set,
                        remove_numbers=remove_numbers
                    )
                    st.session_state.cooccurrence_matrix = matrix
                    st.session_state.cooccurrence_words = words
        
        # Exibir a matriz se existir
        if (st.session_state.cooccurrence_matrix is not None and 
            st.session_state.cooccurrence_words is not None):
            
            st.success(f"✅ Matriz de Coocorrência {st.session_state.matrix_size}x{st.session_state.matrix_size} gerada com sucesso!")
            
            # Informações sobre filtragem
            filter_info = []
            if st.session_state.stopwords_text:
                stopwords_count = len(parse_stopwords(st.session_state.stopwords_text))
                filter_info.append(f"{stopwords_count} stopwords")
            
            if st.session_state.remove_numbers:
                filter_info.append("números")
            
            if filter_info:
                st.info(f"📝 {', '.join(filter_info)} foram excluídos da matriz")
            
            # Criar e exibir o heatmap
            fig, df_matrix = create_cooccurrence_heatmap(
                st.session_state.cooccurrence_matrix,
                st.session_state.cooccurrence_words,
                title=f"Matriz de Coocorrência ({st.session_state.matrix_size}x{st.session_state.matrix_size}) - TODOS os valores mostrados"
            )
            
            if fig:
                st.plotly_chart(fig, use_container_width=True, key="cooccurrence_heatmap")
            
            # Exibir tabela com os dados numéricos
            with st.expander("📋 Ver Dados Numéricos da Matriz", expanded=False):
                st.dataframe(df_matrix, use_container_width=True, key="cooccurrence_df")
                
                # Botão para download dos dados
                csv = df_matrix.to_csv().encode('utf-8')
                st.download_button(
                    label="📥 Download CSV",
                    data=csv,
                    file_name=f"matriz_coocorrencia_{st.session_state.matrix_size}x{st.session_state.matrix_size}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="download_csv_btn"
                )
            
            # Estatísticas da matriz - CORRIGIDO: removido parâmetro 'key' do st.metric()
            st.subheader("📈 Estatísticas da Matriz")
            col_stats1, col_stats2, col_stats3, col_stats4 = st.columns(4)
            
            with col_stats1:
                avg_count = np.mean(st.session_state.cooccurrence_matrix)
                st.metric("Coocorrência Média", f"{avg_count:.1f}")
            
            with col_stats2:
                max_count = np.max(st.session_state.cooccurrence_matrix)
                st.metric("Coocorrência Máxima", f"{max_count}")
            
            with col_stats3:
                non_zero = np.count_nonzero(st.session_state.cooccurrence_matrix)
                total_cells = st.session_state.matrix_size * st.session_state.matrix_size
                coverage = (non_zero / total_cells) * 100
                st.metric("Células Não Zero", f"{coverage:.1f}%")
            
            with col_stats4:
                zero_cells = total_cells - non_zero
                st.metric("Células Zero", f"{zero_cells}")

if __name__ == "__main__":
    main()


