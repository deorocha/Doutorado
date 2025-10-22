import streamlit as st
from pathlib import Path
import pdfplumber
import spacy
import pandas as pd
import plotly.express as px
from collections import Counter
import tempfile
import os
import re

# Obtém o diretório raiz do projeto (onde está o app.py)
current_dir = Path(__file__).parent if "__file__" in locals() else Path.cwd()
project_root = current_dir.parent  # Sobe um nível para a pasta raiz

# Constrói caminhos absolutos para os arquivos
css_path = project_root / "styles" / "styles.css"

@st.cache_resource
def load_spacy_model():
    try:
        return spacy.load("pt_core_news_sm")
    except OSError:
        try:
            st.info("Modelo português não disponível. Usando modelo em inglês...")
            return spacy.load("en_core_web_sm")
        except OSError:
            st.warning("Usando modelo básico do spaCy (funcionalidades limitadas)")
            return spacy.blank("pt")

nlp = load_spacy_model()

# Carregar CSS externo com codificação correta
def load_css(css_path):
    try:
        with open(css_path, "r", encoding="utf-8") as f:
            css_content = f.read()
            st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.error("Arquivo CSS não encontrado na pasta 'styles/'")
    except Exception as e:
        st.error(f"Erro ao carregar CSS: {e}")
load_css(css_path)

st.title("📏 Detecção de Limites de Frases")

st.write("""
## Detecção de Limites de Frases

Técnica que identifica onde começam e terminam as frases em um texto.

### Desafios:
- **Abreviações**: "Dr." não deve quebrar a frase
- **Pontuação múltipla**: "!!!" ou "???"
- **Citações**: Frases dentro de aspas
- **Listas**: Itens numerados ou com marcadores

### Aplicações:
- Processamento de documentos longos
- Análise de discursos
- Preparação para outras tarefas de NLP
- Sumarização de texto
""")

# Adicionar seção de upload de PDF
st.header("Análise de Resumo em PDF")

uploaded_file = st.file_uploader(
    "Carregue um arquivo PDF para análise do resumo",
    type="pdf",
    help="Tamanho máximo: 200MB"
)

