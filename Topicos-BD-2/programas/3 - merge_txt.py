import os

def concatenar_arquivos_txt(pasta_origem, nome_arquivo_saida="arquivo_saida.txt"):
    """
    Lê todos os arquivos .txt em uma pasta de origem e concatena seus
    conteúdos em um único arquivo de saída.

    Args:
        pasta_origem (str): O caminho para a pasta que contém os arquivos .txt.
        nome_arquivo_saida (str): O nome do arquivo .txt que será criado.
    """
    # Cria o caminho completo para o arquivo de saída
    # caminho_arquivo_saida = os.path.join(pasta_origem, nome_arquivo_saida)
    caminho_arquivo_saida = os.path.join('./', nome_arquivo_saida)
    
    # Lista para armazenar o conteúdo de todos os arquivos
    conteudo_total = []
    
    # Contador de arquivos processados
    arquivos_processados = 0

    print(f"Iniciando a concatenação dos arquivos .txt na pasta: {pasta_origem}")
    
    try:
        # Itera sobre todos os arquivos e pastas no diretório de origem
        for nome_arquivo in os.listdir(pasta_origem):
            # Verifica se o arquivo termina com '.txt'
            if nome_arquivo.endswith(".txt") and nome_arquivo != nome_arquivo_saida:
                caminho_completo = os.path.join(pasta_origem, nome_arquivo)
                
                # Abre e lê o conteúdo do arquivo
                try:
                    with open(caminho_completo, 'r', encoding='utf-8') as arquivo_entrada:
                        conteudo = arquivo_entrada.read()
                        
                        # Adiciona o conteúdo lido à lista, com uma linha separadora (opcional)
                        conteudo_total.append("\n")
                        conteudo_total.append(conteudo)
                        conteudo_total.append("\n\n")
                        arquivos_processados += 1
                        print(f"  -> Arquivo lido com sucesso: {nome_arquivo}")
                
                except UnicodeDecodeError:
                    print(f"  -> ATENÇÃO: Não foi possível ler o arquivo {nome_arquivo} devido a erro de codificação. Pulando.")
                except Exception as e:
                    print(f"  -> ERRO ao ler o arquivo {nome_arquivo}: {e}")

        # Verifica se algum arquivo foi processado
        if arquivos_processados == 0:
            print("Nenhum arquivo .txt encontrado para processar (ou apenas o arquivo de saída).")
            return

        # Escreve todo o conteúdo acumulado no arquivo de saída
        with open(caminho_arquivo_saida, 'w', encoding='utf-8') as arquivo_saida:
            arquivo_saida.writelines(conteudo_total)

        print("-" * 50)
        print(f"✅ SUCESSO! {arquivos_processados} arquivo(s) .txt concatenado(s).")
        print(f"Arquivo final gerado em: {caminho_arquivo_saida}")
        print("-" * 50)

    except FileNotFoundError:
        print(f"ERRO: A pasta '{pasta_origem}' não foi encontrada. Verifique o caminho.")
    except Exception as e:
        print(f"Ocorreu um erro inesperado: {e}")

# --- EXECUTANDO O PROGRAMA ---

# 1. Defina o caminho para a sua pasta.
pasta_dos_arquivos = "./files_txt"

# 2. Chame a função
concatenar_arquivos_txt(pasta_dos_arquivos)
