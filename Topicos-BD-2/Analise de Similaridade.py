import streamlit as st
from pathlib import Path
import pdfplumber
import spacy
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.manifold import TSNE
import numpy as np
import tempfile
import os
import re
from collections import Counter

# Obtém o diretório raiz do projeto (onde está o app.py)
current_dir = Path(__file__).parent if "__file__" in locals() else Path.cwd()
project_root = current_dir.parent  # Sobe um nível para a pasta raiz

# Constrói caminhos absolutos para os arquivos
css_path = project_root / "styles" / "styles.css"

@st.cache_resource
def load_spacy_model():
    try:
        # Carregar modelo com word vectors para similaridade semântica
        return spacy.load("pt_core_news_lg")
    except OSError:
        try:
            st.info("Modelo português grande não disponível. Tentando modelo pequeno...")
            return spacy.load("pt_core_news_sm")
        except OSError:
            try:
                st.info("Modelo português não disponível. Usando modelo em inglês...")
                return spacy.load("en_core_web_lg")
            except OSError:
                st.warning("Usando modelo básico do spaCy (similaridade limitada)")
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

st.title("📐 Análise de Similaridade Semântica")

st.write("""
## Análise de Similaridade Semântica

Técnica que mede o quão similares são dois textos considerando significado e contexto.

### Métodos:
- **Similaridade semântica**: Significado similar independente das palavras
- **Embeddings**: Representações vetoriais de texto
- **Transformers**: Modelos de linguagem contextual
- **TF-IDF + Cosine Similarity**: Análise vetorial tradicional

### Aplicações:
- Sistemas de recomendação
- Detecção de plágio
- Agrupamento de documentos
- Busca semântica
""")

# Adicionar seção de upload de PDFs
st.header("Análise de Similaridade entre PDFs")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Primeiro PDF")
    pdf_file1 = st.file_uploader(
        "Carregue o primeiro arquivo PDF",
        type="pdf",
        key="pdf1",
        help="Tamanho máximo: 200MB"
    )

with col2:
    st.subheader("Segundo PDF")
    pdf_file2 = st.file_uploader(
        "Carregue o segundo arquivo PDF",
        type="pdf",
        key="pdf2",
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

def preprocess_text(text):
    """Pré-processa o texto para análise"""
    # Limpar texto - remover múltiplos espaços e quebras de linha
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def calculate_semantic_similarity(text1, text2):
    """Calcula similaridade semântica entre dois textos"""
    # Usar spaCy para similaridade semântica
    doc1 = nlp(text1)
    doc2 = nlp(text2)
    
    # Similaridade usando embeddings do spaCy
    if doc1.has_vector and doc2.has_vector:
        spacy_similarity = doc1.similarity(doc2)
    else:
        spacy_similarity = None
    
    # Similaridade usando TF-IDF e cosine similarity
    vectorizer = TfidfVectorizer().fit_transform([text1, text2])
    vectors = vectorizer.toarray()
    cosine_sim = cosine_similarity(vectors[0:1], vectors[1:2])[0][0]
    
    return {
        "spacy_similarity": spacy_similarity,
        "cosine_similarity": cosine_sim,
        "doc1": doc1,
        "doc2": doc2
    }

def analyze_text_content(text1, text2):
    """Analisa o conteúdo dos textos"""
    doc1 = nlp(text1)
    doc2 = nlp(text2)
    
    # Estatísticas básicas
    stats1 = {
        "sentences": len(list(doc1.sents)),
        "tokens": len(doc1),
        "words": len([token for token in doc1 if token.is_alpha]),
        "unique_words": len(set(token.text.lower() for token in doc1 if token.is_alpha)),
        "avg_sentence_length": len(doc1) / max(len(list(doc1.sents)), 1)
    }
    
    stats2 = {
        "sentences": len(list(doc2.sents)),
        "tokens": len(doc2),
        "words": len([token for token in doc2 if token.is_alpha]),
        "unique_words": len(set(token.text.lower() for token in doc2 if token.is_alpha)),
        "avg_sentence_length": len(doc2) / max(len(list(doc2.sents)), 1)
    }
    
    # Análise de tópicos (palavras mais frequentes)
    words1 = [token.text.lower() for token in doc1 if token.is_alpha and not token.is_stop]
    words2 = [token.text.lower() for token in doc2 if token.is_alpha and not token.is_stop]
    
    freq1 = Counter(words1).most_common(10)
    freq2 = Counter(words2).most_common(10)
    
    return {
        "stats1": stats1,
        "stats2": stats2,
        "frequent_words1": freq1,
        "frequent_words2": freq2
    }

def create_similarity_visualizations(similarity_results, text_analysis):
    """Cria visualizações para a análise de similaridade"""
    # Gauge de similaridade
    fig_gauge = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = similarity_results["cosine_similarity"] * 100,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "Similaridade Semântica (%)"},
        delta = {'reference': 50},
        gauge = {
            'axis': {'range': [None, 100]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [0, 30], 'color': "lightcoral"},
                {'range': [30, 70], 'color': "lightyellow"},
                {'range': [70, 100], 'color': "lightgreen"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 90
            }
        }
    ))
    
    fig_gauge.update_layout(height=300)
    
    # Gráfico de comparação de estatísticas
    stats_df = pd.DataFrame({
        "Métrica": ["Sentenças", "Palavras", "Palavras Únicas", "Média Palavras/Sentença"],
        "Documento 1": [
            text_analysis["stats1"]["sentences"],
            text_analysis["stats1"]["words"],
            text_analysis["stats1"]["unique_words"],
            round(text_analysis["stats1"]["avg_sentence_length"], 2)
        ],
        "Documento 2": [
            text_analysis["stats2"]["sentences"],
            text_analysis["stats2"]["words"],
            text_analysis["stats2"]["unique_words"],
            round(text_analysis["stats2"]["avg_sentence_length"], 2)
        ]
    })
    
    fig_stats = px.bar(
        stats_df,
        x="Métrica",
        y=["Documento 1", "Documento 2"],
        title="Comparação de Estatísticas dos Documentos",
        barmode="group"
    )
    
    # Gráfico de palavras frequentes
    words_df1 = pd.DataFrame(text_analysis["frequent_words1"], columns=["Palavra", "Frequência"])
    words_df2 = pd.DataFrame(text_analysis["frequent_words2"], columns=["Palavra", "Frequência"])
    
    fig_words1 = px.bar(
        words_df1,
        x="Palavra",
        y="Frequência",
        title="Palavras Mais Frequentes - Documento 1",
        color="Frequência"
    )
    
    fig_words2 = px.bar(
        words_df2,
        x="Palavra",
        y="Frequência",
        title="Palavras Mais Frequentes - Documento 2",
        color="Frequência"
    )
    
    return fig_gauge, fig_stats, fig_words1, fig_words2

