import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

def scrape_and_download_pdfs_sbc(url, download_folder="sbc_pdfs_baixados"):
    """
    Acessa uma URL específica da SBC (e.g., https://sol.sbc.org.br/index.php/webmedia/issue/view/1361),
    encontra os links para as páginas de visualização de artigos, constrói os links diretos
    de download de PDF, lista-os e, em seguida, baixa os arquivos para a pasta especificada.

    Args:
        url (str): A URL da página web para analisar e baixar PDFs.
        download_folder (str): O nome da pasta onde os PDFs serão salvos.
    """
    print("=" * 70)
    print("INICIANDO WEB SCRAPING, LISTAGEM E DOWNLOAD DE PDFs")
    print("=" * 70)
    print(f"URL de origem para análise: {url}")
    print(f"Pasta de destino para downloads: {os.path.abspath(download_folder)}")

    if not os.path.exists(download_folder):
        os.makedirs(download_folder)
        print(f"\nPasta '{download_folder}' criada com sucesso.")

    print(f"\nAcessando URL principal: {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status() # Lança exceção para erros HTTP (4xx ou 5xx)
    except requests.exceptions.RequestException as e:
        print(f"Erro ao acessar a URL principal {url}: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Conjunto para armazenar somente os links diretos de download de PDF construídos
    direct_pdf_download_links = set() 
    
    # 1. Encontrar links para páginas de visualização de artigos na página principal
    for link_tag in soup.find_all('a', href=True):
        href = link_tag['href']
        absolute_url = urljoin(url, href)
        parsed_url = urlparse(absolute_url)

        # Verifica se é um link para a página de visualização de um artigo
        # Ex: https://sol.sbc.org.br/index.php/webmedia/article/view/30323/30129
        # E se pertence ao mesmo domínio da URL de origem
        if "/article/view/" in parsed_url.path.lower() and urlparse(absolute_url).netloc == urlparse(url).netloc:
            
            # Constrói o link de download substituindo 'view' por 'download'
            download_path = parsed_url.path.replace('/view/', '/download/')
            download_url = urljoin(absolute_url, download_path)
            
            # Adiciona o link de download direto ao conjunto
            direct_pdf_download_links.add(download_url)

    if not direct_pdf_download_links:
        print("\nNenhum link de download de PDF direto foi encontrado ou construído nesta página.")
        return

    print(f"\n{len(direct_pdf_download_links)} links de download de PDF diretos identificados:")
    print("-" * 50)
    
    # Lista os links encontrados
    sorted_pdf_links = sorted(list(direct_pdf_download_links))
    for i, pdf_url in enumerate(sorted_pdf_links):
        # Tenta extrair um nome de arquivo para referência (ex: o ID do documento)
        path_segments = urlparse(pdf_url).path.split('/')
        filename_hint = path_segments[-1] if path_segments[-1] else "unknown"
        print(f"  {i+1}. [ID: {filename_hint}] {pdf_url}")
    
    print("-" * 50)
    print("\nIniciando o download dos arquivos PDF...")
    downloaded_count = 0

    for pdf_url in sorted_pdf_links: # Itera sobre os links diretos
        try:
            # Tenta extrair um nome de arquivo significativo da URL
            path_segments = urlparse(pdf_url).path.split('/')
            filename_base = path_segments[-1] # Geralmente o ID do documento
            filename = f"{filename_base}.pdf"
            
            # Limpa o nome do arquivo de caracteres inválidos e garante a extensão .pdf
            filename = "".join(c for c in filename if c.isalnum() or c in ('.', '_', '-')).strip()
            if not filename or not filename.lower().endswith('.pdf'): 
                 filename = f"downloaded_sbc_pdf_{downloaded_count + 1}.pdf"
            
            file_path = os.path.join(download_folder, filename)

            # Para evitar sobrescrever se IDs de documento se repetirem ou colidirem
            original_filename = filename
            counter = 1
            while os.path.exists(file_path):
                name, ext = os.path.splitext(original_filename)
                filename = f"{name}_{counter}{ext}"
                file_path = os.path.join(download_folder, filename)
                counter += 1

            print(f"  Baixando '{filename}' de {pdf_url}")

            # Requisição para baixar o PDF em stream para lidar com arquivos grandes
            pdf_response = requests.get(pdf_url, stream=True, headers=headers, timeout=30)
            pdf_response.raise_for_status() # Lança exceção para erros HTTP no download

            with open(file_path, 'wb') as f: # Abre o arquivo em modo binário de escrita
                for chunk in pdf_response.iter_content(chunk_size=8192): # Lê em partes
                    f.write(chunk)
            print(f"  Download concluído: '{filename}'")
            downloaded_count += 1
        except requests.exceptions.RequestException as e:
            print(f"  Erro ao baixar '{pdf_url}': {e}")
        except IOError as e:
            print(f"  Erro ao salvar '{filename}': {e}")
        except Exception as e:
            print(f"  Erro inesperado ao processar '{pdf_url}': {e}")

    print(f"\nProcesso de download concluído. Total de {downloaded_count} PDFs baixados para '{download_folder}'.")

# --- BLOCO DE EXECUÇÃO PRINCIPAL ---
if __name__ == "__main__":
    
    # URL da página da SBC para raspar os PDFs
    SBC_TARGET_URL = "https://sol.sbc.org.br/index.php/webmedia/issue/view/1361"
    # Pasta onde os PDFs baixados da SBC serão salvos
    SBC_DOWNLOAD_FOLDER = "files_pdf"

    scrape_and_download_pdfs_sbc(SBC_TARGET_URL, SBC_DOWNLOAD_FOLDER)

    print("\n" + "=" * 70)
    print("PROGRAMA FINALIZADO.")
    print("=" * 70)
