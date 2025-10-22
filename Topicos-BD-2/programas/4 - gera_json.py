import os
import json
import re
import PyPDF2
import spacy
from datetime import datetime

# Verificar e carregar modelos de idioma do spaCy
try:
    nlp_pt = spacy.load('pt_core_news_sm')
    nlp_en = spacy.load('en_core_web_sm')
except OSError:
    print("Erro: Modelos do spaCy não encontrados.")
    print("Execute no terminal:")
    print("python -m spacy download en_core_web_sm")
    print("python -m spacy download pt_core_news_sm")
    exit(1)

def extract_text_from_pdf(pdf_path):
    """Extrai texto de um arquivo PDF"""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ''
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + '\n'
            return text
    except Exception as e:
        print(f"Erro ao extrair texto de {pdf_path}: {str(e)}")
        return ""

def detect_language(text):
    """Detecta o idioma do texto com base em palavras comuns"""
    if not text:
        return 'Indeterminado'
    
    words = text.lower().split()[:100]  # Analisar apenas as primeiras 100 palavras
    pt_indicators = set(['o', 'a', 'de', 'do', 'da', 'em', 'um', 'uma', 'é', 'são', 'para', 'com'])
    en_indicators = set(['the', 'of', 'and', 'in', 'to', 'a', 'is', 'are', 'for', 'with', 'this', 'that'])
    
    pt_count = sum(1 for word in words if word in pt_indicators)
    en_count = sum(1 for word in words if word in en_indicators)
    
    if pt_count > en_count:
        return 'Português'
    elif en_count > pt_count:
        return 'Inglês'
    else:
        return 'Indeterminado'

def extract_metadata(text, pdf_path, filename):
    """Extrai metadados do texto do PDF"""
    if not text:
        return {
            'titulo': 'Título não encontrado',
            'informacoes_url': 'URL não disponível',
            'idioma': 'Indeterminado',
            'storage_key': pdf_path,
            'autores': [],
            'data_publicacao': 'Data não encontrada',
            'resumo': 'Resumo não encontrado',
            'keywords': [],
            'referencias': [],
            'artigo_completo': ''
        }
    
    lines = text.split('\n')
    
    # Extrair título (primeira linha não vazia com pelo menos 3 palavras)
    title = 'Título não encontrado'
    for line in lines:
        if len(line.strip().split()) >= 3:
            title = line.strip()
            break
    
    # Extrair autores (linhas após o título até o resumo)
    authors_section = []
    in_authors = False
    for line in lines:
        if line.strip() and not in_authors and title in line:
            in_authors = True
            continue
        if in_authors and ('abstract' in line.lower() or 'resumo' in line.lower() or 'introduction' in line.lower()):
            break
        if in_authors and line.strip() and len(line.strip().split()) <= 5:
            authors_section.append(line.strip())
    
    # Processar autores
    authors = []
    for author in authors_section[:5]:  # Limite de 5 autores
        if author:
            authors.append({
                'nome': author,
                'afiliacao': 'Afiliação não encontrada',
                'orcid': 'ORCID não encontrado'
            })
    
    # Extrair resumo
    abstract = 'Resumo não encontrado'
    abstract_patterns = [
        r'(?i)abstract[:\s]*\n(.+?)(?=\n\n|\n\w|\nIntroduction|\nINTRODUCTION)',
        r'(?i)resumo[:\s]*\n(.+?)(?=\n\n|\n\w|\nIntrodução|\nINTRODUÇÃO)',
        r'(?i)summary[:\s]*\n(.+?)(?=\n\n|\n\w)'
    ]
    
    for pattern in abstract_patterns:
        abstract_match = re.search(pattern, text, re.DOTALL)
        if abstract_match:
            abstract = abstract_match.group(1).strip()
            break
    
    # Extrair palavras-chave
    keywords = []
    keywords_patterns = [
        r'(?i)keywords[:\s]*\n(.+?)(?=\n\n|\n\w)',
        r'(?i)palavras-chave[:\s]*\n(.+?)(?=\n\n|\n\w)'
    ]
    
    for pattern in keywords_patterns:
        keywords_match = re.search(pattern, text)
        if keywords_match:
            keywords_text = keywords_match.group(1)
            keywords = [k.strip() for k in re.split(r'[;,]', keywords_text) if k.strip()]
            break
    
    if not keywords:
        keywords = ['Palavras-chave não encontradas']
    
    # Extrair data
    date = 'Data não encontrada'
    date_patterns = [
        r'\b\d{2}/\d{2}/\d{4}\b',
        r'\b\d{4}-\d{2}-\d{2}\b',
        r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b'
    ]
    
    for pattern in date_patterns:
        date_match = re.search(pattern, text)
        if date_match:
            date = date_match.group()
            break
    
    # Extrair referências
    references = []
    references_pattern = r'(?i)(references|referências|bibliography)[:\s]*\n(.+?)(?=\n\n|\Z)'
    references_match = re.search(references_pattern, text, re.DOTALL)
    
    if references_match:
        references_text = references_match.group(2)
        references = [ref.strip() for ref in re.split(r'\n\d+\.?\s*|\n•\s*|\n-\s*', references_text) if ref.strip()]
    
    if not references:
        references = ['Referências não encontradas']
    
    return {
        'titulo': title,
        'informacoes_url': f'https://exemplo.com/artigo/{filename}',
        'idioma': detect_language(text),
        'storage_key': pdf_path,
        'autores': authors,
        'data_publicacao': date,
        'resumo': abstract,
        'keywords': keywords,
        'referencias': references[:10],  # Limitar a 10 referências
        'artigo_completo': text[:5000]  # Limitar o texto completo para evitar arquivos muito grandes
    }

