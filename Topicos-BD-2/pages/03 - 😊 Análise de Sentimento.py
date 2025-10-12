import streamlit as st
import re
import json
from collections import defaultdict
from textblob import TextBlob
import matplotlib.pyplot as plt
import pandas as pd
import PyPDF2
import io
from pathlib import Path

# Obtém o diretório raiz do projeto (onde está o app.py)
current_dir = Path(__file__).parent if "__file__" in locals() else Path.cwd()
project_root = current_dir.parent  # Sobe um nível para a pasta raiz

# Constrói caminhos absolutos para os arquivos
css_path = project_root / "styles" / "styles.css"
categories_path = project_root / "categories.json"

# Configuração do TextBlob
@st.cache_resource
def setup_textblob():
    """Configura todos os recursos necessários para o TextBlob"""
    import nltk
    
    # Lista de corpora necessários
    corpora = [
        'punkt',        # Tokenizer
        'brown',        # Corpus para treinamento
        'movie_reviews', # Análise de sentimentos
        'wordnet',      # Thesaurus
        'averaged_perceptron_tagger', # POS tagging
        'stopwords'     # Palavras comuns para remoção
    ]
    
    for corpus in corpora:
        try:
            nltk.data.find(f'tokenizers/{corpus}' if corpus == 'punkt' else f'corpora/{corpus}' if corpus in ['brown', 'movie_reviews', 'wordnet', 'stopwords'] else f'taggers/{corpus}')
        except LookupError:
            with st.spinner(f'Baixando {corpus}...'):
                nltk.download(corpus, quiet=True)
    
    st.success("TextBlob configurado com sucesso!")

# Executa a configuração do TextBlob
try:
    setup_textblob()
except Exception as e:
    st.warning(f"Alguns recursos do TextBlob podem não funcionar: {e}")

# Carregar CSS externo com codificação correta
def load_css():
    try:
        with open(css_path, "r", encoding="utf-8") as f:
            css_content = f.read()
            st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.error("Arquivo CSS não encontrado na pasta 'styles/'")
    except Exception as e:
        st.error(f"Erro ao carregar CSS: {e}")
load_css()

