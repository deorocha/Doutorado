import streamlit as st
import pygame
import random
import sys
import time
import os
import io
import base64
from PIL import Image
import tempfile

# Inicializar pygame
pygame.init()

# Configurações da tela
LARGURA_TELA = 1050
ALTURA_TELA = 1200 
TAMANHO_CELULA = 150
LARGURA_LINHA = 4
DIMENSOES_GRID = (7, 7)  # (colunas, linhas)

# Cores
PRETO = (0, 0, 0)
BRANCO = (255, 255, 255)
CINZA = (128, 128, 128)
VERMELHO = (255, 0, 0)
AZUL = (0, 120, 255)
VERDE = (0, 255, 0)
AMARELO = (255, 255, 0)
CINZA_CLARO = (200, 200, 200)
CINZA_ESCURO = (100, 100, 100)

# Define objetos do Ambiente
grid_ambiente = [
    [1, 0, 0, 0, 0, 0, 0],  # Linha 0
    [0, 0, 3, 0, 0, 0, 0],  # Linha 1
    [0, 0, 0, 0, 0, 0, 0],  # Linha 2
    [0, 0, 0, 2, 0, 3, 0],  # Linha 3
    [0, 0, 0, 0, 3, 4, 0],  # Linha 4
    [0, 0, 0, 0, 0, 0, 0],  # Linha 5 
    [0, 0, 0, 0, 0, 0, 3]   # Linha 6
]

