import streamlit as st
import spacy
from spacy import displacy
import pandas as pd
from pathlib import Path

# Obtém o diretório raiz do projeto (onde está o app.py)
current_dir = Path(__file__).parent if "__file__" in locals() else Path.cwd()
project_root = current_dir.parent  # Sobe um nível para a pasta raiz

# Constrói caminhos absolutos para os arquivos
#css_path = project_root / "styles" / "styles.css"
css_path = "./styles/styles.css"

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

st.title("🔗 Análise de Dependências")

@st.cache_resource
def load_spacy_model():
    try:
        # Tenta carregar o modelo grande em português
        return spacy.load("pt_core_news_lg")
    except OSError:
        try:
            # Se falhar, tenta o modelo pequeno em português
            st.info("Usando modelo pt_core_news_sm (mais leve)")
            return spacy.load("pt_core_news_sm")
        except OSError:
            try:
                # Se falhar, tenta o modelo em inglês
                st.info("Modelo português não disponível. Usando modelo em inglês...")
                return spacy.load("en_core_web_sm")
            except OSError:
                # Último recurso: modelo mínimo
                st.warning("Usando modelo básico do spaCy (funcionalidades limitadas)")
                return spacy.blank("pt")

nlp = load_spacy_model()

st.write("""
## Análise de Dependências

Técnica que identifica relações sintáticas entre palavras em uma frase.

### Tipos de relações:
- **Sujeito**: Relação entre verbo e sujeito
- **Objeto**: Relação entre verbo e objeto
- **Modificador**: Adjetivos que modificam substantivos
- **Complemento**: Elementos que completam o sentido

### Aplicações:
- Análise sintática profunda
- Extração de informação estruturada
- Sistemas de perguntas e respostas
- Análise de sentimentos contextual
""")

# Dicionários com as legendas
dependency_descriptions = {
    "acl": "Cláusula adnominal modificadora",
    "acomp": "Complemento do adjetivo",
    "advcl": "Cláusula adverbial",
    "advmod": "Modificador adverbial",
    "amod": "Modificador adnominal (adjetivo)",
    "appos": "Aposição",
    "attr": "Atributo",
    "aux": "Verbo auxiliar",
    "auxpass": "Verbo auxiliar na voz passiva",
    "case": "Caso (preposição, posposição)",
    "cc": "Conjunção coordenativa",
    "ccomp": "Cláusula completiva",
    "compound": "Composto",
    "conj": "Conjunto",
    "cop": "Verbo de ligação (cópula)",
    "csubj": "Sujeito clausal",
    "csubjpass": "Sujeito clausal passivo",
    "dative": "Objeto dativo",
    "dep": "Dependência não classificada",
    "det": "Determinante",
    "dobj": "Objeto direto",
    "expl": "Pronome expletivo",
    "intj": "Interjeição",
    "mark": "Marcador (conjunção subordinativa)",
    "meta": "Meta-informação",
    "neg": "Modificador de negação",
    "nmod": "Modificador nominal",
    "npadvmod": "Modificador adverbial nominal",
    "nsubj": "Sujeito nominal",
    "nsubjpass": "Sujeito nominal passivo",
    "nummod": "Modificador numérico",
    "obl": "Argumento oblíquo (complemento nominal ou adverbial)",
    "oprd": "Predicativo do objeto",
    "parataxis": "Parataxe",
    "pcomp": "Complemento de preposição",
    "pobj": "Objeto de preposição",
    "poss": "Modificador possessivo",
    "preconj": "Preconjuntivo",
    "predet": "Pré-determinante",
    "prep": "Modificador preposicional",
    "prt": "Partícula verbal",
    "punct": "Pontuação",
    "quantmod": "Modificador de quantificador",
    "relcl": "Cláusula relativa",
    "root": "Raiz (verbo principal)",
    "xcomp": "Cláusula complementar aberta"
}

pos_descriptions = {
    "ADJ": "Adjetivo",
    "ADP": "Adposição (preposição, posposição)",
    "ADV": "Advérbio",
    "AUX": "Verbo auxiliar",
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
    "X": "Outro"
}

text = "No Brasil, investigamos os comentários para compreender a opinião pública no Youtube."
text_input = st.text_input("Digite algum texto 👇", text)

if text_input:
    doc = nlp(text_input)
    
    # Render Dependency Parse
    dep_html = displacy.render(doc, style="dep", jupyter=False)

    if st.button('Analisar dependências', type="primary"):
        st.header("")
        st.write(dep_html, unsafe_allow_html=True)
        
        # Adicionar as tabelas de legenda
        st.header("Legenda das Dependências")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("### Relações de Dependência")
            dependency_data = []
            for dep, description in dependency_descriptions.items():
                dependency_data.append({"Tag": dep, "Descrição": description})
            
            dependency_df = pd.DataFrame(dependency_data)
            st.dataframe(dependency_df, use_container_width=True, hide_index=True)
        
        with col2:
            st.write("### Partes do Discurso")
            pos_data = []
            for pos, description in pos_descriptions.items():
                pos_data.append({"Tag": pos, "Descrição": description})
            
            pos_df = pd.DataFrame(pos_data)
            st.dataframe(pos_df, use_container_width=True, hide_index=True)