def create_semantic_space_visualization(text1, text2):
    """Cria visualização do espaço semântico"""
    # Dividir textos em sentenças para análise
    doc1 = nlp(text1)
    doc2 = nlp(text2)
    
    sentences1 = [sent.text for sent in doc1.sents][:10]  # Limitar a 10 sentenças
    sentences2 = [sent.text for sent in doc2.sents][:10]
    
    all_sentences = sentences1 + sentences2
    labels = ["Doc1"] * len(sentences1) + ["Doc2"] * len(sentences2)
    
    # Calcular embeddings (simplificado)
    if nlp.has_pipe("textcat"):
        vectors = []
        for sent in all_sentences:
            doc = nlp(sent)
            if doc.has_vector:
                vectors.append(doc.vector)
            else:
                # Fallback para TF-IDF se não houver embeddings
                vectors.append(np.zeros(100))
    else:
        # Usar TF-IDF como fallback
        vectorizer = TfidfVectorizer(max_features=100)
        vectors = vectorizer.fit_transform(all_sentences).toarray()
    
    # Reduzir dimensionalidade com t-SNE
    if len(vectors) > 1:
        tsne = TSNE(n_components=2, random_state=42, perplexity=min(5, len(vectors)-1))
        vectors_2d = tsne.fit_transform(vectors)
        
        fig_tsne = px.scatter(
            x=vectors_2d[:, 0],
            y=vectors_2d[:, 1],
            color=labels,
            title="Espaço Semântico - Similaridade entre Sentenças",
            labels={"x": "Dimensão 1", "y": "Dimensão 2"},
            color_discrete_map={"Doc1": "blue", "Doc2": "red"}
        )
        return fig_tsne
    return None

