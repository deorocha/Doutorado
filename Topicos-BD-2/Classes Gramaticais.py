import streamlit as st
import spacy
from pathlib import Path
import pdfplumber
import pandas as pd
import plotly.express as px
from collections import Counter
import tempfile
import os

# Tenta encontrar a raiz do projeto: sobe até encontrar a pasta 'styles' ou 'images'
def find_project_root(current_path):
    # Sobe até encontrar a raiz (onde estão as pastas styles e images)
    for parent in [current_path] + list(current_path.parents):
        if (parent / "styles").exists() and (parent / "images").exists():
            return parent
    return current_path  # fallback

# Obtém o diretório atual do script
current_dir = Path(__file__).parent if "__file__" in locals() else Path.cwd()
project_root = find_project_root(current_dir)

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

st.title("📝 Marcação de Classes Gramaticais")

# Mover explicação para o topo
st.write("""
## Marcação de Classes Gramaticais (POS Tagging)

Técnica que atribui etiquetas gramaticais a cada palavra em um texto.

### Categorias comuns:
- **Substantivos** (NN): pessoas, lugares, coisas
- **Verbos** (VB): ações e estados
- **Adjetivos** (JJ): qualidades e características
- **Advérbios** (RB): modificação de verbos, adjetivos

### Aplicações:
- Análise sintática
- Tradução automática
- Correção gramatical
- Análise de estilo literário
""")

# Adicionar seção de upload de PDF
st.header("Análise de Arquivos PDF")

uploaded_file = st.file_uploader(
    "Carregue um arquivo PDF para análise gramatical",
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

def analyze_grammar(text):
    """Executa análise gramatical completa no texto"""
    doc = nlp(text)
    
    # Estatísticas básicas
    total_tokens = len(doc)
    sentences = list(doc.sents)
    total_sentences = len(sentences)
    
    # Contagem de classes gramaticais
    pos_counts = Counter(token.pos_ for token in doc)
    
    # Análise detalhada
    grammar_data = []
    for token in doc:
        if not token.is_space:
            grammar_data.append({
                "Texto": token.text,
                "Lemma": token.lemma_,
                "Classe Gramatical": token.pos_,
                "Tag Detalhada": token.tag_,
                "Dependência": token.dep_,
                "Forma": token.shape_,
                "É Alpha": token.is_alpha,
                "É Stopword": token.is_stop
            })
    
    return {
        "doc": doc,
        "stats": {
            "total_tokens": total_tokens,
            "total_sentences": total_sentences,
            "pos_counts": pos_counts
        },
        "grammar_data": grammar_data
    }

def create_visualizations(pos_counts):
    """Cria visualizações para as estatísticas gramaticais"""
    if pos_counts:
        df = pd.DataFrame({
            "Classe Gramatical": list(pos_counts.keys()),
            "Quantidade": list(pos_counts.values())
        })
        
        fig_bar = px.bar(
            df,
            x="Classe Gramatical",
            y="Quantidade",
            title="Distribuição de Classes Gramaticais",
            color="Classe Gramatical"
        )
        
        fig_pie = px.pie(
            df,
            values="Quantidade",
            names="Classe Gramatical",
            title="Proporção de Classes Gramaticais"
        )
        
        return fig_bar, fig_pie
    
    return None, None

# Tabelas de legenda para Classes Gramaticais e Dependências
POS_LEGEND = {
    "ADJ": "Adjetivo",
    "ADP": "Adposição",
    "ADV": "Advérbio",
    "AUX": "Verbo auxiliar",
    "CONJ": "Conjunção",
    "CCONJ": "Conjunção coordenativa",
    "DET": "Determinante",
    "INTJ": "Interjeição",
    "NOUN": "Substantivo",
    "NUM": "Numeral",
    "PART": "Partícula",
    "PRON": "Pronome",
    "PROPN": "Nome próprio",
    "PUNCT": "Pontuação",
    "SCONJ": "Conjunção subordinativa",
    "SYM": "Símbolo",
    "VERB": "Verbo",
    "X": "Outro",
    "SPACE": "Espaço"
}

DEP_LEGEND = {
    "acl": "Cláusula adnominal",
    "advcl": "Cláusula adverbial",
    "advmod": "Modificador adverbial",
    "amod": "Modificador adjetival",
    "appos": "Aposição",
    "aux": "Auxiliar",
    "case": "Caso",
    "cc": "Conjunção coordenativa",
    "ccomp": "Complemento clausal",
    "clf": "Classificador",
    "compound": "Composto",
    "conj": "Conjunção",
    "cop": "Cópula",
    "csubj": "Sujeito clausal",
    "dep": "Dependência não especificada",
    "det": "Determinante",
    "discourse": "Elemento discursivo",
    "dislocated": "Deslocado",
    "expl": "Expletivo",
    "fixed": "Expressão fixa",
    "flat": "Nome flat",
    "goeswith": "Goes with",
    "iobj": "Objeto indireto",
    "list": "Lista",
    "mark": "Marcador",
    "nmod": "Modificador nominal",
    "nsubj": "Sujeito nominal",
    "nummod": "Modificador numérico",
    "obj": "Objeto",
    "obl": "Oblíquo",
    "orphan": "Órfão",
    "parataxis": "Parataxe",
    "punct": "Pontuação",
    "reparandum": "Reparandum",
    "root": "Raiz",
    "vocative": "Vocativo",
    "xcomp": "Complemento clausal aberto"
}

if uploaded_file is not None:
    with st.spinner("Processando PDF..."):
        # Extrair texto
        text = extract_text_from_pdf(uploaded_file)
        
        if text:
            st.success("Texto extraído com sucesso!")
            
            # Analisar gramática
            analysis = analyze_grammar(text)
            
            # Mostrar estatísticas
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total de Palavras", analysis["stats"]["total_tokens"])
            with col2:
                st.metric("Total de Sentenças", analysis["stats"]["total_sentences"])
            with col3:
                st.metric("Classes Gramaticais Únicas", len(analysis["stats"]["pos_counts"]))
            
            # Visualizações - uma abaixo da outra
            st.subheader("Visualizações")
            fig_bar, fig_pie = create_visualizations(analysis["stats"]["pos_counts"])
            
            if fig_bar and fig_pie:
                st.plotly_chart(fig_bar, use_container_width=True)
                st.plotly_chart(fig_pie, use_container_width=True)
            
            # Tabela detalhada
            st.subheader("Análise Detalhada")
            df_grammar = pd.DataFrame(analysis["grammar_data"])
            st.dataframe(df_grammar, use_container_width=True)
            
            # Tabelas de legenda
            st.subheader("Legendas")
            col_legend1, col_legend2 = st.columns(2)
            
            with col_legend1:
                st.write("**Classes Gramaticais**")
                pos_legend_df = pd.DataFrame([
                    {"Sigla": sigla, "Significado": significado} 
                    for sigla, significado in POS_LEGEND.items()
                ])
                st.dataframe(pos_legend_df, use_container_width=True, height=400)
            
            with col_legend2:
                st.write("**Dependências Sintáticas**")
                dep_legend_df = pd.DataFrame([
                    {"Sigla": sigla, "Significado": significado} 
                    for sigla, significado in DEP_LEGEND.items()
                ])
                st.dataframe(dep_legend_df, use_container_width=True, height=400)
            
            # Download dos resultados
            st.subheader("Exportar Resultados")
            csv_data = df_grammar.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download como CSV",
                data=csv_data,
                file_name="analise_gramatical.csv",
                mime="text/csv"
            )
        else:
            st.error("Não foi possível extrair texto do PDF")
