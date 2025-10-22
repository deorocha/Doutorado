import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

def list_pdfs_on_page(url):
    """
    Acessa uma URL, encontra e lista todos os links para arquivos PDF,
    com foco na estrutura da página da SBC.

    Args:
        url (str): A URL da página web para analisar.
    """
    print(f"Acessando URL: {url}")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status() # Lança exceção para erros HTTP
    except requests.exceptions.RequestException as e:
        print(f"Erro ao acessar a URL {url}: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')
    
    found_pdfs = set() # Usar um set para armazenar URLs únicas
    
    # 1. Tentar encontrar links diretos para download de PDF (ex: links com 'download' e '.pdf')
    # Estes são geralmente os botões "Baixar PDF"
    for link in soup.find_all('a', class_=['pdf', 'btn-primary'], href=True):
        href = link['href']
        absolute_url = urljoin(url, href)
        parsed_url = urlparse(absolute_url)

        if parsed_url.path.lower().endswith('.pdf') or '/download/' in parsed_url.path.lower():
            found_pdfs.add(absolute_url)
            
    # 2. Tentar encontrar links para as páginas de visualização do PDF que também podem levar ao download
    # Geralmente são links com a classe "label" ou texto "PDF"
    for link in soup.find_all('a', href=True):
        href = link['href']
        absolute_url = urljoin(url, href)
        parsed_url = urlparse(absolute_url)

        # Se o link contém "/article/view/" e é para o mesmo domínio
        # Pode ser um link para a página de visualização do artigo, que geralmente tem um link para o PDF
        if "/article/view/" in parsed_url.path.lower() and urlparse(absolute_url).netloc == urlparse(url).netloc:
            # Verifica se o texto do link ou um span dentro dele indica PDF
            if "pdf" in link.get_text().lower() or link.find('span', class_='label', string='PDF'):
                 found_pdfs.add(absolute_url) # Adiciona a URL da página de visualização do PDF

    # 3. Faz uma requisição para as URLs de visualização (se encontradas) para extrair o link de download direto
    download_links_from_views = set()
    for pdf_view_url in found_pdfs.copy(): # Itera sobre uma cópia, pois o set pode ser modificado
        if "/article/view/" in urlparse(pdf_view_url).path.lower() and pdf_view_url not in found_pdfs:
            print(f"  Explorando página de visualização de PDF: {pdf_view_url}")
            try:
                view_response = requests.get(pdf_view_url, headers=headers, timeout=10)
                view_response.raise_for_status()
                view_soup = BeautifulSoup(view_response.content, 'html.parser')

                # Procura pelo link de download real dentro da página de visualização
                for download_link in view_soup.find_all('a', href=True, class_=['pdf', 'btn-primary']):
                    dl_href = download_link['href']
                    dl_absolute_url = urljoin(pdf_view_url, dl_href)
                    dl_parsed_url = urlparse(dl_absolute_url)

                    if dl_parsed_url.path.lower().endswith('.pdf') or '/download/' in dl_parsed_url.path.lower():
                        download_links_from_views.add(dl_absolute_url)
                        found_pdfs.add(dl_absolute_url) # Adiciona ao set principal
            except requests.exceptions.RequestException as e:
                print(f"  Erro ao explorar {pdf_view_url}: {e}")

    if found_pdfs:
        print("\nArquivos PDF encontrados:")
        # Filtra para mostrar apenas os links de download diretos, se houver
        direct_download_links = {link for link in found_pdfs if '/download/' in urlparse(link).path.lower()}
        
        if direct_download_links:
            print("\n  Links de Download Direto:")
            for pdf_url in sorted(list(direct_download_links)):
                print(f"  - {pdf_url}")
        else: # Se não encontrou links de download direto, lista todos os outros links encontrados
            print("\n  Links Potenciais (incluindo páginas de visualização):")
            for pdf_url in sorted(list(found_pdfs)):
                print(f"  - {pdf_url}")
    else:
        print("Nenhum arquivo PDF encontrado nesta página.")

# --- Bloco de execução principal ---
if __name__ == "__main__":
    target_url = "https://sol.sbc.org.br/index.php/webmedia/issue/view/1361"

    print("Iniciando a listagem de PDFs.")
    print("-" * 50)

    list_pdfs_on_page(target_url)

    print("-" * 50)
    print("Listagem concluída.")
