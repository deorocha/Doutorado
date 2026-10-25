# 🔬 Autofoco Z — Scanner histológico de baixo custo

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://SEU-USUARIO-autofocus-z-app-XXXX.streamlit.app)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Aplicação **Streamlit** para autofoco automático do eixo Z em um scanner
histológico de baixo custo. Compara quatro métricas clássicas de foco em
lâminas H&E, com medição de **acurácia** e **tempo de cálculo** por métrica:

- **Variância do Laplaciano** — 2ª derivada (passa-alta)
- **Tenengrad** — energia do gradiente Sobel
- **Brenner** — diferença k-vizinha ao quadrado
- **Energia de alta frequência (FFT)** — magnitude do espectro fora do DC

---

## 📑 Índice

- [Demonstração online](#-demonstração-online)
- [Estrutura do repositório](#-estrutura-do-repositório)
- [Hardware](#-hardware)
- [Instalação](#-instalação)
- [Uso](#-uso)
- [Calibração do eixo Z](#-calibração-do-eixo-z)
- [Arquitetura do software](#-arquitetura-do-software)
- [Deploy no Streamlit Cloud](#-deploy-no-streamlit-cloud)
- [Limitações conhecidas](#-limitações-conhecidas)
- [Referências](#-referências)
- [Licença](#-licença)

---

## 🚀 Demonstração online

🔗 **[Abrir no Streamlit Cloud](https://SEU-USUARIO-autofocus-z-app-XXXX.streamlit.app)**

> ⚠️ **Na nuvem, apenas o modo "Mock (demo)" funciona.**
>
> O Streamlit Cloud **não tem acesso** à câmera local nem à porta serial do
> ESP8266 (é um servidor Linux remoto, sem o seu USB). Para uso com hardware
> real, siga a seção [Instalação](#-instalação) e rode o app **localmente**.
>
> A versão online é útil para:
> - Visualizar o método, gráficos e tabelas sem precisar de hardware
> - Compartilhar o link com orientador/banca para revisão
> - Testar a interface e o fluxo de análise
> - Servir de figura ilustrativa no artigo/tese

---

## 📁 Estrutura do repositório

```
Autofoco-EixoZ/
│
├── app.py                          # Aplicação Streamlit completa (ponto de entrada)
├── requirements.txt                # Dependências Python (ver abaixo)
├── README.md                       # Este arquivo
├── LICENSE                         # Licença MIT
├── .gitignore                      # Arquivos que não devem ir ao Git
│
├── .streamlit/
│   └── config.toml                 # Tema, telemetria, limite de upload
│
├── firmware/
│   └── ZAxis_Nema17_Wemos.ino      # Sketch do ESP8266 (Nema17 + DRV8825)
│
└── docs/
    ├── screenshot-mock.png         # Captura de tela (modo Mock)
    ├── screenshot-accuracy.png     # Captura de tela (aba Acurácia + Tempo)
    ├── schematic.png               # Diagrama de ligação ESP8266 + DRV8825
    └── focus-curves-example.png    # Exemplo de curvas de foco reais
```

### Descrição de cada arquivo

| Arquivo | Conteúdo |
|---|---|
| **`app.py`** | Aplicação inteira em um único arquivo: métricas de foco, classes de hardware (Mock, ESP8266 Serial, ESP8266 WiFi), sweep, plots e UI Streamlit. ~900 linhas. |
| **`requirements.txt`** | Dependências Python (ver [Instalação](#-instalação)). |
| **`README.md`** | Documentação (este arquivo). |
| **`LICENSE`** | Licença MIT — permite uso acadêmico e comercial com atribuição. |
| **`.gitignore`** | Ignora `__pycache__/`, `autofocus_images/`, `.streamlit/secrets.toml`, `*.csv` gerados, `.venv/`. |
| **`.streamlit/config.toml`** | Configuração do Streamlit: tema claro, telemetria desligada, upload até 200 MB. |
| **`firmware/ZAxis_Nema17_Wemos.ino`** | Firmware do ESP8266: protocolo serial (`Z<mm>`, `W`, `PING`, `$102?`) + HTTP (`/move`, `/wait`, `/spm`). Reproduz o controlador usado nos experimentos. |
| **`docs/`** | Imagens para o README, diagramas de hardware e capturas do app em funcionamento. Inclua aqui as figuras do artigo. |

### O que **não** vai no repositório

Os seguintes itens são gerados em tempo de execução e estão no `.gitignore`:

```
autofocus_images/          # Frames capturados durante a varredura
*.csv                      # Resultados exportados (sweep_results.csv, accuracy_comparison.csv)
__pycache__/               # Cache Python
.venv/, venv/              # Ambientes virtuais
.streamlit/secrets.toml    # Credenciais locais (IP do ESP, tokens)
```

Se você quiser versionar resultados de experimentos (para o material
suplementar da tese), crie uma pasta `results/` **explicitamente** e não
a inclua no `.gitignore`:

```
results/
├── 2026-10-25-lamina-01/
│   ├── sweep_results.csv
│   ├── accuracy_comparison.csv
│   └── focus-curves.png
└── README.md                # Descrição do experimento, data, operador
```

E adicione `results/` ao `.gitignore` para evitar commits acidentais:

```gitignore
results/
!results/README.md
```

---

## 🔧 Hardware

### Diagrama de ligação

```
┌─────────────────┐      USB (dados)      ┌──────────────────┐
│   PC / Notebook │ ─────────────────────►│  Wemos D1 R2     │
│  (Streamlit)    │                       │  (ESP8266)       │
└─────────────────┘                       │                  │
                                          │  D5 ─── STEP     │
                                          │  D6 ─── DIR      │
                                          │  D7 ─── ENABLE   │
                                          │  3V3 ── RST+SLP  │
                                          │  GND ── GND      │
                                          └────────┬─────────┘
                                                   │
                                          ┌────────▼─────────┐
                                          │  DRV8825         │
                                          │  (1/16 microstep)│
                                          │                  │
                        ┌─── 12 V (+) ────┤ VMOT             │
                        │                 │ GND  ──── 12 V(–)│
                        │                 │                  │
                        │                 │ B2,B1  ── bobina B
                        │                 │ A1,A2  ── bobina A
                        │                 └────────┬─────────┘
                        │                          │
                   ┌────┴────┐              ┌──────▼──────┐
                   │ Fonte   │              │  Nema17     │
                   │ 12–24 V │              │  + fuso T8  │
                   │ ≥ 2 A   │              └─────────────┘
                   └─────────┘
                        │
                   ┌────▼────┐
                   │ 100 µF  │  ← capacitor entre VMOT e GND
                   └─────────┘
```

### Lista de materiais (BOM)

| Componente | Especificação | Qtd |
|---|---|---|
| Microcontrolador | Wemos D1 R2 (ESP8266) | 1 |
| Driver de motor | DRV8825 (módulo StepStick) | 1 |
| Motor de passo | Nema17 (1,5 A, ~0,4 N·m) | 1 |
| Fuso trapezoidal | T8, passo 8 mm/volta | 1 |
| Fonte | 12–24 V, ≥ 2 A | 1 |
| Capacitor | 100 µF eletrolítico (≥ 25 V) | 1 |
| Câmera | USB (qualquer resolução ≥ 640×480) | 1 |
| Fios, jumpers | Macho-fêmea e fêmea-fêmea | — |

### Parâmetros do DRV8825

- **Microstepping**: `1/16` → jumpers: `MS1=GND, MS2=GND, MS3=VCC`
- **Vref**: **0,75 V** medido no pino 12 do CI (Nema17 1,5 A, Rs=0,1 Ω)
- **RST + SLP**: unidos ao `3V3` (senão o chip dorme)
- **`$102`** (steps/mm): `200 × 16 / 8 = 400` — calibre com paquímetro

### Firmware

O sketch `firmware/ZAxis_Nema17_Wemos.ino` implementa um protocolo mínimo:

**Serial (115200 baud):**
```
Z<mm>       move para posição absoluta (ex.: Z22.5000)
W           aguarda fim do movimento → 'ok' quando parado
PING        responde 'PONG'
$102?       responde '$102=<steps_per_mm>'
$102=<v>    ajusta steps_per_mm
$0          zera a posição atual
```

**HTTP:**
```
GET  /move?mm=20   /wait   /pos   /spm   /ping
POST /spm  (v=<steps_per_mm>)
```

---

## ⚙️ Instalação

### Requisitos

- Python **3.10+**
- Sistema operacional: Windows 10/11, Linux ou macOS
- Hardware conectado (câmera USB + ESP8266 via USB ou WiFi)

### Passo a passo

```bash
# 1. Clone o repositório
git clone https://github.com/SEU-USUARIO/autofocus-z.git
cd autofocus-z

# 2. Crie um ambiente virtual (recomendado)
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux / macOS:
source .venv/bin/activate

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Rode o app
streamlit run app.py
```

O navegador abre automaticamente em `http://localhost:8501`.

### `requirements.txt`

```txt
# Interface
streamlit>=1.32,<1.40

# Processamento de imagem e dados
opencv-python-headless>=4.8,<5.0
numpy>=1.24,<3.0
pandas>=2.0,<3.0
matplotlib>=3.7,<4.0

# Hardware (usado só no modo local)
pyserial>=3.5
requests>=2.31
```

**Notas importantes:**

- **`opencv-python-headless`** (não `opencv-python`) — evita a dependência de
  `libGL.so.1` no Linux do Streamlit Cloud. Suporta todas as funções usadas
  (`Sobel`, `Laplacian`, `GaussianBlur`, `VideoCapture`). Não inclui `imshow`/
  `waitKey`, que **não são usados** por este app.
- **`streamlit>=1.32,<1.40`** — o upper bound é crítico: a partir do 1.40,
  `use_column_width` em `st.image` é depreciado; a partir do 1.49, removido.
  O pin garante que o app rode no Cloud **exatamente como roda no seu PC**.
- **`pyserial`** e **`requests`** — usados apenas nos modos ESP. No Streamlit
  Cloud, falham graciosamente (a UI mostra a mensagem, o app não trava).

### Notas por sistema operacional

**Windows**
- Se a porta COM não abrir com `OSError(22)`: o app tem fallback
  (`_open_serial_robust`) que contorna o bug do driver CH340.
- Feche o Monitor Serial do Arduino IDE **antes** de rodar o app (porta é
  exclusiva).
- Instale o driver **CH340** (wch.cn → CH341SER) se a porta não aparecer.

**Linux**
- Adicione seu usuário ao grupo `dialout` para acessar portas seriais:
  ```bash
  sudo usermod -a -G dialout $USER
  # logout e login novamente
  ```
- O app já usa `cv2.CAP_V4L2` no Linux (detecção automática por `platform`).

**macOS**
- A porta serial costuma ser `/dev/tty.usbserial-XXXX`.
- Autorize o acesso à câmera em **Preferências do Sistema → Segurança e
  Privacidade → Câmera**.

---

## 🎮 Uso

### Modo Mock (demo, sem hardware)

Perfeito para aprender a interface, testar o método, ou usar no Streamlit Cloud.

1. **Sidebar → Hardware → "Mock (demo)"**
2. Ajuste **"Foco verdadeiro simulado"** (padrão: 22.0 mm) e
   **"Resolução simulada"** (padrão: 512×640)
3. Clique **▶️ Iniciar varredura**
4. Explore as abas:
   - **Curvas sobrepostas** — 4 métricas no mesmo gráfico
   - **Painéis por métrica** — 2×2 individual, com separação coarse/refine
   - **🎯 Acurácia + Tempo** — erro vs. ground truth + tempo de cálculo
   - **Tabela** — todos os scores linha a linha + download CSV
   - **Melhores imagens** — frame no pico de cada métrica (grade 2×2)

### Modo ESP8266 Serial (hardware via USB)

1. **Sidebar → Hardware → "ESP8266 — Serial USB"**
2. **Porta serial**: `COM5` (Windows), `/dev/ttyUSB0` (Linux)
3. **Baudrate**: `115200`
4. **⚙️ Calibração `$102`** → **📊 Ler `$102`** → confirme `400.0`
5. **🔌 Testar conexão (câmera + ESP)** → deve mostrar preview e `$102`
6. **▶️ Iniciar varredura**

### Modo ESP8266 WiFi (hardware via rede)

1. **Sidebar → Hardware → "ESP8266 — WiFi (HTTP)"**
2. **IP do ESP8266**: `192.168.1.42` (aparece no Monitor Serial ao ligar)
3. Mesma calibração e teste do modo serial

### Resultado da varredura

Para cada métrica, o app retorna:

- **`z_ótimo`** — posição do pico da curva de foco
- **`score`** — valor da métrica no pico
- **`tempo`** — tempo médio de cálculo por imagem (em ms)
- **`erro`** (modo mock) — |z_ótimo − z_verdadeiro| em µm

O **spread** entre as métricas é exibido como indicador de concordância:
- Spread pequeno → métricas convergem, alta confiança no foco
- Spread grande → divergência, sinal de ruído, ROI vazia ou plano focal múltiplo

---

## 🎯 Calibração do eixo Z

`$102` é o número de passos por milímetro. Sem calibrar, **todas as posições
em mm estão erradas** e a comparação entre métricas fica comprometida.

### Procedimento (2 iterações)

1. Com motor acoplado ao fuso e driver energizado:
2. **Zere a referência** — no Monitor Serial, digite `$0` → responde `ok`
3. **Comande 10 mm** — digite `Z10` → responde `ok` (aguarde o motor parar)
4. **Meça o deslocamento real** `D` com paquímetro
5. **Calcule o novo valor**:
   ```
   $102_novo = $102_atual × (10 / D)
   ```
   Exemplo: mediu 9,6 mm → `$102_novo = 400 × (10/9,6) ≈ 416.7`
6. **Aplique** — no painel Streamlit, digite o novo valor e **💾 Aplicar**
7. **Repita** os passos 2–5 para validar (deve medir 10,0 mm agora)

### Valor teórico (ponto de partida)

```
$102 = passos_por_volta × microstepping / passo_do_fuso_mm
     = 200 × 16 / 8
     = 400  steps/mm
```

---

## 🏗️ Arquitetura do software

`app.py` é organizado em 9 seções:

```
1) Métricas de foco              metric_laplacian, _tenengrad, _brenner, _fft_hf
2) Serial robusto                _open_serial_robust (contorna OSError(22) CH340)
3) Hardware — Mock               MockZAxis, MockCamera (simulador)
4) Hardware — ESP8266 Serial     ESP8266SerialZAxis (handshake PING/PONG)
5) Hardware — Câmera             OpenCVCamera (Windows/Linux/macOS)
6) Sweep                         run_sweep (gerador, com medição de tempo)
7) Helpers de UI                 make_fig, _per_metric, _accuracy, _table
8) App principal                 main() — sidebar, execução, abas
9) Painel de calibração $102     _render_calibration_panel
```

**Decisões de projeto:**

- **Interface unificada `ZAxis`** — as três classes (`MockZAxis`,
  `ESP8266SerialZAxis`, `ESP8266WiFiZAxis`) expõem o mesmo contrato
  (`move_to_mm`, `wait_until_idle`, `close`). Trocar de modo **não muda**
  o `run_sweep`.
- **Handshake ativo** — em vez de esperar passivamente `ready` (one-shot no
  boot), o `__init__` envia `PING` e aguarda `PONG`/`$102=`/`ok`. Isso
  funciona mesmo se o ESP estiver ligado há horas.
- **`_open_serial_robust`** — contorna o bug `OSError(22)` do CH340 no
  Windows (pré-setar `dtr=False` **antes** de `open()` dispara o erro;
  fazer `open()` simples primeiro, depois esperar, resolve).
- **CSV duplo** — `sweep_results.csv` (dados brutos) e
  `accuracy_comparison.csv` (resumo por métrica), prontos para importar no
  Origin/Pandas e montar tabelas do artigo.
- **`use_column_width=True`** (não `use_container_width`) em `st.image`
  — compatibilidade com Streamlit 1.32–1.39.

---

## ☁️ Deploy no Streamlit Cloud

### Subir para o GitHub

```bash
cd "caminho/para/autofocus-z"

git init
git add app.py requirements.txt README.md .gitignore .streamlit/config.toml firmware/ docs/
git commit -m "Autofoco Z — versão 2.4 (acurácia + tempo, mock + ESP8266)"
git branch -M main
git remote add origin https://github.com/SEU-USUARIO/autofocus-z.git
git push -u origin main
```

### Conectar ao Streamlit Cloud

1. Acesse **https://share.streamlit.io**
2. **Sign in with GitHub** → autorize o acesso ao repositório
3. **New app** → preencha:
   - **Repository**: `SEU-USUARIO/autofocus-z`
   - **Branch**: `main`
   - **Main file path**: `app.py`
4. **Deploy!** (primeira vez leva ~2–3 min)

### O que funciona e o que não funciona na nuvem

| Recurso | Cloud | Local |
|---|---|---|
| Modo Mock (demo) | ✅ Funciona | ✅ Funciona |
| Gráficos, tabelas, CSV | ✅ Funciona | ✅ Funciona |
| Câmera local (`cv2.VideoCapture`) | ❌ Sem acesso | ✅ Funciona |
| ESP8266 via USB (`/dev/ttyUSB0`) | ❌ Sem porta | ✅ Funciona |
| ESP8266 via WiFi (IP da rede local) | ⚠️ Só se o ESP estiver na mesma rede do servidor | ✅ Funciona |

**Conclusão prática:** use o Cloud para **mostrar o método** (mock);
use local para **gerar dados reais** (hardware).

### Atualização automática

Após o primeiro deploy, cada `git push` na branch `main` **redeploya
automaticamente** em ~30 segundos. O cache de dependências também é
reaproveitado se `requirements.txt` não mudou.

### Secrets (opcional)

Se um dia você quiser guardar o IP do ESP8266 fora do código:

1. No painel do app no Streamlit Cloud → **Settings → Secrets**
2. Cole:
   ```toml
   esp_host = "192.168.1.42"
   ```
3. No código: `st.secrets.get("esp_host", "192.168.1.42")`
4. **Nunca** commite `.streamlit/secrets.toml` (já está no `.gitignore`)

---

## ⚠️ Limitações conhecidas

### Do hardware

- **Streamlit Cloud não acessa hardware** — modo real só localmente.
- **ESP8266 via WiFi** só funciona se o servidor Streamlit estiver na
  **mesma rede** do ESP. Para acesso externo, use **ngrok** ou
  **Cloudflare Tunnel** (configuração à parte).
- **28BYJ-48 + ULN2003** é fisicamente inviável para elevar a câmera
  (~0,034 N·m vs. ~0,4 N·m necessários). Este projeto usa **Nema17 +
  DRV8825**.

### Do software

- **Mock é simétrico** — as 4 métricas convergem no pico verdadeiro em modo
  demo (desfoque Gaussiano puro, sem discriminação espectral). Em imagens
  reais de H&E, com ruído, texturas e aberrações ópticas distintas, as
  métricas divergem. No mock, o diferenciador prático é o **tempo de cálculo**.
- **Sem persistência entre sessões** — fechar o app limpa `session_state`.
  Os CSVs exportados ficam no disco (ou no `tempfile` se `save_images=False`).
- **`use_column_width=True`** — fixado em `streamlit<1.40`. Migração para
  `width="stretch"` fica para quando o Streamlit 1.40+ for estável.

### Do escopo científico

- As métricas são **clássicas** (Laplaciano, Tenengrad, Brenner, FFT). Não é
  novidade — o valor científico está na **avaliação em H&E com hardware de
  baixo custo**, não no algoritmo.
- Não há comparação com **métodos de deep learning** (ver
  [Referências](#-referências) para trabalhos recentes). Fica como trabalho
  futuro e complementa o argumento de baixo custo computacional.

---

## 📚 Referências

Fundamentos das métricas e comparações clássicas:

- **Sun, Y., Duthaler, S., & Nelson, B. J. (2004).** Autofocusing in computer
  microscopy: Selecting the optimal focus algorithm. *Microscopy Research
  and Technique*, 65(3), 139–149.
- **Pertuz, S., Puig, D., & Garcia, M. A. (2013).** Analysis of focus measure
  operators for shape-from-focus. *Pattern Recognition*, 46(5), 1415–1432.
- **Yazdanfar, S., Kenny, K. B., Tasimi, K., Corwin, A. D., Dixon, E. T., &
  Filkins, R. J. (2008).** Simple and robust image-based autofocusing for
  digital microscopy. *Optics Express*, 16(12), 8670–8677.
- **Santos, A., Ortiz de Solórzano, C., Vaquero, J. J., Peña, J. M., Malpica,
  N., & del Pozo, F. (1997).** Evaluation of autofocus functions in molecular
  cytogenetic analysis. *Journal of Microscopy*, 188(3), 264–272.

Hardware acessível e patologia digital:

- **Collins, J. T., et al. (2017).** Robotic microscopy for everyone: the
  OpenFlexure Microscope. *Review of Scientific Instruments*, 88(8), 083105.
- **Bian, Z., et al. (2020).** Autofocusing technologies for whole slide
  imaging. *Journal of Pathology Informatics*.
- **Chen, G., et al. (2024).** GJFocuser: A robust autofocus method for
  low-cost digital microscopy. *Biomedical Optics Express*.

> ⚠️ Verifique cada referência nas bases primárias (PubMed, Scopus, IEEE
> Xplore) antes de citar no artigo. A memória de treinamento pode conter
> imprecisões de volume/página/ano.

---

## 🤝 Contribuindo

Issues e pull requests são bem-vindos. Para mudanças grandes, abra uma issue
primeiro para discutir o que você quer mudar.

## 📄 Licença

Distribuído sob a **licença MIT**. Veja [LICENSE](LICENSE) para o texto
completo. Uso acadêmico e comercial permitido, com atribuição.

## 👤 Autor

**André Rocha**
Doutorando em Ciência da Computação — PGCOMP/UFBA
📧 rocha.a@ufba.br

## 🙏 Agradecimentos

- Meu orientador de Doutorado, o Prof. Dr. Luciano Oliveira
- Comunidade open-source do Streamlit, OpenCV e NumPy
- Projeto [OpenFlexure](https://openflexure.org/) — referência de microscopia open-hardware
- [OpenWSI](https://github.com/AndyFooGuo/OpenWSI) — referência de scanner de baixo custo

---

<p align="center">
  Feito com 🔬 para patologia digital acessível
</p>
