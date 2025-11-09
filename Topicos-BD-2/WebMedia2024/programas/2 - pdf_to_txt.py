import fitz  # PyMuPDF
import os
import re

def clean_text(text):
    """
    Realiza operações de limpeza no texto extraído:
    - Normaliza quebras de linha e remove caracteres de avanço de página.
    - Tenta remover nomes de autores e afiliações (abordagem heurística, linguagem agnóstica).
    - Remove as seções ABSTRACT (Inglês) e KEYWORDS (Inglês).
    - Remove o cabeçalho INTRODUCTION (Inglês) se for um título de seção.
    - Remove as seções REFERENCES/BIBLIOGRAPHY (Inglês).
    - Tenta remover números de página.
    - Normaliza espaços em branco para delimitação de parágrafos e palavras.
    """
    # 1. Normaliza quebras de linha e remove caracteres de avanço de página
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = text.replace('\x0c', '') # Caractere de avanço de página

    lines = text.split('\n')
    
    # --- 2. Tentativa de remover Nomes de Autores e Afiliações (altamente heurística) ---
    # Aplica-se às primeiras linhas. Esta parte é linguagem agnóstica.
    main_content_start_index = 0
    # Limita a busca às primeiras 50 linhas para eficiência e relevância
    for i, line in enumerate(lines[:min(50, len(lines))]):
        line_lower = line.lower().strip()
        # Procura por marcadores de início de conteúdo principal (English/Portuguese)
        if (
            line_lower.startswith('abstract') or line_lower.startswith('resumo') or
            line_lower.startswith('introdução') or line_lower.startswith('introduction') or
            re.match(r'^\d+\.?\s+[A-Z]', line_lower) or # Ex: "1. Título"
            re.match(r'^[IVX]+\.?\s+[A-Z]', line_lower) # Ex: "I. Título"
        ):
            main_content_start_index = i
            break
        # Heurística para linhas longas que não parecem ser metadados de autor
        elif len(line_lower.split()) > 10 and not any(
            keyword in line_lower for keyword in ['email', 'university', 'department', 'institute', 'college', 'orcid', 'instituição', 'affiliation', 'author']
        ):
            main_content_start_index = i
            break
        
    # Se um potencial início de conteúdo principal foi encontrado, verifica se o bloco anterior
    # realmente contém padrões de autor para evitar remover introduções legítimas.
    if main_content_start_index > 0:
        potential_author_block = "\n".join(lines[:main_content_start_index]).lower()
        if any(keyword in potential_author_block for keyword in ['email', 'university', 'department', 'institute', 'college', 'orcid', 'instituição', 'affiliation', 'author']):
            lines = lines[main_content_start_index:]
        # Caso contrário, mantém as linhas originais, pois não encontrou padrões fortes de autor.


    # Re-junta as linhas para aplicar regex de blocos maiores
    text = '\n'.join(lines)
    
    # --- 3. Remove seções ABSTRACT (Inglês) e KEYWORDS (Inglês) ---
    # Remove ABSTRACT (Inglês)
    abstract_pattern_en = re.compile(
        r'\bABSTRACT\b.*?'  # Captura ABSTRACT
        r'(?='  # Lookahead para o fim da seção ABSTRACT
        r'\bKEYWORDS\b'         # Fim se encontrar KEYWORDS (English)
        r'|\bRESUMO\b'          # Fim se encontrar RESUMO (Portuguese) - para não remover
        r'|\b(?:1\.\s*Introduction|I\.\s*INTRODUCTION)\b' # Fim se encontrar Introduction (English)
        r'|\bPALAVRAS-CHAVE\b'  # Fim se encontrar PALAVRAS-CHAVE (Portuguese) - para não remover
        r'|\b\d+\.\s+[A-Z][a-zA-Z\s]+' # Ou início de nova seção numerada
        r'|\b[IVX]+\.\s+[A-Z][a-zA-Z\s]+' # Ou início de nova seção romana
        r'|\n\n[A-Z]'           # Ou duas quebras de linha seguidas por uma letra maiúscula (novo parágrafo/seção)
        r'|\Z'                  # Ou fim do documento
        r')',
        re.IGNORECASE | re.DOTALL
    )
    text = abstract_pattern_en.sub('', text)

    # Remove KEYWORDS (Inglês) - se não foi pego pelo ABSTRACT_pattern_en
    keywords_only_pattern_en = re.compile(
        r'\bKEYWORDS\b.*?'
        r'(?='
        r'\bPALAVRAS-CHAVE\b'  # Fim se encontrar PALAVRAS-CHAVE (Portuguese) - para não remover
        r'|\b(?:1\.\s*Introduction|I\.\s*INTRODUCTION)\b' # Fim se encontrar Introduction (English)
        r'|\b\d+\.\s+[A-Z][a-zA-Z\s]+'
        r'|\b[IVX]+\.\s+[A-Z][a-zA-Z\s]+'
        r'|\n\n[A-Z]'
        r'|\Z'
        r')',
        re.IGNORECASE | re.DOTALL
    )
    text = keywords_only_pattern_en.sub('', text)

    # --- 4. Remove o cabeçalho INTRODUCTION (Inglês) ---
    # Procura por linhas que são estritamente o cabeçalho INTRODUCTION, com ou sem numeração.
    # Ex: "1. Introduction", "I. INTRODUCTION", "Introduction"
    introduction_heading_pattern_en = re.compile(
        r'^\s*(?:\d+\.?\s*|[IVX]+\.?\s*)?INTRODUCTION\s*$',
        re.IGNORECASE | re.MULTILINE
    )
    # Substitui a linha do cabeçalho por uma string vazia para ser limpa depois
    text = introduction_heading_pattern_en.sub('\n', text)

    # --- 5. Remove a seção de Referências (Inglês: REFERENCES/BIBLIOGRAPHY) ---
    # Captura "REFERENCES" ou "BIBLIOGRAPHY" (case-insensitive) e tudo o que segue.
    references_pattern_en = re.compile(
        r'\b(?:REFERENCES|BIBLIOGRAPHY)\b.*',
        re.IGNORECASE | re.DOTALL
    )
    text = references_pattern_en.sub('', text)

    # --- 6. Remove números de página ---
    # Opera linha a linha para remover linhas que contêm APENAS um número de página.
    lines = text.split('\n')
    cleaned_lines_without_page_numbers = []
    
    # Regex para identificar uma linha que é *apenas* um número de página
    # Suporta números arábicos (até 4 dígitos) e romanos (até 4 caracteres),
    # opcionalmente envolvidos por hífens/traços e espaços.
    page_number_regex = re.compile(r'^\s*[-–—]?\s*(?:\d{1,4}|[ivxlcdmIVXLCDM]{1,4})\s*[-–—]?\s*$')

    for line in lines:
        stripped_line = line.strip()
        if not stripped_line:
            # Mantém linhas vazias para que a estrutura de parágrafos não seja prejudicada antes da normalização final
            cleaned_lines_without_page_numbers.append(line)
            continue

        # Verifica se a linha corresponde ao padrão de número de página
        if page_number_regex.match(stripped_line):
            # Adiciona uma heurística extra para evitar falsos positivos.
            # Se a linha for curta (até 9 caracteres) E for puramente numérica ou romana, a removemos.
            if len(stripped_line) < 10 and (
                stripped_line.isdigit() or 
                re.fullmatch(r'[ivxlcdmIVXLCDM]+', stripped_line.replace('-', '').replace('–', '').replace('—', '').strip())
            ):
                continue # Remove a linha se for um número de página
        
        # Se não for um número de página (ou for um falso positivo), mantém a linha
        cleaned_lines_without_page_numbers.append(line)

    text = '\n'.join(cleaned_lines_without_page_numbers)

    # --- 7. Normaliza parágrafos e palavras ---
    # Substitui múltiplas quebras de linha por no máximo duas (simulando quebra de parágrafo)
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Substitui múltiplos espaços (e tabulações) por um único espaço
    text = re.sub(r'[ \t]{2,}', ' ', text)
    # Remove espaços em branco do início/fim de cada linha
    text = '\n'.join([line.strip() for line in text.split('\n')])
    # Remove linhas vazias que podem ter resultado das operações anteriores
    text = '\n'.join(filter(lambda x: x.strip(), text.split('\n')))

    return text