def extract_text_from_pdf(uploaded_file):
    """Extrai texto de um arquivo PDF carregado"""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name
        
        text = ""
        with pdfplumber.open(tmp_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        
        os.unlink(tmp_path)  # Remove arquivo temporário
        return text.strip()
    
    except Exception as e:
        st.error(f"Erro ao extrair texto do PDF: {e}")
        return None

def extract_abstract(text):
    """Extrai o resumo do texto do PDF usando padrões comuns"""
    # Padrões para identificar resumo em português e inglês
    patterns = [
        r'RESUMO\s*[\n\r]+(.*?)(?=\n\s*\n|\n\s*INTRODUÇÃO|\n\s*ABSTRACT|\n\s*1\s|\n\s*1\.|\Z)',
        r'ABSTRACT\s*[\n\r]+(.*?)(?=\n\s*\n|\n\s*INTRODUCTION|\n\s*RESUMO|\n\s*1\s|\n\s*1\.|\Z)',
        r'Resumo\s*[\n\r]+(.*?)(?=\n\s*\n|\n\s*Introdução|\n\s*Abstract|\n\s*1\s|\n\s*1\.|\Z)',
        r'Abstract\s*[\n\r]+(.*?)(?=\n\s*\n|\n\s*Introduction|\n\s*Resumo|\n\s*1\s|\n\s*1\.|\Z)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            abstract = match.group(1).strip()
            # Limpar o texto removendo múltiplos espaços e quebras de linha
            abstract = re.sub(r'\s+', ' ', abstract)
            return abstract
    
    # Se não encontrar por padrões, tentar pegar o primeiro parágrafo significativo
    paragraphs = re.split(r'\n\s*\n', text)
    for para in paragraphs:
        if len(para.strip()) > 100:  # Parágrafo com pelo menos 100 caracteres
            return para.strip()
    
    return None

def analyze_sentence_boundaries(text):
    """Analisa os limites de frases no texto"""
    doc = nlp(text)
    
    # Estatísticas das frases
    sentences = list(doc.sents)
    sentence_data = []
    
    for i, sent in enumerate(sentences, 1):
        sentence_text = sent.text.strip()
        words = [token.text for token in sent if not token.is_space]
        tokens = len(words)
        chars = len(sentence_text)
        
        sentence_data.append({
            "Nº": i,
            "Frase": sentence_text,
            "Palavras": tokens,
            "Caracteres": chars,
            "Terminador": sentence_text[-1] if sentence_text else ""
        })
    
    # Estatísticas gerais
    total_sentences = len(sentences)
    total_words = sum(len([token for token in sent if not token.is_space]) for sent in sentences)
    avg_words_per_sentence = total_words / total_sentences if total_sentences > 0 else 0
    avg_chars_per_sentence = sum(len(sent.text.strip()) for sent in sentences) / total_sentences if total_sentences > 0 else 0
    
    # Análise de terminadores de frases
    sentence_endings = Counter()
    for sent in sentences:
        if sent.text.strip():
            ending = sent.text.strip()[-1]
            sentence_endings[ending] += 1
    
    return {
        "sentence_data": sentence_data,
        "stats": {
            "total_sentences": total_sentences,
            "total_words": total_words,
            "avg_words_per_sentence": round(avg_words_per_sentence, 2),
            "avg_chars_per_sentence": round(avg_chars_per_sentence, 2),
            "sentence_endings": sentence_endings
        }
    }

def create_visualizations(analysis):
    """Cria visualizações para a análise de frases"""
    # Gráfico de distribuição de tamanho de frases
    sentence_lengths = [sent["Palavras"] for sent in analysis["sentence_data"]]
    
    fig_length = px.histogram(
        x=sentence_lengths,
        title="Distribuição de Palavras por Frase",
        labels={"x": "Número de Palavras", "y": "Quantidade de Frases"},
        nbins=10
    )
    
    # Gráfico de terminadores de frases
    endings_data = analysis["stats"]["sentence_endings"]
    if endings_data:
        fig_endings = px.pie(
            values=list(endings_data.values()),
            names=list(endings_data.keys()),
            title="Tipos de Terminadores de Frases"
        )
    else:
        fig_endings = None
    
    return fig_length, fig_endings

if uploaded_file is not None:
    with st.spinner("Processando PDF e analisando resumo..."):
        # Extrair texto
        text = extract_text_from_pdf(uploaded_file)
        
        if text:
            st.success("Texto extraído com sucesso!")
            
            # Extrair resumo
            abstract = extract_abstract(text)
            
            if abstract:
                st.success("Resumo identificado!")
                
                # Mostrar o resumo extraído
                st.subheader("Resumo Extraído")
                st.text_area("Texto do Resumo", abstract, height=150, key="abstract_text")
                
                # Analisar limites de frases
                analysis = analyze_sentence_boundaries(abstract)
                
                # Mostrar estatísticas
                st.subheader("Estatísticas do Resumo")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total de Frases", analysis["stats"]["total_sentences"])
                with col2:
                    st.metric("Total de Palavras", analysis["stats"]["total_words"])
                with col3:
                    st.metric("Média Palavras/Frase", analysis["stats"]["avg_words_per_sentence"])
                with col4:
                    st.metric("Média Caracteres/Frase", analysis["stats"]["avg_chars_per_sentence"])
                
                # Visualizações
                st.subheader("Visualizações")
                fig_length, fig_endings = create_visualizations(analysis)
                
                if fig_length:
                    st.plotly_chart(fig_length, use_container_width=True)
                
                if fig_endings:
                    st.plotly_chart(fig_endings, use_container_width=True)
                
                # Tabela detalhada de frases
                st.subheader("Análise Detalhada das Frases")
                df_sentences = pd.DataFrame(analysis["sentence_data"])
                st.dataframe(df_sentences, use_container_width=True)
                
                # Regras LLM aplicadas
                st.subheader("Regras de LLM para Detecção de Limites")
                
                col_rules1, col_rules2 = st.columns(2)
                
                with col_rules1:
                    st.write("**Regras Básicas:**")
                    st.markdown("""
                    - **Pontuação final**: `.`, `!`, `?` como indicadores primários
                    - **Contexto sintático**: Análise da estrutura gramatical
                    - **Abreviações**: Detecção de termos como "Dr.", "Prof.", etc.
                    - **Iniciais**: Nomes com iniciais (A. B. Silva)
                    """)
                
                with col_rules2:
                    st.write("**Regras Avançadas:**")
                    st.markdown("""
                    - **Citações**: Frases dentro de aspas e parênteses
                    - **Listas**: Itens numerados e marcadores
                    - **Padrões específicos**: Datas, URLs, emails
                    - **Contexto semântico**: Coerência temática entre frases
                    """)
                
                # Análise de padrões especiais
                st.subheader("Padrões Especiais Detectados")
                
                special_patterns = {
                    "Abreviações": r'\b(?:Dr|Prof|Sr|Sra|Exmo|Ilmo|etc|vs|aprox|pág)\.',
                    "Iniciais": r'\b[A-Z]\.\s*[A-Z]\.',
                    "Datas": r'\b\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b',
                    "Números decimais": r'\b\d+[,.]\d+\b'
                }
                
                pattern_results = {}
                for pattern_name, pattern in special_patterns.items():
                    matches = re.findall(pattern, abstract, re.IGNORECASE)
                    pattern_results[pattern_name] = len(matches)
                
                df_patterns = pd.DataFrame({
                    "Padrão": list(pattern_results.keys()),
                    "Ocorrências": list(pattern_results.values())
                })
                
                st.dataframe(df_patterns, use_container_width=True)
                
                # Download dos resultados
                st.subheader("Exportar Resultados")
                csv_data = df_sentences.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="📥 Download da Análise como CSV",
                    data=csv_data,
                    file_name="analise_limites_frases.csv",
                    mime="text/csv"
                )
                
            else:
                st.warning("Não foi possível identificar o resumo no documento. Analisando texto completo...")
                # Analisar o texto completo se não encontrar resumo
                analysis = analyze_sentence_boundaries(text[:2000])  # Limitar a 2000 caracteres
                
                # Mostrar estatísticas
                st.subheader("Estatísticas do Texto")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total de Frases", analysis["stats"]["total_sentences"])
                with col2:
                    st.metric("Total de Palavras", analysis["stats"]["total_words"])
                with col3:
                    st.metric("Média Palavras/Frase", analysis["stats"]["avg_words_per_sentence"])
                
                # Tabela com as primeiras frases
                st.subheader("Primeiras Frases do Texto")
                df_sentences = pd.DataFrame(analysis["sentence_data"][:10])  # Mostrar apenas as 10 primeiras
                st.dataframe(df_sentences, use_container_width=True)
        else:
            st.error("Não foi possível extrair texto do PDF")