# --- Função para criar imagens padrão ---
def criar_imagem_padrao(cor, tamanho, texto=""):
    """Cria uma imagem padrão quando os arquivos não estão disponíveis"""
    superficie = pygame.Surface(tamanho)
    superficie.fill(cor)
    
    if texto:
        fonte = pygame.font.SysFont(None, 30)
        texto_surface = fonte.render(texto, True, PRETO)
        texto_rect = texto_surface.get_rect(center=(tamanho[0]//2, tamanho[1]//2))
        superficie.blit(texto_surface, texto_rect)
    
    return superficie

# --- Carregar imagens com fallback ---
def carregar_imagem(nome_arquivo, tamanho=None):
    """Carrega uma imagem e opcionalmente redimensiona"""
    try:
        # Para Streamlit Cloud, usamos imagens padrão
        if "robo1" in nome_arquivo or "robot" in nome_arquivo:
            return criar_imagem_padrao(AZUL, (TAMANHO_CELULA-10, TAMANHO_CELULA-10), "R1")
        elif "robo2" in nome_arquivo:
            return criar_imagem_padrao(VERMELHO, (TAMANHO_CELULA-10, TAMANHO_CELULA-10), "R2")
        elif "ouro" in nome_arquivo or "gold" in nome_arquivo:
            return criar_imagem_padrao(AMARELO, (TAMANHO_CELULA-10, TAMANHO_CELULA-10), "OURO")
        elif "lixo" in nome_arquivo:
            return criar_imagem_padrao(VERDE, (TAMANHO_CELULA-10, TAMANHO_CELULA-10), "LIXO")
        else:
            return criar_imagem_padrao(CINZA, (TAMANHO_CELULA-10, TAMANHO_CELULA-10))
    except:
        return criar_imagem_padrao(CINZA, (TAMANHO_CELULA-10, TAMANHO_CELULA-10))

# Carrega as imagens
imagem_robo1 = carregar_imagem("./images/robot.png", (TAMANHO_CELULA-10, TAMANHO_CELULA-10))
imagem_robo2 = carregar_imagem("./images/robot2.png", (TAMANHO_CELULA-10, TAMANHO_CELULA-10))
imagem_lixo = carregar_imagem("./images/lixo.png", (TAMANHO_CELULA-10, TAMANHO_CELULA-10))
imagem_ouro = carregar_imagem("./images/gold.png", (TAMANHO_CELULA-10, TAMANHO_CELULA-10))

# --- Definição das classes ---
class Robo:
    """Classe base para os robôs"""
    def __init__(self, cor, posicao_grid, imagem=None):
        self.cor = cor
        self.largura = TAMANHO_CELULA - 10
        self.altura = TAMANHO_CELULA - 10
        self.posicao_grid = posicao_grid
        self.imagem = imagem
        self.atualizar_rect()

    def atualizar_rect(self):
        """Atualiza o retângulo de colisão e desenho com base na posição do grid"""
        x = self.posicao_grid[0] * TAMANHO_CELULA + (TAMANHO_CELULA - self.largura) // 2 + LARGURA_LINHA
        y = self.posicao_grid[1] * TAMANHO_CELULA + (TAMANHO_CELULA - self.altura) // 2 + LARGURA_LINHA
        self.rect = pygame.Rect(x, y, self.largura, self.altura)

    def desenhar(self, superficie):
        """Desenha o robô na tela"""
        if self.imagem:
            pos_x = self.rect.x + (self.rect.width - self.imagem.get_width()) // 2
            pos_y = self.rect.y + (self.rect.height - self.imagem.get_height()) // 2
            superficie.blit(self.imagem, (pos_x, pos_y))
        else:
            pygame.draw.rect(superficie, self.cor, self.rect, border_radius=10)
            pygame.draw.rect(superficie, PRETO, self.rect.inflate(-10, -10), border_radius=5, width=2)

class Lixo:
    """Classe para representar os itens de lixo"""
    def __init__(self, posicao_grid, imagem=None):
        self.posicao_grid = posicao_grid
        self.carregado = False
        self.raio = 8
        self.imagem = imagem
        self.atualizar_posicao_tela()

    def atualizar_posicao_tela(self):
        """Calcula a posição na tela com base no grid"""
        self.x = self.posicao_grid[0] * TAMANHO_CELULA + TAMANHO_CELULA // 2 + LARGURA_LINHA
        self.y = self.posicao_grid[1] * TAMANHO_CELULA + TAMANHO_CELULA // 2 + LARGURA_LINHA

    def desenhar(self, superficie):
        """Desenha o lixo como uma imagem ou círculo verde se não estiver carregado"""
        if not self.carregado:
            if self.imagem:
                pos_x = self.x - self.imagem.get_width() // 2
                pos_y = self.y - self.imagem.get_height() // 2
                superficie.blit(self.imagem, (pos_x, pos_y))
            else:
                pygame.draw.circle(superficie, VERDE, (self.x, self.y), self.raio)

class Ouro:
    """Classe para representar a moeda de ouro"""
    def __init__(self, posicao_grid, imagem=None):
        self.posicao_grid = posicao_grid
        self.coletado = False
        self.raio = 12
        self.imagem = imagem
        self.atualizar_posicao_tela()

    def atualizar_posicao_tela(self):
        """Calcula a posição na tela com base no grid"""
        self.x = self.posicao_grid[0] * TAMANHO_CELULA + TAMANHO_CELULA // 2 + LARGURA_LINHA
        self.y = self.posicao_grid[1] * TAMANHO_CELULA + TAMANHO_CELULA // 2 + LARGURA_LINHA

    def desenhar(self, superficie):
        """Desenha o ouro como uma imagem ou círculo amarelo se não estiver coletado"""
        if not self.coletado:
            if self.imagem:
                pos_x = self.x - self.imagem.get_width() // 2
                pos_y = self.y - self.imagem.get_height() // 2
                superficie.blit(self.imagem, (pos_x, pos_y))
            else:
                pygame.draw.circle(superficie, AMARELO, (self.x, self.y), self.raio)

class Botao:
    """Classe para representar um botão"""
    def __init__(self, x, y, largura, altura, texto, cor_normal=CINZA_CLARO, cor_hover=CINZA_ESCURO):
        self.rect = pygame.Rect(x, y, largura, altura)
        self.texto = texto
        self.cor_normal = cor_normal
        self.cor_hover = cor_hover
        self.cor_atual = cor_normal
        self.fonte = pygame.font.SysFont(None, 60)
        self.clicado = False
        
    def desenhar(self, superficie):
        """Desenha o botão na tela"""
        pygame.draw.rect(superficie, self.cor_atual, self.rect, border_radius=5)
        pygame.draw.rect(superficie, PRETO, self.rect, 2, border_radius=5)
        
        texto_surface = self.fonte.render(self.texto, True, PRETO)
        texto_rect = texto_surface.get_rect(center=self.rect.center)
        superficie.blit(texto_surface, texto_rect)
        
    def atualizar(self, eventos, mouse_pos, mouse_clicado):
        """Atualiza o estado do botão com base nos eventos"""
        self.clicado = False
        
        if self.rect.collidepoint(mouse_pos):
            self.cor_atual = self.cor_hover
            if mouse_clicado:
                self.clicado = True
        else:
            self.cor_atual = self.cor_normal

# --- Funções de apoio ---
def desenhar_grid(superficie):
    """Desenha as linhas do grid na tela"""
    for linha in range(DIMENSOES_GRID[1] + 1):
        y = linha * TAMANHO_CELULA
        pygame.draw.line(superficie, CINZA, (0, y), (LARGURA_TELA, y), LARGURA_LINHA)
    for coluna in range(DIMENSOES_GRID[0] + 1):
        x = coluna * TAMANHO_CELULA
        pygame.draw.line(superficie, CINZA, (x, 0), (x, LARGURA_TELA), LARGURA_LINHA)

def encontrar_caminho(pos_atual, pos_destino):
    """Encontra um caminho simples entre duas posições no grid"""
    caminho = []
    x_atual, y_atual = pos_atual
    x_dest, y_dest = pos_destino
    
    while x_atual != x_dest:
        if x_atual < x_dest:
            x_atual += 1
        else:
            x_atual -= 1
        caminho.append((x_atual, y_atual))
    
    while y_atual != y_dest:
        if y_atual < y_dest:
            y_atual += 1
        else:
            y_atual -= 1
        caminho.append((x_atual, y_atual))
    
    return caminho

def inicializar_ambiente():
    """Inicializa o ambiente a partir da matriz fornecida"""
    pos_r1 = None
    pos_r2 = None
    posicoes_lixo = []
    pos_ouro = None
    
    for linha in range(len(grid_ambiente)):
        for coluna in range(len(grid_ambiente[linha])):
            valor = grid_ambiente[linha][coluna]
            if valor == 1:
                pos_r1 = (coluna, linha)
            elif valor == 2:
                pos_r2 = (coluna, linha)
            elif valor == 3:
                posicoes_lixo.append((coluna, linha))
            elif valor == 4:
                pos_ouro = (coluna, linha)
    
    return pos_r1, pos_r2, posicoes_lixo, pos_ouro

def surface_to_image(surface):
    """Converte uma surface do pygame para uma imagem que o Streamlit pode exibir"""
    image_str = pygame.image.tostring(surface, 'RGB')
    image = Image.frombytes('RGB', surface.get_size(), image_str)
    return image

# --- Configuração do Streamlit ---
st.set_page_config(page_title="Robôs de Limpeza", layout="wide")
st.title("🤖 Simulador de Robôs de Limpeza")

# Sidebar com controles
st.sidebar.header("Controles")
if st.sidebar.button("Iniciar Limpeza Automática"):
    st.session_state.modo_automatico = True
    st.session_state.mensagem_atual = "Procurando lixo..."
    st.session_state.estado = "procurando"
    st.session_state.ambiente_limpo = False

if st.sidebar.button("Reiniciar Simulação"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]

# Inicializar estado da sessão
if 'modo_automatico' not in st.session_state:
    st.session_state.modo_automatico = False
    st.session_state.mensagem_atual = "Pressione 'Iniciar Limpeza' para começar"
    st.session_state.estado = "procurando"
    st.session_state.ambiente_limpo = False
    st.session_state.pontuacao = 0
    st.session_state.lixo_carregando = None
    st.session_state.caminho_atual = []
    st.session_state.indice_caminho = 0
    st.session_state.aguardando = 0
    st.session_state.delay_movimento = 5

# Inicializar ambiente
pos_r1, pos_r2, posicoes_lixo, pos_ouro = inicializar_ambiente()

# Criar objetos do jogo
robo_aspirador = Robo(AZUL, pos_r1, imagem_robo1)
robo_incinerador = Robo(VERMELHO, pos_r2, imagem_robo2)
lista_lixo = [Lixo(pos, imagem_lixo) for pos in posicoes_lixo]
ouro = Ouro(pos_ouro, imagem_ouro) if pos_ouro else None

# Atualizar estado se necessário
if st.session_state.modo_automatico:
    if st.session_state.aguardando > 0:
        st.session_state.aguardando -= 1
    else:
        # Lógica do modo automático (simplificada para demonstração)
        if not st.session_state.ambiente_limpo and lista_lixo:
            if st.session_state.estado == "procurando":
                lixo_mais_proximo = min(lista_lixo, 
                                      key=lambda l: abs(l.posicao_grid[0] - robo_aspirador.posicao_grid[0]) + 
                                                    abs(l.posicao_grid[1] - robo_aspirador.posicao_grid[1]))
                
                st.session_state.caminho_atual = encontrar_caminho(robo_aspirador.posicao_grid, lixo_mais_proximo.posicao_grid)
                st.session_state.indice_caminho = 0
                st.session_state.estado = "indo_para_lixo"
                st.session_state.mensagem_atual = "Lixo encontrado! Indo coletar..."
            
            elif st.session_state.estado == "indo_para_lixo":
                if st.session_state.indice_caminho < len(st.session_state.caminho_atual):
                    robo_aspirador.posicao_grid = st.session_state.caminho_atual[st.session_state.indice_caminho]
                    robo_aspirador.atualizar_rect()
                    st.session_state.indice_caminho += 1
                    st.session_state.aguardando = st.session_state.delay_movimento
                    
                    if robo_aspirador.posicao_grid == st.session_state.caminho_atual[-1]:
                        st.session_state.estado = "pegando_lixo"
                        st.session_state.mensagem_atual = "Aspirando lixo..."
            
            elif st.session_state.estado == "pegando_lixo":
                for item_lixo in lista_lixo:
                    if item_lixo.posicao_grid == robo_aspirador.posicao_grid and not item_lixo.carregado:
                        item_lixo.carregado = True
                        st.session_state.lixo_carregando = item_lixo
                        break
                
                st.session_state.caminho_atual = encontrar_caminho(robo_aspirador.posicao_grid, robo_incinerador.posicao_grid)
                st.session_state.indice_caminho = 0
                st.session_state.estado = "indo_para_incinerador"
                st.session_state.mensagem_atual = "Levando lixo ao incinerador..."
            
            elif st.session_state.estado == "indo_para_incinerador":
                if st.session_state.indice_caminho < len(st.session_state.caminho_atual):
                    robo_aspirador.posicao_grid = st.session_state.caminho_atual[st.session_state.indice_caminho]
                    robo_aspirador.atualizar_rect()
                    st.session_state.indice_caminho += 1
                    
                    if st.session_state.lixo_carregando is not None:
                        st.session_state.lixo_carregando.posicao_grid = robo_aspirador.posicao_grid
                        st.session_state.lixo_carregando.atualizar_posicao_tela()
                    
                    st.session_state.aguardando = st.session_state.delay_movimento
                    
                    if robo_aspirador.posicao_grid == st.session_state.caminho_atual[-1]:
                        st.session_state.estado = "incinerando"
                        st.session_state.mensagem_atual = "Incinerando lixo..."
            
            elif st.session_state.estado == "incinerando":
                if st.session_state.lixo_carregando is not None:
                    lista_lixo.remove(st.session_state.lixo_carregando)
                    st.session_state.lixo_carregando = None
                    st.session_state.pontuacao += 1
                
                st.session_state.estado = "procurando"
                st.session_state.mensagem_atual = "Lixo incinerado! Procurando mais lixo..."
        
        else:
            st.session_state.ambiente_limpo = True
            if ouro and not ouro.coletado:
                st.session_state.estado = "procurando_ouro"
                st.session_state.mensagem_atual = "Ambiente limpo! Procurando ouro..."

# Criar a superfície do pygame
tela = pygame.Surface((LARGURA_TELA, ALTURA_TELA))
tela.fill(BRANCO)

# Desenhar elementos
desenhar_grid(tela)

# Desenhar lixo
for item_lixo in lista_lixo:
    item_lixo.desenhar(tela)

# Desenhar ouro
if ouro and not ouro.coletado:
    ouro.desenhar(tela)

# Desenhar robôs
robo_aspirador.desenhar(tela)
robo_incinerador.desenhar(tela)

# Desenhar informações
fonte = pygame.font.SysFont(None, 40)
pygame.draw.rect(tela, CINZA_CLARO, (0, 1050, LARGURA_TELA, 150))

# Mensagem atual
texto_mensagem = fonte.render(st.session_state.mensagem_atual, True, PRETO)
tela.blit(texto_mensagem, (20, 1070))

# Pontuação
texto_pontuacao = fonte.render(f"Lixo coletado: {st.session_state.pontuacao}", True, PRETO)
tela.blit(texto_pontuacao, (20, 1120))

# Estado do ambiente
estado_ambiente = "Ambiente limpo! 🎉" if st.session_state.ambiente_limpo else "Ambiente sujo"
texto_ambiente = fonte.render(f"Estado: {estado_ambiente}", True, PRETO)
tela.blit(texto_ambiente, (400, 1120))

# Converter para imagem do Streamlit
imagem_jogo = surface_to_image(tela)

# Exibir no Streamlit
col1, col2 = st.columns([2, 1])

with col1:
    st.image(imagem_jogo, use_column_width=True, caption="Simulação em Tempo Real")

with col2:
    st.header("Status do Jogo")
    st.info(st.session_state.mensagem_atual)
    st.metric("Lixo Coletado", st.session_state.pontuacao)
    st.metric("Estado", "Limpo 🎉" if st.session_state.ambiente_limpo else "Sujo 🗑️")
    
    if st.session_state.ambiente_limpo and ouro and not ouro.coletado:
        st.warning("💰 Ouro encontrado! Indo coletar...")
    elif st.session_state.ambiente_limpo and (ouro is None or ouro.coletado):
        st.success("🎉 Missão completa! Ambiente totalmente limpo!")

# Informações na sidebar
st.sidebar.header("Informações")
st.sidebar.write("""
**Legenda:**
- 🔵 Robô Aspirador (R1)
- 🔴 Robô Incinerador (R2)
- 🟢 Lixo
- 🟡 Ouro

**Funcionamento:**
1. R1 coleta o lixo
2. R1 leva o lixo para R2
3. R2 incinera o lixo
4. Após limpar tudo, R1 busca o ouro
""")

st.sidebar.header("Estatísticas")
st.sidebar.metric("Lixo Restante", len(lista_lixo))
st.sidebar.metric("Ouro", "Coletado" if (ouro and ouro.coletado) or not ouro else "Disponível")