def process_text_nlp(text, language):
    """Processa o texto com spaCy para tokenização, POS tagging e lematização"""
    if not text:
        return [], [], []
    
    try:
        if language == 'Português':
            nlp = nlp_pt
        elif language == 'Inglês':
            nlp = nlp_en
        else:
            nlp = nlp_en  # Default para inglês
        
        # Processar apenas os primeiros 10.000 caracteres para evitar problemas de memória
        doc = nlp(text[:10000])
        
        tokens = [token.text for token in doc]
        pos_tags = [token.pos_ for token in doc]
        lemmas = [token.lemma_ for token in doc]
        
        return tokens, pos_tags, lemmas
    except Exception as e:
        print(f"Erro no processamento NLP: {str(e)}")
        return [], [], []

def process_pdfs(pdf_directory):
    """Processa todos os PDFs em um diretório e retorna os dados estruturados"""
    articles_data = []
    
    # Verificar se o diretório existe
    if not os.path.exists(pdf_directory):
        print(f"Erro: Diretório '{pdf_directory}' não encontrado!")
        print("Criando diretório...")
        try:
            os.makedirs(pdf_directory)
            print(f"Diretório '{pdf_directory}' criado. Adicione arquivos PDF e execute novamente.")
        except Exception as e:
            print(f"Erro ao criar diretório: {str(e)}")
        return articles_data
    
    # Listar arquivos PDF
    pdf_files = [f for f in os.listdir(pdf_directory) if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        print(f"Nenhum arquivo PDF encontrado no diretório '{pdf_directory}'")
        return articles_data
    
    print(f"Encontrados {len(pdf_files)} arquivos PDF para processar...")
    
    for filename in pdf_files:
        pdf_path = os.path.join(pdf_directory, filename)
        print(f"Processando: {filename}")
        
        try:
            # Extrair texto do PDF
            text = extract_text_from_pdf(pdf_path)
            
            if not text:
                print(f"Aviso: Não foi possível extrair texto de {filename}")
                continue
            
            # Extrair metadados
            metadata = extract_metadata(text, pdf_path, filename)
            
            # Processamento de NLP
            tokens, pos_tags, lemmas = process_text_nlp(
                text, 
                metadata['idioma']
            )
            
            metadata['artigo_tokenizado'] = tokens
            metadata['pos_tagger'] = pos_tags
            metadata['lema'] = lemmas
            
            articles_data.append(metadata)
            print(f"✓ {filename} processado com sucesso")
            
        except Exception as e:
            print(f"Erro ao processar {filename}: {str(e)}")
    
    return articles_data

# Configurações
PDF_DIR = 'arquivos_pdf'  # Nome corrigido
OUTPUT_JSON = 'artigos.json'

# Executar processamento
if __name__ == "__main__":
    print("Iniciando processamento de PDFs...")
    data = process_pdfs(PDF_DIR)
    
    if data:
        with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"Arquivo {OUTPUT_JSON} gerado com sucesso!")
        print(f"Total de artigos processados: {len(data)}")
    else:
        print("Nenhum dado foi processado. O arquivo JSON não foi criado.")
