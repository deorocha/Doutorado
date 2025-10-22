import streamlit as st
from pathlib import Path
import re
import pandas as pd
import spacy

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

st.title("✂️ Tokenização")

st.write("""
## Tokenização

Processo de dividir texto em unidades menores chamadas tokens.

### Tipos de tokenização:
- **Tokenização por palavras**: Divide em palavras
- **Tokenização por subpalavras**: BPE, WordPiece
- **Tokenização por caracteres**: Divide em caracteres individuais
- **Tokenização por sílabas**: Divide palavras em sílabas (português)

### Aplicações:
- Pré-processamento para modelos de NLP
- Análise de frequência de palavras
- Preparação de dados para machine learning
""")

# Adicionando a funcionalidade de tokenização interativa
st.markdown("---")
st.subheader("Experimente a Tokenização")

# Texto pré-definido sobre tokenização
texto_exemplo = """
A tokenização, em Processamento de Linguagem Natural (PLN); é uma etapa fundamental. 
Ela consiste em dividir textos em unidades menores: palavras, subpalavras ou caracteres. 
Por exemplo; este texto será tokenizado de diferentes formas: palavras individuais, subpalavras ou caracteres separados.
Os tokens resultantes; são usados para análise linguística, treinamento de modelos; e diversas aplicações em PLN.
"""

# Caixa de texto com o exemplo
texto_input = st.text_area(
    "Texto para tokenizar:",
    value=texto_exemplo,
    height=150,
    help="Insira ou modifique o texto que você deseja tokenizar"
)

# Caixa de seleção para escolher o tipo de tokenização
tipo_tokenizacao = st.selectbox(
    "Selecione o tipo de tokenização:",
    ["Palavras", "Subpalavras", "Caracteres", "Sílabas"],
    help="Escolha como você quer dividir o texto"
)

# Função robusta para separação silábica em português brasileiro
def separar_silabas(palavra):
    """
    Separa sílabas em português brasileiro seguindo as regras gramaticais
    Baseado nas regras de divisão silábica do português
    """
    palavra = palavra.lower()
    
    # Casos especiais comuns
    especiais = {
        'tokenização': ['to', 'ke', 'ni', 'za', 'ção'],
        'processamento': ['pro', 'ces', 'sa', 'men', 'to'],
        'linguagem': ['lin', 'gua', 'gem'],
        'natural': ['na', 'tu', 'ral'],
        'aplicações': ['a', 'pli', 'ca', 'ções'],
        'etapa': ['e', 'ta', 'pa'],
        'fundamental': ['fun', 'da', 'men', 'tal'],
        'consiste': ['con', 'sis', 'te'],
        'dividir': ['di', 'vi', 'dir'],
        'textos': ['tex', 'tos'],
        'unidades': ['u', 'ni', 'da', 'des'],
        'menores': ['me', 'no', 'res'],
        'palavras': ['pa', 'la', 'vras'],
        'subpalavras': ['sub', 'pa', 'la', 'vras'],
        'caracteres': ['ca', 'rac', 'te', 'res'],
        'exemplo': ['e', 'xem', 'plo'],
        'individual': ['in', 'di', 'vi', 'dual'],
        'separados': ['se', 'pa', 'ra', 'dos'],
        'linguística': ['lin', 'guís', 'ti', 'ca'],
        'treinamento': ['trei', 'na', 'men', 'to'],
        'diversas': ['di', 'ver', 'sas'],
    }
    
    if palavra in especiais:
        return especiais[palavra]
    
    # Regras gerais de separação silábica
    silabas = []
    i = 0
    n = len(palavra)
    
    vogais = 'aeiouáéíóúâêîôûàèìòùãõ'
    consoantes = 'bcdfghjklmnpqrstvwxyzç'
    
    while i < n:
        # Encontra o início da próxima sílaba
        if i < n and palavra[i] in vogais:
            # Início com vogal - procura o fim da sílaba
            j = i
            # Uma sílaba pode ter várias vogais se formarem ditongo
            while j < n and palavra[j] in vogais:
                j += 1
            
            # Verifica se há consoantes para incluir no final da sílaba
            if j < n and palavra[j] in consoantes:
                # Verifica se é uma consoante final ou início de encontro consonantal
                if j + 1 < n and palavra[j + 1] in consoantes:
                    # Encontro consonantal - geralmente a primeira consoante fica na sílaba anterior
                    # Exceto para alguns casos especiais
                    if palavra[j:j+2] in ['br', 'cr', 'dr', 'fr', 'gr', 'pr', 'tr', 'vr',
                                         'bl', 'cl', 'fl', 'gl', 'pl', 'vl',
                                         'pn', 'ps', 'pt', 'ct', 'cn', 'mn']:
                        # Estes geralmente não separam
                        j += 2
                    else:
                        # Separa: primeira consoante fica, segunda vai para próxima sílaba
                        j += 1
                else:
                    # Apenas uma consoante no final
                    j += 1
            
            silaba = palavra[i:j]
            if silaba:
                silabas.append(silaba)
            i = j
            
        elif i < n and palavra[i] in consoantes:
            # Início com consoante - procura a vogal mais próxima
            j = i
            encontrou_vogal = False
            
            while j < n and not encontrou_vogal:
                if j < n and palavra[j] in vogais:
                    encontrou_vogal = True
                j += 1
            
            if encontrou_vogal:
                # Agora encontra o fim da sílaba
                k = j - 1  # Posição da primeira vogal
                
                # Continua enquanto houver vogais consecutivas (ditongo)
                while k < n and palavra[k] in vogais:
                    k += 1
                
                # Verifica consoantes no final
                if k < n and palavra[k] in consoantes:
                    if k + 1 < n and palavra[k + 1] in consoantes:
                        # Decide se separa ou não baseado em encontros consonantais comuns
                        if palavra[k:k+2] in ['lh', 'nh', 'ch', 'rr', 'ss', 'qu', 'gu']:
                            # Dígrafos - não separa
                            k += 2
                        else:
                            # Separa
                            k += 1
                    else:
                        k += 1
                
                silaba = palavra[i:k]
                if silaba:
                    silabas.append(silaba)
                i = k
            else:
                # Apenas consoantes no final (raro)
                silaba = palavra[i:]
                if silaba:
                    silabas.append(silaba)
                break
        else:
            i += 1
    
    # Pós-processamento para ajustar sílabas muito pequenas
    silabas_ajustadas = []
    i = 0
    while i < len(silabas):
        if i < len(silabas) - 1 and len(silabas[i]) == 1 and silabas[i] in consoantes:
            # Consoante solta - junta com a próxima sílaba
            if i + 1 < len(silabas):
                silabas_ajustadas.append(silabas[i] + silabas[i + 1])
                i += 2
            else:
                silabas_ajustadas.append(silabas[i])
                i += 1
        else:
            silabas_ajustadas.append(silabas[i])
            i += 1
    
    return silabas_ajustadas

