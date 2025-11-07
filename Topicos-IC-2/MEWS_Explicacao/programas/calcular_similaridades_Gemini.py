import pandas as pd
import spacy
from spacy.lang.pt import Portuguese

# --- 1. Definição das Variáveis Padrão ---
VARIAVEIS_PADRAO = {
    'fundamento_padrao': "Em pacientes estáveis, os sistemas homeostáticos estão compensados. A verificação em intervalos padronizados estabelece uma linha de base individual e permite a detecção de desvios sutis dessa linha de base, que são os primeiros sinais de uma possível deterioração. Intervalos superiores a 8 horas podem não capturar uma tendência de agravamento que ainda é lenta e silenciosa.",
    'evidencias_padrao': "O Programa Nacional de Segurança do Paciente (PNSP) e protocolos baseados na RDC 36/2013 recomendam a monitorização vital periódica como a espinha dorsal da detecção precoce. Estudos de validação do MEWS mostram que a frequência de coleta de dados impacta diretamente sua sensibilidade. A faixa de 4-8h é considerada o equilíbrio ideal entre segurança e alocação eficiente de recursos para pacientes de baixo risco.",
    'riscos_padrao': "A omissão ou a extensão excessiva do intervalo permitiria que uma deterioração inicial progredisse sem ser notada, potencialmente evoluindo para uma situação de emergência que poderia ter sido evitada com uma intervenção simples e oportuna.",
    'impacto_padrao': "Proporciona segurança contínua e não invasiva. O paciente se sente cuidado e monitorado, e a equipe tem dados objetivos para sustentar a conduta de baixo risco."
}

# --- 2. Configuração e Carregamento do Modelo spaCy ---
INPUT_FILE = "Compara_modelos.xlsx"
OUTPUT_FILE = "similaridade_semantica_Gemini.csv"

# Tenta carregar o modelo de linguagem grande (necessário para similaridade de qualidade)
try:
    nlp = spacy.load("pt_core_news_lg")
    print("Modelo spaCy 'pt_core_news_lg' carregado.")
except Exception:
    # Fallback caso o modelo pt_core_news_lg não seja encontrado
    print("AVISO: Modelo spaCy 'pt_core_news_lg' não encontrado. Usando Pipeline Básico (similaridade será imprecisa/zero).")
    nlp = Portuguese()

# Pré-processamento dos Textos Padrão (criação dos objetos doc/vetores)
DOCS_PADRAO = {key: nlp(text) for key, text in VARIAVEIS_PADRAO.items()}

# --- 3. Carregamento e Preparação do DataFrame ---
# CORREÇÃO: Usar read_excel() em vez de read_csv() para arquivos .xlsx
try:
    # Lê o arquivo Excel e ignora as últimas 15 linhas
    df = pd.read_excel(INPUT_FILE, skipfooter=0)
    print(f"Arquivo de entrada '{INPUT_FILE}' carregado com sucesso (skipfooter aplicado).")
except FileNotFoundError:
    print(f"ERRO: Arquivo '{INPUT_FILE}' não encontrado.")
    exit()

# Garante que as colunas de texto existam e não contenham NaN
colunas_de_texto = [
    'fundamento_llm', 'fundamento_exp',
    'evidencias_llm', 'evidencias_exp',
    'riscos_llm', 'riscos_exp',
    'impacto_llm', 'impacto_exp'
]
for col in colunas_de_texto:
    if col in df.columns:
        df[col] = df[col].astype(str).fillna("")
    else:
        print(f"AVISO: Coluna '{col}' não encontrada.")

# --- 4. Função para Calcular a Similaridade ---
def calcular_similaridade_semantica(texto_padrao_doc, texto_comparado_str):
    """Calcula a similaridade do cosseno entre o texto padrão (doc) e o texto comparado (str)."""
    if not texto_comparado_str or texto_comparado_str.strip() == "nan":
        return 0.0

    doc_comparado = nlp(texto_comparado_str)

    # Verifica se os vetores (embeddings) estão disponíveis para o cálculo
    if texto_padrao_doc.has_vector and doc_comparado.has_vector:
        return texto_padrao_doc.similarity(doc_comparado)
    else:
        # Retorna 0.0 se o modelo pt_core_news_lg não estiver carregado
        return 0.0

# --- 5. Execução dos Cálculos e Geração das Novas Colunas ---

# Mapeamento das comparações: (coluna_padrao, coluna_comparada, nome_idx_saida)
comparacoes = [
    ('fundamento_padrao', 'fundamento_llm', 'idx_fundamento_llm_calc'),
    ('fundamento_padrao', 'fundamento_exp', 'idx_fundamento_exp_calc'),
    ('evidencias_padrao', 'evidencias_llm', 'idx_evidencias_llm_calc'),
    ('evidencias_padrao', 'evidencias_exp', 'idx_evidencias_exp_calc'),
    ('riscos_padrao', 'riscos_llm', 'idx_riscos_llm_calc'),
    ('riscos_padrao', 'riscos_exp', 'idx_riscos_exp_calc'),
    ('impacto_padrao', 'impacto_llm', 'idx_impacto_llm_calc'),
    ('impacto_padrao', 'impacto_exp', 'idx_impacto_exp_calc')
]

for padrao_key, comparado_col, idx_col in comparacoes:
    if comparado_col in df.columns:
        doc_padrao = DOCS_PADRAO[padrao_key]
        df[idx_col] = df[comparado_col].apply(
            lambda x: calcular_similaridade_semantica(doc_padrao, x)
        )
    else:
        df[idx_col] = 0.0

# --- 6. Formatação e Exportação do Arquivo de Saída ---

# Colunas finais na ordem solicitada, usando SEMICOLON (;) como separador
colunas_saida_final = {
    'id': 'id',
    'idx_fundamento_llm_calc': 'idx_fundamento_llm',
    'idx_fundamento_exp_calc': 'idx_fundamento_exp',
    'idx_evidencias_llm_calc': 'idx_evidencias_llm',
    'idx_evidencias_exp_calc': 'idx_evidencias_exp',
    'idx_riscos_llm_calc': 'idx_riscos_llm',
    'idx_riscos_exp_calc': 'idx_riscos_exp',
    'idx_impacto_llm_calc': 'idx_impacto_llm',
    'idx_impacto_exp_calc': 'idx_impacto_exp'
}

df_saida = df[[c[2] for c in comparacoes] + ['id']].rename(columns=colunas_saida_final)
df_saida = df_saida[['id'] + [c for c in df_saida.columns if c != 'id']] # Reordena 'id' para o início

# Salva o resultado no formato CSV com separador ';' e 3 casas decimais
df_saida.to_csv(OUTPUT_FILE, index=False, sep=';', float_format='%.3f')

print(f"\n--- SUCESSO ---")
print(f"O arquivo '{OUTPUT_FILE}' foi gerado. Este código deve funcionar corretamente no seu ambiente local.")