def convert_pdfs_to_txt(input_folder, output_folder):
    """
    Lê todos os arquivos PDF na pasta de entrada, converte-os para TXT
    e os salva na pasta de saída após a limpeza.
    """
    if not os.path.exists(input_folder):
        print(f"Erro: A pasta de entrada '{input_folder}' não existe.")
        return

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"Pasta de saída '{output_folder}' criada.")

    pdf_files = [f for f in os.listdir(input_folder) if f.lower().endswith(".pdf")]

    if not pdf_files:
        print(f"Nenhum arquivo PDF encontrado na pasta '{input_folder}'.")
        return

    print(f"Iniciando conversão de {len(pdf_files)} arquivos PDF para TXT...")
    for filename in pdf_files:
        pdf_path = os.path.join(input_folder, filename)
        txt_filename = os.path.splitext(filename)[0] + ".txt"
        txt_path = os.path.join(output_folder, txt_filename)

        print(f"Processando '{filename}'...")
        try:
            document = fitz.open(pdf_path)
            full_text = []
            for page_num in range(document.page_count):
                page = document.load_page(page_num)
                # Extrai texto bruto, ignorando colunas visuais para uma saída de coluna única.
                # page.get_text("text") é a melhor opção para texto puro sem layout complexo.
                full_text.append(page.get_text("text")) 
            document.close()

            combined_text = "\n".join(full_text)
            cleaned_final_text = clean_text(combined_text)

            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(cleaned_final_text)
            print(f"Concluído: '{filename}' -> '{txt_filename}'.")

        except Exception as e:
            print(f"Erro ao processar '{filename}': {e}")
            # Opcional: Salvar o erro em um arquivo de log
            with open(os.path.join(output_folder, f"{os.path.splitext(filename)[0]}_error.log"), "w", encoding="utf-8") as err_f:
                err_f.write(f"Erro ao processar '{filename}': {e}\n")
                err_f.write("Texto original extraído (antes da limpeza):\n")
                # Registra até os primeiros 10000 caracteres do texto bruto em caso de erro
                err_f.write(combined_text[:10000] + ("..." if len(combined_text) > 10000 else "")) 
            

    print("Conversão de PDFs para TXT concluída.")

# Bloco de execução principal
if __name__ == "__main__":
    # --- CONFIGURAÇÃO ---
    # Defina o caminho para a pasta que contém seus arquivos PDF de entrada.
    # Certifique-se de que esta pasta exista e contenha os PDFs.
    input_folder_path = "files_pdf"
    
    # Defina o caminho para a pasta onde os arquivos TXT convertidos serão salvos.
    # Esta pasta será criada automaticamente se não existir.
    output_folder_path = "files_txt"

    print(f"Início do programa de conversão de PDF para TXT.")
    print(f"Lendo arquivos PDF de: '{input_folder_path}'")
    print(f"Salvando arquivos TXT em: '{output_folder_path}'")

    convert_pdfs_to_txt(input_folder_path, output_folder_path)

    print("\nPrograma concluído.")