# Carregar categorias do JSON com encoding UTF-8
@st.cache_data
def load_categories():
    try:
        with open(categories_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except UnicodeDecodeError:
        # Fallback para latin-1 se UTF-8 falhar
        with open(categories_path, 'r', encoding='latin-1') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Erro ao carregar categorias: {e}")
        return {}
categories = load_categories()

def extract_text_from_pdf(uploaded_file):
    """Extrai texto de arquivo PDF"""
    try:
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        st.error(f"Erro ao extrair texto do PDF: {e}")
        return ""

def analyze_sentiment(texto):
    """Analisa o sentimento do texto e retorna informações detalhadas"""
    try:
        blob = TextBlob(texto)
        if any(palavra in texto.lower() for palavra in ['é', 'á', 'ã', 'ç', 'õ']):
            texto_ingles = str(blob.translate(to='en'))
            blob = TextBlob(texto_ingles)
    except:
        blob = TextBlob(texto)
    
    sentiment = blob.sentiment
    polarity = sentiment.polarity
    subjectivity = sentiment.subjectivity
    
    # Classificação detalhada da polaridade
    if polarity > 0.3:
        sentiment_label = "Muito Positivo"
        sentiment_emoji = "😊"
        sentiment_color = "#2ecc71"
        sentiment_description = "Fortemente positivo"
    elif polarity > 0.1:
        sentiment_label = "Positivo"
        sentiment_emoji = "🙂"
        sentiment_color = "#27ae60"
        sentiment_description = "Levemente positivo"
    elif polarity > -0.1:
        sentiment_label = "Neutro"
        sentiment_emoji = "😐"
        sentiment_color = "#f39c12"
        sentiment_description = "Equilibrado/Neutro"
    elif polarity > -0.3:
        sentiment_label = "Negativo"
        sentiment_emoji = "🙁"
        sentiment_color = "#e67e22"
        sentiment_description = "Levemente negativo"
    else:
        sentiment_label = "Muito Negativo"
        sentiment_emoji = "😞"
        sentiment_color = "#e74c3c"
        sentiment_description = "Fortemente negativo"
    
    return {
        'polarity': polarity,
        'subjectivity': subjectivity,
        'sentiment_label': sentiment_label,
        'sentiment_emoji': sentiment_emoji,
        'sentiment_color': sentiment_color,
        'sentiment_description': sentiment_description
    }

def analyze_categories(texto, categories):
    """Analisa as categorias no texto"""
    texto_limpo = re.sub(r'[^\w\s]', '', texto.lower())
    scores = {categoria: 0 for categoria in categories.keys()}
    total_palavras_chave = 0
    
    for categoria, palavras_chave in categories.items():
        for palavra in palavras_chave:
            pattern = r'\b' + re.escape(palavra) + r'\b'
            matches = re.findall(pattern, texto_limpo)
            scores[categoria] += len(matches)
            total_palavras_chave += len(matches)
    
    return scores, total_palavras_chave

def calculate_percentages(scores):
    """Calcula percentuais baseados nos scores"""
    total_score = sum(scores.values())
    percentuais = {}
    
    for categoria, score in scores.items():
        if total_score > 0:
            percentuais[categoria] = (score / total_score) * 100
        else:
            percentuais[categoria] = 0
    
    return percentuais

def calculate_axes(percentuais):
    """Calcula os eixos conceituais"""
    pensamento_total = percentuais['Pensamento Subjetivo'] + percentuais['Pensamento Objetivo']
    acao_total = percentuais['Ação Comportamental'] + percentuais['Ação Prática']
    
    subjetividade_total = percentuais['Pensamento Subjetivo'] + percentuais['Ação Comportamental']
    objetividade_total = percentuais['Pensamento Objetivo'] + percentuais['Ação Prática']
    
    # Normalizar para 100% cada eixo
    if pensamento_total + acao_total > 0:
        pensamento_percent = (pensamento_total / (pensamento_total + acao_total)) * 100
        acao_percent = (acao_total / (pensamento_total + acao_total)) * 100
    else:
        pensamento_percent = acao_percent = 50
        
    if subjetividade_total + objetividade_total > 0:
        subjetivo_percent = (subjetividade_total / (subjetividade_total + objetividade_total)) * 100
        objetivo_percent = (objetividade_total / (subjetividade_total + objetividade_total)) * 100
    else:
        subjetivo_percent = objetivo_percent = 50
    
    return {
        'pensamento': pensamento_percent,
        'acao': acao_percent,
        'subjetivo': subjetivo_percent,
        'objetivo': objetivo_percent
    }


def generate_insights(sentiment_info, axes):
    """Gera insights baseados na análise"""
    insights = []
    polarity = sentiment_info['polarity']
    subjectivity = sentiment_info['subjectivity']
    
    # Insights baseados nos eixos
    if axes['pensamento'] > 70:
        insights.append("🧠 **Texto reflexivo**: Predominância de elementos de pensamento e análise")
    elif axes['acao'] > 70:
        insights.append("⚡ **Texto ativo**: Foco em ações, comportamentos e resultados")
    else:
        insights.append("⚖️ **Equilíbrio reflexão-ação**: Balanceamento entre pensar e agir")
    
    if axes['subjetivo'] > 70:
        insights.append("🎭 **Abordagem subjetiva**: Ênfase em experiências pessoais, emoções e perspectivas individuais")
    elif axes['objetivo'] > 70:
        insights.append("📐 **Abordagem objetiva**: Foco em fatos, dados e análise imparcial")
    else:
        insights.append("🔄 **Perspectiva integrada**: Combina elementos subjetivos e objetivos")
    
    # Insights baseados no sentimento
    if polarity > 0.3:
        insights.append("✅ **Tom positivo**: Linguagem otimista e construtiva")
    elif polarity < -0.3:
        insights.append("⚠️ **Tom crítico**: Linguagem cautelosa ou negativa")
    else:
        insights.append("🔍 **Tom neutro**: Abordagem equilibrada e factual")
    
    # Insights baseados na subjetividade
    if subjectivity > 0.7:
        insights.append("💭 **Alta subjetividade**: Forte presença de opiniões e perspectivas pessoais")
    elif subjectivity < 0.3:
        insights.append("📊 **Baixa subjetividade**: Linguagem factual e impessoal")
    
    return insights

st.title("Análise de Sentimento")

st.write("""
## Análise de Sentimento

Técnica que identifica e extrai opiniões, emoções e sentimentos expressos em texto.

### Métodos comuns:
- **Análise léxica**: Baseada em dicionários de palavras
- **Machine Learning**: Modelos supervisionados
- **Deep Learning**: Redes neurais e transformers

### Aplicações:
- Monitoramento de redes sociais
- Análise de reviews de produtos
- Pesquisa de mercado
""")

# Botões de upload e limpar texto
col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    uploaded_file = st.file_uploader("📁 Upload texto", type=['txt', 'pdf'], 
                                   help="Carregue arquivos .txt ou .pdf")

with col2:
    if st.button("🗑️ Limpar texto"):
        st.session_state.texto_analise = ""
        st.rerun()

# Processar arquivo carregado
if uploaded_file is not None:
    if uploaded_file.type == "text/plain":
        # Arquivo TXT
        texto_carregado = str(uploaded_file.read(), "utf-8")
        st.session_state.texto_analise = texto_carregado
    elif uploaded_file.type == "application/pdf":
        # Arquivo PDF
        texto_carregado = extract_text_from_pdf(uploaded_file)
        st.session_state.texto_analise = texto_carregado

# Inicializar variável de texto na session_state se não existir
if 'texto_analise' not in st.session_state:
    st.session_state.texto_analise = ""

# Entrada do usuário
texto = st.text_area("Digite o texto para análise:", 
                     value=st.session_state.texto_analise,
                     height=200, 
                     placeholder="Cole ou digite aqui qualquer texto (artigos, discursos, redações, relatórios, etc.)...")

with col3:
    analyze_button = st.button("🔍 Analisar Texto")

if analyze_button:
    if not texto:
        st.warning("Por favor, insira um texto para análise.")
    else:
        # 1. ANÁLISE DE SENTIMENTO
        st.header("📊 Análise de Sentimento")
        
        sentiment_info = analyze_sentiment(texto)
        polarity = sentiment_info['polarity']
        subjectivity = sentiment_info['subjectivity']
        palavras_count = len(texto.split())
        
        # Métricas de sentimento
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            # Polaridade com classificação detalhada
            st.metric(
                f"Polaridade {sentiment_info['sentiment_emoji']}", 
                f"{polarity:.3f}", 
                sentiment_info['sentiment_label']
            )
            
        with col2:
            # Subjetividade
            if subjectivity > 0.7:
                nivel = "Alta"
                cor = "#e74c3c"
            elif subjectivity > 0.4:
                nivel = "Moderada"
                cor = "#f39c12"
            else:
                nivel = "Baixa"
                cor = "#2ecc71"
            st.metric("Subjetividade", f"{subjectivity:.3f}", nivel)
        
        with col3:
            st.metric("📝 Total de Palavras", palavras_count)
            
        with col4:
            # Classificação do sentimento
            st.metric(
                "Classificação", 
                sentiment_info['sentiment_label'],
                sentiment_info['sentiment_description']
            )
        
        # Escala de polaridade visual
        st.subheader("🎯 Escala de Polaridade")
        
        # Definir posição na escala baseada na polaridade
        scale_position = ((polarity + 1) / 2) * 100  # Converter de [-1,1] para [0,100]
        
        escala_html = f"""
        <div style="background: #ecf0f1; border-radius: 15px; padding: 5px; margin: 10px 0; position: relative;">
            <div style="display: flex; justify-content: space-between; padding: 0 10px; font-weight: bold;">
                <span style="color: #e74c3c;">😞 Muito Negativo</span>
                <span style="color: #f39c12;">😐 Neutro</span>
                <span style="color: #2ecc71;">😊 Muito Positivo</span>
            </div>
            <div style="background: linear-gradient(90deg, #e74c3c 0%, #f39c12 50%, #2ecc71 100%); 
                        border-radius: 10px; height: 20px; margin: 5px 0; position: relative;">
                <div style="position: absolute; top: -5px; left: {scale_position}%; transform: translateX(-50%); 
                            background: {sentiment_info['sentiment_color']}; width: 10px; height: 30px; 
                            border-radius: 5px; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);">
                </div>
            </div>
            <div style="text-align: center; font-weight: bold; color: {sentiment_info['sentiment_color']}; 
                        margin-top: 10px; font-size: 1.1rem;">
                {sentiment_info['sentiment_emoji']} {sentiment_info['sentiment_label']} - {sentiment_info['sentiment_description']}
            </div>
        </div>
        """
        st.markdown(escala_html, unsafe_allow_html=True)
        
        # Detalhamento das faixas de polaridade
        with st.expander("📋 Detalhes das Faixas de Polaridade"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("""
                **🔴 Negativo**
                - **Muito Negativo**: -1.0 a -0.3
                - **Negativo**: -0.3 a -0.1
                """)
                
            with col2:
                st.markdown("""
                **🟡 Neutro**
                - **Neutro**: -0.1 a +0.1
                """)
                
            with col3:
                st.markdown("""
                **🟢 Positivo**
                - **Positivo**: +0.1 a +0.3
                - **Muito Positivo**: +0.3 a +1.0
                """)
            
            st.info(f"**Polaridade atual**: {polarity:.3f} → **{sentiment_info['sentiment_label']}**")

        # 2. ANÁLISE DOS EIXOS CONCEITUAIS
        st.header("🎯 Análise dos Eixos Conceituais")
        
        scores, total_palavras_chave = analyze_categories(texto, categories)
        percentuais = calculate_percentages(scores)
        axes = calculate_axes(percentuais)

        # Exibição dos eixos
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🧠 Eixo Pensamento vs Ação")
            st.markdown(f"**Pensamento**: {axes['pensamento']:.1f}%")
            st.progress(axes['pensamento'] / 100)
            st.markdown(f"**Ação**: {axes['acao']:.1f}%")
            st.progress(axes['acao'] / 100)
            
            # Gráfico de pizza
            fig1, ax1 = plt.subplots(figsize=(6, 6))
            ax1.pie([axes['pensamento'], axes['acao']], 
                   labels=[f'Pensamento\n{axes["pensamento"]:.1f}%', f'Ação\n{axes["acao"]:.1f}%'],
                   colors=['#3498db', '#e74c3c'], autopct='%1.1f%%', startangle=90)
            ax1.axis('equal')
            st.pyplot(fig1)
        
        with col2:
            st.subheader("📊 Eixo Subjetivo vs Objetivo")
            st.markdown(f"**Subjetivo**: {axes['subjetivo']:.1f}%")
            st.progress(axes['subjetivo'] / 100)
            st.markdown(f"**Objetivo**: {axes['objetivo']:.1f}%")
            st.progress(axes['objetivo'] / 100)
            
            # Gráfico de pizza
            fig2, ax2 = plt.subplots(figsize=(6, 6))
            ax2.pie([axes['subjetivo'], axes['objetivo']], 
                   labels=[f'Subjetivo\n{axes["subjetivo"]:.1f}%', f'Objetivo\n{axes["objetivo"]:.1f}%'],
                   colors=['#9b59b6', '#2ecc71'], autopct='%1.1f%%', startangle=90)
            ax2.axis('equal')
            st.pyplot(fig2)

        # 3. MATRIZ CONCEITUAL COMPLETA
        st.header("🎯 Matriz Conceitual Completa")
        
        matriz_html = f"""
        <div class="concept-matrix">
            <div class="matrix-cell matrix-cell-subjective">
                <h4>🧠 Pensamento</h4>
                <h5>Subjetivo</h5>
                <div class="matrix-value">{percentuais['Pensamento Subjetivo']:.1f}%</div>
                <small>Emoções, intuições, sentimentos</small>
            </div>
            <div class="matrix-cell matrix-cell-objective">
                <h4>🧠 Pensamento</h4>
                <h5>Objetivo</h5>
                <div class="matrix-value">{percentuais['Pensamento Objetivo']:.1f}%</div>
                <small>Dados, lógica, fatos</small>
            </div>
            <div class="matrix-cell matrix-cell-behavioral">
                <h4>⚡ Ação</h4>
                <h5>Comportamental</h5>
                <div class="matrix-value">{percentuais['Ação Comportamental']:.1f}%</div>
                <small>Interações, relações, comunicação</small>
            </div>
            <div class="matrix-cell matrix-cell-practical">
                <h4>⚡ Ação</h4>
                <h5>Prática</h5>
                <div class="matrix-value">{percentuais['Ação Prática']:.1f}%</div>
                <small>Execução, resultados, eficiência</small>
            </div>
        </div>
        """
        st.markdown(matriz_html, unsafe_allow_html=True)

        # 4. INTERPRETAÇÃO E INSIGHTS
        st.header("💡 Insights e Interpretação")
        
        insights = generate_insights(sentiment_info, axes)
        for insight in insights:
            st.info(insight)

        # 5. RESUMO ESTATÍSTICO
        with st.expander("📋 Resumo Estatístico Detalhado"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Distribuição por Categoria")
                df_categorias = pd.DataFrame({
                    'Categoria': list(percentuais.keys()),
                    'Percentual': list(percentuais.values()),
                    'Ocorrências': list(scores.values())
                })
                st.dataframe(df_categorias, use_container_width=True)
            
            with col2:
                st.subheader("Métricas de Texto")
                densidade = f"{(total_palavras_chave/palavras_count*100):.1f}%" if palavras_count > 0 else "0%"
                df_metricas = pd.DataFrame({
                    'Metrica': ['Total de Palavras', 'Palavras-chave Encontradas', 'Densidade de Palavras-chave', 
                               'Sentimento', 'Subjetividade', 'Classificação'],
                    'Valor': [palavras_count, total_palavras_chave, densidade, 
                             f"{polarity:.3f}", f"{subjectivity:.3f}", sentiment_info['sentiment_label']]
                })
                st.dataframe(df_metricas, use_container_width=True)
            
            st.subheader("Detalhamento do Sentimento")
            st.markdown(f"""
            - **Valor da Polaridade**: {polarity:.3f}
            - **Classificação**: {sentiment_info['sentiment_label']}
            - **Descrição**: {sentiment_info['sentiment_description']}
            - **Subjetividade**: {subjectivity:.3f} ({'Alta' if subjectivity > 0.7 else 'Moderada' if subjectivity > 0.4 else 'Baixa'})
            """)
            
            st.subheader("Exemplos de Palavras Encontradas")
            palavras_encontradas = []
            for categoria, palavras_chave in categories.items():
                encontradas = [palavra for palavra in palavras_chave if re.search(r'\b' + palavra + r'\b', texto.lower())]
                if encontradas:
                    palavras_encontradas.append(f"**{categoria}**: {', '.join(encontradas[:5])}" + 
                                              ("..." if len(encontradas) > 5 else ""))
            
            for item in palavras_encontradas:
                st.write(item)

        # 6. RECOMENDAÇÕES
        with st.expander("💎 Recomendações Baseadas na Análise"):
            st.markdown("""
            **Para comunicação eficaz baseada no perfil do texto:**
            
            - **Texto muito subjetivo**: Considere adicionar dados concretos para maior credibilidade
            - **Texto muito objetivo**: Pode beneficiar-se de elementos humanos e emocionais
            - **Foco excessivo em pensamento**: Inclua exemplos práticos e aplicações
            - **Foco excessivo em ação**: Desenvolva mais a fundamentação teórica
            - **Tom muito negativo**: Balance com aspectos positivos e soluções
            - **Tom muito positivo**: Inclua considerações sobre desafios e limitações
            """)