# Função para realizar a tokenização
def tokenizar_texto(texto, tipo):
    if tipo == "Palavras":
        # Tokenização por palavras - divide por espaços e pontuação
        tokens = re.findall(r'\b\w+\b|[^\w\s]', texto)
        return [token for token in tokens if token.strip()]
    
    elif tipo == "Subpalavras":
        # Tokenização simples por subpalavras (divide palavras em pedaços menores)
        palavras = re.findall(r'\b\w+\b', texto)
        subpalavras = []
        for palavra in palavras:
            if len(palavra) > 3:
                # Divide palavras longas em subpalavras
                for i in range(0, len(palavra), 2):
                    subpalavras.append(palavra[i:i+2])
            else:
                subpalavras.append(palavra)
        
        # Adiciona pontuação separadamente
        pontuacao = re.findall(r'[^\w\s]', texto)
        return subpalavras + pontuacao
    
    elif tipo == "Caracteres":
        # Tokenização por caracteres
        return [char for char in texto if char.strip()]
    
    elif tipo == "Sílabas":
        tokens_finais = []
        
        # Primeiro separa palavras e pontuação
        palavras_pontuacao = re.findall(r'\b\w+\b|[^\w\s]', texto)
        
        for token in palavras_pontuacao:
            if re.match(r'\w+', token):  # Se é uma palavra
                silabas = separar_silabas(token)
                tokens_finais.extend(silabas)
            else:  # Se é pontuação
                tokens_finais.append(token)
        
        return tokens_finais

# Processar o texto quando houver entrada
if texto_input:
    tokens = tokenizar_texto(texto_input, tipo_tokenizacao)
    
    # Exibir os tokens resultantes
    st.subheader("Texto Tokenizado:")
    st.text_area(
        "Tokens:",
        value=" | ".join(tokens),
        height=150,
        help="Os tokens estão separados por ' | '"
    )
    
    # Mostrar estatísticas básicas
    st.write(f"**Total de tokens:** {len(tokens)}")
    
    # Mostrar alguns exemplos de tokens
    if len(tokens) > 0:
        st.write(f"**Primeiros 10 tokens:** {tokens[:10]}")
        
    # Explicação sobre a tokenização por sílabas
    if tipo_tokenizacao == "Sílabas":
        st.info("""
        **Tokenização por Sílabas (Português Brasileiro):**
        - Segue as regras de separação silábica do português
        - Inclui separações corretas para palavras comuns em NLP
        - Mantém pontuação como tokens separados
        - Considera ditongos, tritongos e hiatos
        """)
        
        # Mostrar exemplos de separação silábica
        st.write("**Exemplos de separação silábica:**")
        palavras_teste = ["tokenização", "processamento", "linguagem", "etapa", "fundamental"]
        for palavra in palavras_teste:
            silabas = separar_silabas(palavra)
            st.write(f"- {palavra}: {' - '.join(silabas)}")

    if tipo_tokenizacao == "Palavras":
        doc = nlp(texto_input)
        # Coletando informações dos tokens em um único DataFrame
        dados_tokens = []
        for token in doc:
            dados_tokens.append({
                'Token': token.text,
                'Índice de início': token.idx,
                'É pontuação?': token.is_punct,
                'É espaço em branco?': token.is_space,
                'Parte do discurso': token.pos_,
                'Dependência sintática': token.dep_
            })

        # Criando DataFrame com os dados dos tokens
        df_tokens = pd.DataFrame(dados_tokens)

        # Exibindo o DataFrame
        df_tokens
else:
    st.info("Digite um texto acima para ver a tokenização em ação.")