if pdf_file1 is not None and pdf_file2 is not None:
    with st.spinner("Processando PDFs e analisando similaridade..."):
        # Extrair textos
        text1 = extract_text_from_pdf(pdf_file1)
        text2 = extract_text_from_pdf(pdf_file2)
        
        if text1 and text2:
            st.success("Textos extraídos com sucesso!")
            
            # Pré-processar textos
            text1_clean = preprocess_text(text1)
            text2_clean = preprocess_text(text2)
            
            # Calcular similaridade
            similarity_results = calculate_semantic_similarity(text1_clean, text2_clean)
            
            # Analisar conteúdo
            text_analysis = analyze_text_content(text1_clean, text2_clean)
            
            # Mostrar resultados de similaridade
            st.header("Resultados da Similaridade Semântica")
            
            col_sim1, col_sim2, col_sim3 = st.columns(3)
            
            with col_sim1:
                if similarity_results["spacy_similarity"] is not None:
                    st.metric(
                        "Similaridade SpaCy", 
                        f"{similarity_results['spacy_similarity']:.2%}",
                        help="Baseada em embeddings semânticos do spaCy"
                    )
                else:
                    st.metric(
                        "Similaridade SpaCy",
                        "N/A",
                        help="Modelo não suporta similaridade semântica"
                    )
            
            with col_sim2:
                st.metric(
                    "Similaridade Cosseno (TF-IDF)",
                    f"{similarity_results['cosine_similarity']:.2%}",
                    help="Baseada em vetores TF-IDF e similaridade de cosseno"
                )
            
            with col_sim3:
                overall_similarity = (
                    similarity_results["spacy_similarity"] 
                    if similarity_results["spacy_similarity"] is not None 
                    else similarity_results["cosine_similarity"]
                )
                st.metric(
                    "Similaridade Geral",
                    f"{overall_similarity:.2%}",
                    delta=f"{overall_similarity - 0.5:.2%}" if overall_similarity else None,
                    delta_color="normal"
                )
            
            # Interpretação da similaridade
            st.subheader("Interpretação da Similaridade")
            
            similarity_levels = [
                (0.9, 1.0, "Muito Alta", "Os documentos são semanticamente muito similares"),
                (0.7, 0.9, "Alta", "Os documentos compartilham significados similares"),
                (0.5, 0.7, "Moderada", "Os documentos têm algumas similaridades"),
                (0.3, 0.5, "Baixa", "Os documentos são diferentes mas com algum overlap"),
                (0.0, 0.3, "Muito Baixa", "Os documentos são semanticamente distintos")
            ]
            
            for min_val, max_val, level, description in similarity_levels:
                if min_val <= overall_similarity < max_val:
                    st.info(f"**{level}**: {description}")
                    break
            
            # Visualizações
            st.header("Visualizações")
            fig_gauge, fig_stats, fig_words1, fig_words2 = create_similarity_visualizations(
                similarity_results, text_analysis
            )
            
            st.plotly_chart(fig_gauge, use_container_width=True)
            st.plotly_chart(fig_stats, use_container_width=True)
            
            col_words1, col_words2 = st.columns(2)
            with col_words1:
                st.plotly_chart(fig_words1, use_container_width=True)
            with col_words2:
                st.plotly_chart(fig_words2, use_container_width=True)
            
            # Espaço semântico
            st.subheader("Análise do Espaço Semântico")
            fig_tsne = create_semantic_space_visualization(text1_clean, text2_clean)
            if fig_tsne:
                st.plotly_chart(fig_tsne, use_container_width=True)
                st.caption("Visualização t-SNE mostrando a proximidade semântica entre sentenças dos dois documentos")
            
            # Detalhes técnicos
            st.header("Detalhes Técnicos")
            
            with st.expander("Métodos de Similaridade Utilizados"):
                st.markdown("""
                **1. Similaridade SpaCy (Embeddings)**
                - Usa representações vetoriais de palavras e documentos
                - Captura relações semânticas e contextuais
                - Baseado em modelos pré-treinados em grandes corpora
                
                **2. Similaridade de Cosseno (TF-IDF)**
                - Representa documentos como vetores TF-IDF
                - Calcula o cosseno do ângulo entre os vetores
                - Mede similaridade baseada em frequência de termos
                
                **3. Análise t-SNE**
                - Redução de dimensionalidade para visualização
                - Mostra proximidade semântica no espaço 2D
                - Agrupa sentenças semanticamente similares
                """)
            
            # Resumo executivo
            st.header("Resumo Executivo")
            
            col_sum1, col_sum2 = st.columns(2)
            
            with col_sum1:
                st.subheader("📊 Pontos Fortes da Similaridade")
                if overall_similarity > 0.7:
                    st.success("✅ Alta sobreposição temática")
                    st.success("✅ Contextos semânticos alinhados")
                    st.success("✅ Potencial para integração de conteúdo")
                elif overall_similarity > 0.4:
                    st.warning("⚠️ Similaridade moderada")
                    st.warning("⚠️ Alguns temas em comum")
                    st.warning("⚠️ Oportunidade para conexões")
                else:
                    st.error("❌ Baixa similaridade semântica")
                    st.error("❌ Contextos distintos")
                    st.error("❌ Foco em temas diferentes")
            
            with col_sum2:
                st.subheader("🎯 Recomendações")
                if overall_similarity > 0.7:
                    st.info("• Considerar fusão ou integração dos conteúdos")
                    st.info("• Desenvolver síntese conjunta")
                    st.info("• Explorar complementaridades")
                elif overall_similarity > 0.4:
                    st.info("• Identificar pontos de conexão específicos")
                    st.info("• Desenvolver comparação crítica")
                    st.info("• Explorar diferenças como oportunidades")
                else:
                    st.info("• Manter como documentos distintos")
                    st.info("• Desenvolver análises separadas")
                    st.info("• Considerar contextos de uso específicos")
            
        else:
            st.error("Não foi possível extrair texto de um ou ambos os PDFs")
else:
    if pdf_file1 or pdf_file2:
        st.warning("⚠️ Por favor, carregue ambos os arquivos PDF para análise")
