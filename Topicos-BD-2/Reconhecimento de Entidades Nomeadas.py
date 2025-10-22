import streamlit as st
import spacy 
from spacy import displacy 
import pandas as pd
from pathlib import Path

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

css_path = project_root / "styles" / "styles.css"

@st.cache_resource
def load_spacy_model(model_name):
    try:
        return spacy.load(model_name)
    except OSError:
        st.error(f"Modelo {model_name} não encontrado. Instale com: python -m spacy download {model_name}")
        return None
    except Exception as e:
        st.error(f"Erro ao carregar modelo: {e}")
        return None

nlp = load_spacy_model("pt_core_news_lg")

# Verificar se o modelo foi carregado com sucesso
if nlp is None:
    st.warning("""
    ⚠️ **Modelo não carregado**
    
    Para usar esta funcionalidade, você precisa:
    1. Instalar o modelo em português do spaCy:
    ```bash
    python -m spacy download pt_core_news_lg
    ```
    2. Reiniciar o aplicativo
    """)
    st.stop()

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

st.title("🔍 Reconhecimento de Entidades Nomeadas (NER)")

st.write("""
## O que é NER?

O Reconhecimento de Entidades Nomeadas (NER) é uma técnica de Processamento 
de Linguagem Natural que identifica e classifica entidades mencionadas em texto.

### Tipos comuns de entidades:

- **Pessoas**: Nomes de indivíduos
- **Organizações**: Empresas, instituições
- **Locais**: Cidades, países, endereços
- **Datas**: Datas específicas
- **Valores monetários**: Quantias em dinheiro

### Aplicações:
- Extração de informação
- Análise de documentos
- Sistemas de busca inteligente
""")

# Dicionário com as legendas das entidades
entity_descriptions = {
    "PER": "Pessoa - Nomes de pessoas, personagens",
    "LOC": "Local - Nomes de lugares, países, cidades, regiões",
    "ORG": "Organização - Empresas, instituições, times",
    "MISC": "Miscelânea - Outras entidades que não se encaixam nas categorias acima",
    "EVENT": "Evento - Nomes de eventos históricos, conferências, competições",
    "PRODUCT": "Produto - Objetos, veículos, alimentos, etc.",
    "DATE": "Data - Datas, períodos, horários",
    "TIME": "Tempo - Expressões temporais",
    "MONEY": "Valor Monetário - Quantias em dinheiro",
    "CARDINAL": "Cardinal - Números que não são datas",
    "ORDINAL": "Ordinal - Primeiro, segundo, etc.",
    "QUANTITY": "Quantidade - Medidas, pesos, distâncias",
    "FAC": "Instalação - Edifícios, aeroportos, estradas",
    "GPE": "Entidade Geopolítica - Países, cidades, estados",
    "LANGUAGE": "Idioma - Nomes de línguas",
    "LAW": "Lei - Nomes de leis, documentos legais",
    "WORK_OF_ART": "Obra de Arte - Títulos de livros, músicas, filmes"
}

text = "No Brasil, a Anatel investigou os comentários feitos no Twitter e no Youtube sobre o Papa."
text_input = st.text_input("Digite algum texto 👇", text)

# Processar texto apenas se o modelo estiver carregado
if nlp is not None:
    doc = nlp(text_input)
    
    if st.button('Analisar Entidades', type="primary"):
        # Render NER
        ner_html = displacy.render(doc, style="ent", jupyter=False)
        
        st.header("")
        st.write(ner_html, unsafe_allow_html=True)
        
        # Adicionar a tabela de legenda
        st.header("Legenda das Entidades")
        
        # Criar DataFrame com as legendas
        entity_data = []
        for entity, description in entity_descriptions.items():
            entity_data.append({"Tag": entity, "Descrição": description})
        
        entity_df = pd.DataFrame(entity_data)
        st.dataframe(entity_df, use_container_width=True, hide_index=True)
        
        # Adicionar informações extras sobre as entidades encontradas
        if doc.ents:
            st.subheader("Entidades Encontradas no Texto")
            found_entities = []
            for ent in doc.ents:
                found_entities.append({
                    "Texto": ent.text,
                    "Tag": ent.label_,
                    "Descrição": entity_descriptions.get(ent.label_, "Desconhecida"),
                    "Posição": f"{ent.start_char}-{ent.end_char}"
                })
            
            found_df = pd.DataFrame(found_entities)
            st.dataframe(found_df, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma entidade nomeada foi encontrada no texto.")
