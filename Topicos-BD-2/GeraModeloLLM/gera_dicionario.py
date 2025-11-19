import os
import re
from PyPDF2 import PdfReader

def criar_dicionario():
    # Lista para armazenar todas as palavras
    palavras = []
    
    # Diretório onde os PDFs estão armazenados
    diretorio = "./pdf_files"
    
    # Verifica se o diretório existe
    if not os.path.exists(diretorio):
        print(f"Erro: Diretório '{diretorio}' não encontrado!")
        return
    
    # Processa cada arquivo no diretório
    for arquivo in os.listdir(diretorio):
        if arquivo.lower().endswith('.pdf'):
            caminho_arquivo = os.path.join(diretorio, arquivo)
            print(f"Processando: {arquivo}")
            
            try:
                # Extrai texto do PDF
                leitor = PdfReader(caminho_arquivo)
                texto = ""
                for pagina in leitor.pages:
                    texto += pagina.extract_text() or ""
                
                # Remove caracteres especiais e divide em palavras
                # Mantém apenas letras, números básicos e espaços
                texto_limpo = re.sub(r'[^\w\sÀ-ÿ]', ' ', texto)
                
                # Divide o texto em palavras
                palavras_arquivo = texto_limpo.lower().split()
                
                # Filtra palavras válidas
                palavras_validas = []
                for palavra in palavras_arquivo:
                    # Remove qualquer caractere especial residual e verifica se não está vazia
                    palavra_limpa = re.sub(r'[^a-z0-9À-ÿ]', '', palavra)
                    if palavra_limpa and len(palavra_limpa) > 1:  # Ignora palavras com 1 caractere
                        palavras_validas.append(palavra_limpa)
                
                palavras.extend(palavras_validas)
                print(f"  → {len(palavras_validas)} palavras extraídas")
                
            except Exception as e:
                print(f"Erro ao processar {arquivo}: {str(e)}")
    
    if not palavras:
        print("Nenhuma palavra foi extraída dos arquivos PDF.")
        return
    
    # Remove duplicatas e ordena
    palavras_unicas = sorted(set(palavras))
    
    # Salva no arquivo
    with open('dicionario.txt', 'w', encoding='utf-8') as f:
        for palavra in palavras_unicas:
            f.write(palavra + '\n')
    
    print(f"\nDicionário criado com sucesso!")
    print(f"Total de palavras únicas: {len(palavras_unicas)}")
    print(f"Arquivo salvo como: dicionario.txt")

# Versão alternativa com limpeza mais agressiva
def criar_dicionario_limpo():
    # Lista para armazenar todas as palavras
    palavras = []
    
    # Diretório onde os PDFs estão armazenados
    diretorio = "./pdf_files"
    
    # Verifica se o diretório existe
    if not os.path.exists(diretorio):
        print(f"Erro: Diretório '{diretorio}' não encontrado!")
        return
    
    # Processa cada arquivo no diretório
    for arquivo in os.listdir(diretorio):
        if arquivo.lower().endswith('.pdf'):
            caminho_arquivo = os.path.join(diretorio, arquivo)
            print(f"Processando: {arquivo}")
            
            try:
                # Extrai texto do PDF
                leitor = PdfReader(caminho_arquivo)
                texto = ""
                for pagina in leitor.pages:
                    texto += pagina.extract_text() or ""
                
                # Limpeza mais agressiva - mantém apenas letras (incluindo acentuadas)
                texto_limpo = re.sub(r'[^a-zA-ZÀ-ÿ\s]', ' ', texto)
                
                # Divide o texto em palavras e converte para minúsculas
                palavras_arquivo = texto_limpo.lower().split()
                
                # Filtra palavras válidas
                palavras_validas = []
                for palavra in palavras_arquivo:
                    # Remove qualquer caractere não-alfabético residual
                    palavra_limpa = re.sub(r'[^a-zÀ-ÿ]', '', palavra)
                    # Verifica se a palavra não está vazia e tem pelo menos 2 caracteres
                    if palavra_limpa and len(palavra_limpa) > 1:
                        palavras_validas.append(palavra_limpa)
                
                palavras.extend(palavras_validas)
                print(f"  → {len(palavras_validas)} palavras extraídas")
                
            except Exception as e:
                print(f"Erro ao processar {arquivo}: {str(e)}")
    
    if not palavras:
        print("Nenhuma palavra foi extraída dos arquivos PDF.")
        return
    
    # Remove duplicatas e ordena
    palavras_unicas = sorted(set(palavras))
    
    # Salva no arquivo
    with open('dicionario.txt', 'w', encoding='utf-8') as f:
        for palavra in palavras_unicas:
            f.write(palavra + '\n')
    
    print(f"\nDicionário criado com sucesso!")
    print(f"Total de palavras únicas: {len(palavras_unicas)}")
    print(f"Arquivo salvo como: dicionario.txt")

if __name__ == "__main__":
    # Use a função que preferir:
    criar_dicionario_limpo()  # Versão mais restritiva (apenas letras)
    # criar_dicionario()      # Versão que inclui números
