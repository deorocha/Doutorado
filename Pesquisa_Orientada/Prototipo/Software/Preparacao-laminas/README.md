# 🔬 Preparação de Lâminas — Áreas de Varredura

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://SEU-USUARIO-preparacao-laminas.streamlit.app)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Aplicação **Streamlit** para **preparação interativa de lâminas
histológicas** antes da digitalização. A partir de uma imagem capturada
da lâmina, o usuário seleciona **quais áreas** o scanner deve varrer —
por **detecção automática** (HSV + Canny + morfologia) ou por
**seleção manual** (magic wand com distância de cor em CIELAB, ou
ferramentas de desenho retângulo/elipse/ponto).

Ao final, gera um **`scan_plan.json`** que descreve, para cada lâmina
preparada, o modo de varredura (lâmina inteira vs. áreas específicas),
as regiões a varrer e os parâmetros usados — arquivo que o scanner
consome na etapa seguinte.

- **Grade 8×2** visualizando as bandejas e o status de cada lâmina
- **Dois modos de preparação**: `manual` (magic wand + ferramentas) e
  `auto` (detecção por limiar de cor + bordas)
- **Leitura de QR** da imagem para vincular o ID físico ao caso
- **QR detectado é salvo** na lâmina (`qr_id`) e exportado no plano
- **Barra de progresso** por bandeja (`preparadas/total`)
- **Exportação dupla**: arquivo local + download no navegador
- **Guia em PDF** exibido inline (`st.pdf`, com fallback `<embed>`)

---

## ⚠️ Aviso crítico: o app NÃO roda só com o `app.py`

O `app.py` **importa 7 módulos locais** que você **precisa levar para o
GitHub** junto com o arquivo principal:

```python
from config import (...)          # constantes, DEFAULT_PARAMS, image_path, slide_key, EXPORT_FILE
from storage import (...)         # load_state, get_slide, update_slide
from processing import (...)      # detect_regions, draw_regions, magic_wand_flood_fill
from qr_utils import read_qr      # leitor de QR (pyzbar OU cv2.QRCodeDetector)
from demo import generate_demo_slide   # imagem sintética para testes
from clickable import drawable_image   # componente interativo de desenho
from toolbar import toolbar            # barra de ferramentas (magic wand, retângulo, etc.)
```

Se você subir só o `app.py`, o deploy no Streamlit Cloud falha em ~3 s
com:

```
ModuleNotFoundError: No module named 'config'
```

**Antes de fazer `git push`, confirme que todos esses arquivos estão na
mesma pasta do `app.py`.** Veja a
[estrutura completa do repositório](#-estrutura-do-repositório).

### ⚠️ Aviso secundário: filesystem no Cloud é efêmero

`storage.update_slide()` grava em arquivo local (o `state.json` por
baixo), `image_path(tray, pos)` grava imagens em disco, e `EXPORT_FILE`
grava o `scan_plan.json` no disco do servidor. No Streamlit Cloud:

- **Escritas funcionam durante a sessão**
- **São apagadas a cada redeploy ou reinício do container**
- **Não são compartilhadas entre usuários** (múltiplas abas do mesmo
  navegador compartilham `session_state`; navegadores diferentes **não**)

Isso significa que o app **serve para uso individual e sessão curta**,
mas **não substitui um backend persistente**. Para laboratório real,
coloque `state.json` + imagens + `scan_plan.json` em:
- SQLite em `/tmp` (persiste enquanto o container estiver de pé), **ou**
- S3 / GCS / Azure Blob (persistência real), **ou**
- Um Postgres/Supabase externo (configurável via `st.secrets`)

Veja [Limitações conhecidas](#-limitações-conhecidas) para o detalhamento.

---

## 📑 Índice

- [Demonstração online](#-demonstração-online)
- [Estrutura do repositório](#-estrutura-do-repositório)
- [Workflow](#-workflow)
- [Instalação](#-instalação)
- [Uso](#-uso)
- [Modo manual: magic wand + ferramentas](#-modo-manual-magic-wand--ferramentas)
- [Detecção automática: parâmetros](#-detecção-automática-parâmetros)
- [QR codes](#-qr-codes)
- [Deploy no Streamlit Cloud](#-deploy-no-streamlit-cloud)
- [Limitações conhecidas](#-limitações-conhecidas)
- [Referências](#-referências)
- [Licença](#-licença)

---

## 🚀 Demonstração online

🔗 **[Abrir no Streamlit Cloud](https://SEU-USUARIO-preparacao-laminas.streamlit.app)**

A versão online permite testar **todo o fluxo** com a imagem de
demonstração (`🎲 Gerar imagem de demonstração` na tela da lâmina
vazia). Bom para:

- Validar a interface com a equipe do laboratório
- Mostrar o método para orientador/banca
- Ilustrar o artigo com capturas do fluxo de preparação

**Limitações no Cloud:**
- `scan_plan.json` some quando o container reinicia
- Imagens enviadas duram só a sessão
- **Estado não é compartilhado** entre navegadores diferentes

Para uso em bancada, rode **localmente** (o estado persiste em disco
entre sessões).

---

## 📁 Estrutura do repositório

```
Preparacao-Laminas/
│
├── app.py                          # ✅ fornecido (ponto de entrada)
├── requirements.txt                # ✅ este arquivo
├── README.md                       # ✅ este arquivo
├── LICENSE                         # MIT
├── .gitignore                      # ignora imagens/estado gerados
│
├── config.py                       # ⚠️ NÃO fornecido — necessário
├── storage.py                      # ⚠️ NÃO fornecido — necessário
├── processing.py                   # ⚠️ NÃO fornecido — necessário
├── qr_utils.py                     # ⚠️ NÃO fornecido — necessário
├── demo.py                         # ⚠️ NÃO fornecido — necessário
├── clickable.py                    # ⚠️ NÃO fornecido — necessário
├── toolbar.py                      # ⚠️ NÃO fornecido — necessário
│
├── styles.css                      # ⚠️ externo (CSS para a grade 8×2)
├── Preparação das lâminas.pdf      # ⚠️ opcional (guia; tem fallback)
│
├── packages.txt                    # ⚠️ SE qr_utils usa pyzbar: libzbar0
│
├── .streamlit/
│   └── config.toml                 # tema, telemetria desligada
│
├── frontend/                       # ⚠️ SE clickable/toolbar for custom component
│   └── build/                      #    (HTML+JS compilado) — commitar
│
├── images/                         # 📁 gerado em runtime — NÃO commitar
│   └── tray1_pos01.png             #    (capturas das lâminas)
│
├── state.json                      # 📄 gerado em runtime — NÃO commitar
└── scan_plan.json                  # 📄 gerado em runtime — NÃO commitar
```

### O que **não** vai no repositório

Adicione ao `.gitignore`:

```gitignore
__pycache__/
*.pyc
.venv/venv/
.streamlit/secrets.toml

# Estado e artefatos do app
images/
state.json
scan_plan.json
Preparação das lâminas.pdf
```

> O PDF do guia é opcional: `_render_guia_pdf()` detecta a ausência e
> mostra um aviso no expander da sidebar (sem travar o app). Se quiser
> versioná-lo, comite — o arquivo tem ~200 KB e ajuda outros usuários.

### `.gitignore` recomendado

```gitignore
__pycache__/
*.pyc
*.pyo
.venv/
venv/
env/

# Streamlit
.streamlit/secrets.toml

# Estado de runtime
images/
state.json
scan_plan.json

# Sistema
.DS_Store
Thumbs.db
```

---

## 🔄 Workflow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Bandeja 1..N   │ ──▶ │  Lâmina 1..16    │ ──▶ │  Preparação     │
│  (grade 8×2)    │     │  (status + QR)   │     │  (áreas)        │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         ▲                       │                        │
         │                       │                        ▼
         │                       │              ┌──────────────────┐
         │                       │              │  Modo: whole     │
         │                       │              │  Modo: manual    │
         │                       │              │  Modo: auto      │
         │                       │              └──────────────────┘
         │                       │                        │
         │                       ▼                        │
         │              ┌──────────────────┐              │
         │              │  💾 Salvar        │◀─────────────┘
         │              │  (status=prepared)│
         │              └──────────────────┘
         │                       │
         │                       ▼
         │              ┌──────────────────┐
         └──────────────│  📤 Exportar     │
                        │  scan_plan.json  │
                        └──────────────────┘
```

### Status das lâminas

| Ícone | Status | Significado |
|---|---|---|
| ⬜ | `empty` | Nunca preparada |
| 🟦 | `loaded` | Imagem capturada + QR lido (mas não preparada) |
| ✅ | `prepared` | Pronta para o scanner (vai no `scan_plan.json`) |

### Modos de varredura

| Modo | O que faz | Quando usar |
|---|---|---|
| `whole` | Marca a **lâmina inteira** para varredura | Lâmina já está bem posicionada; quer varrer tudo |
| `specific` (manual) | Você desenha/seleciona **regiões** interativamente | Poucas áreas de interesse bem definidas |
| `specific` (auto) | Detecção por **HSV + Canny + morfologia** | Lâminas com tecido bem delimitado e fundo limpo |

O plano final inclui, por lâmina preparada:
```json
{
  "slide_id": 3,
  "qr_id": "L-2026-0042",
  "scan_mode": "specific",
  "regions": [{"x": 120, "y": 340, "w": 800, "h": 600}],
  "params": {"sat_threshold": 40, "canny_low": 50, ...}
}
```

---

## ⚙️ Instalação

### Requisitos

- Python **3.10+**
- Windows 10/11, Linux ou macOS
- Navegador moderno (o `clickable`/`toolbar` usam JavaScript;
  Chrome/Firefox/Edge/Safari funcionam)

### Passo a passo

```bash
# 1. Clone o repositório
git clone https://github.com/SEU-USUARIO/preparacao-laminas.git
cd preparacao-laminas

# 2. Confirme que os 7 módulos locais estão presentes
ls config.py storage.py processing.py qr_utils.py demo.py clickable.py toolbar.py
# Todos devem existir. Se faltar algum, o app NÃO roda.

# 3. Ambiente virtual (recomendado)
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux / macOS:
source .venv/bin/activate

# 4. Instale as dependências
pip install -r requirements.txt

# 5. Rode o app
streamlit run app.py
```

O navegador abre automaticamente em `http://localhost:8501`.

### Notas por sistema operacional

**Windows**
- Nenhuma configuração especial. OpenCV headless é wheel nativa.
- Se `cv2.imread` retornar `None` em caminhos com acentuação (ex.:
  `Preparação`), use `cv2.imdecode(np.fromfile(...), cv2.IMREAD_COLOR)`
  — limitação do `imread` no Windows com encoding UTF-8.

**Linux**
- Se faltar `libGL.so.1` (erro comum com `opencv-python` **não-headless**),
  ou troque para `opencv-python-headless` ou instale `apt install libgl1`.
  O `requirements.txt` já usa headless.
- Se `qr_utils.py` usa `pyzbar`, instale `sudo apt install libzbar0`.

**macOS**
- Nada especial. `pyzbar` (se usado) requer `brew install zbar`.

---

## 🎮 Uso

### Fluxo básico

1. **Sidebar → Bandeja** — escolha a bandeja (1 a `N_TRAYS`)
2. **Grade 8×2** — clique em uma lâmina (⬜ vazia, 🟦 carregada ou
   ✅ preparada)
3. **Tela da lâmina** — se não há imagem:
   - **🎲 Gerar imagem de demonstração** — cria uma imagem sintética
     para testar o fluxo sem hardware
   - **Upload** — envie um PNG/JPG/JPEG capturado previamente
4. **Escolha o modo de varredura**:
   - **🖼️ Lâmina inteira** → clique em **💾 Salvar configuração** → pronto
   - **🎯 Áreas específicas** → escolha `manual` ou `auto` (ver seções
     abaixo) → **💾 Salvar preparação**
5. **Repita** para outras lâminas
6. **Aba 📤 Exportar** → revise o JSON → **💾 Gerar arquivo** (grava
   `scan_plan.json` no disco) ou **⬇️ Baixar** (download no navegador)

### Lendo o QR

Na primeira vez que a imagem de uma lâmina é carregada, `read_qr()` é
chamado. Se um QR for detectado:

- O `qr_id` é salvo em `slide["qr_id"]`
- O status muda de `empty` → `loaded`
- A tela mostra `QR: L-2026-0042` no cabeçalho

Se não houver QR, a lâmina fica em `loaded` sem `qr_id`, e a preparação
**pode continuar** — o `qr_id` vai como `null` no plano exportado.

### Barra de progresso

O sidebar mostra `prep / total` em `st.progress`. Total =
`N_TRAYS × SLIDES_PER_TRAY` (definido em `config.py`).

---

## 🖌️ Modo manual: magic wand + ferramentas

Ao escolher **🎯 Áreas específicas** → **🖌️ Manual**, você tem:

### Magic wand (varinha mágica)

Clique na imagem para selecionar o "blob" de cor similar à região
clicada. Ajuste:

| Controle | Efeito | Dica |
|---|---|---|
| **Limiar (threshold)** | Distância de cor em CIELAB (1–200) | Baixo = estrito; alto = permissivo |
| **Margem (px)** | Expande a borda da seleção | Use 5–10 px para incluir a borda do tecido |
| **CLAHE** | Realce de contraste local | Ative se o tecido estiver esmaecido |
| **Contíguo** | Só o blob conectado ao clique | Desative para pegar todos os blobs da mesma cor |

Após o clique:

- A região fica **pendente** (contorno vermelho)
- Botão **✅ Adicionar** — commita em `regions`
- Botão **❌ Descartar** — descarta
- **Mudar slider** com pendente ativa → **recalcula** a região com o
  novo limiar (o app guarda a assinatura `(x, y, threshold, padding, ...)`
  e refaz o flood-fill)

### Ferramentas de desenho

Barra superior com ferramentas:

- **🖌️ Magic wand** — clique para selecionar blob
- **⬛ Retângulo** — arraste para desenhar
- **⭕ Elipse** — arraste para desenhar
- **📍 Ponto** — clique único (marca uma região de 1×1 px)

Todas as regiões desenhadas são adicionadas **diretamente** em
`regions` (não passam por "pendente").

### Lista de regiões

No expander **📋 Regiões preparadas (N)**:

- Cada região mostra `#N (kind) · x= y= w= h=`
- **🗑️** remove individual
- **🗑️ Limpar todas** remove tudo

### Aparência

- **Cor da borda** (`st.color_picker`) — cor das linhas tracejadas
- **Espessura da borda** (1–5 px) — espessura das linhas

Essas preferências são por lâmina (`key=f"..._{tray}_{pos}"`), então
cada lâmina pode ter sua própria cor.

---

## 🤖 Detecção automática: parâmetros

Ao escolher **🎯 Áreas específicas** → **🤖 Detecção automática**:

### Pipeline (definido em `processing.detect_regions`)

```
Imagem BGR
    │
    ├──▶ Conversão para HSV
    │
    ├──▶ Threshold: (S < sat_threshold) AND (V < val_threshold)
    │       └──▶ mascara_tecido   (tecido H&E é escuro e saturado)
    │
    ├──▶ Canny(canny_low, canny_high) → bordas
    │
    ├──▶ morfologia (kernel = morph_kernel)
    │       └──▶ fecha buracos
    │
    └──▶ cv2.connectedComponentsWithStats
            └──▶ filtro por area_px >= min_area
                    └──▶ regiões finais
```

### Controles (sliders)

| Parâmetro | Faixa | O que faz |
|---|---|---|
| **Saturação** (`sat_threshold`) | 0–120 | Limite superior de S no HSV — tecido H&E é **mais saturado** que o fundo |
| **Valor máx.** (`val_threshold`) | 0–255 | Limite superior de V no HSV — tecido é **mais escuro** que o vidro |
| **Canny low** | 0–255 | Bordas fracas |
| **Canny high** | 0–255 | Bordas fortes (recomendado: `low = high/3` a `high/2`) |
| **Área mín.** (`min_area`) | 100–60000 px² | Descarta fragmentos pequenos (bolhas, poeira) |
| **Kernel** (`morph_kernel`) | 1–25 (ímpar) | Tamanho do elemento estruturante da morfologia |

### Visualização

Ao lado dos controles, duas imagens lado a lado:

- **Imagem com contornos**: `draw_regions(img, regions, color, thickness)`
- **Máscara binária**: `mask` (o que foi classificado como tecido)

### Ações

- **➕ Adicionar todas** — appenda as regiões detectadas à lista,
  **deduplicando** por `(x, y, w, h)`
- **♻️ Substituir lista** — descarta a lista atual e coloca só as
  detectadas
- **🔄 Valores padrão** — reseta os 6 sliders para `DEFAULT_PARAMS`
- **💾 Salvar preparação** — commita com os parâmetros usados

### Calibração

1. Gere uma imagem de demonstração ou carregue uma real
2. Vá em **auto**, ajuste `Saturação` e `Valor máx.` até a **máscara
   mostrar só o tecido** (sem fundo)
3. Ajuste `Área mín.` para descartar fragmentos
4. Ajuste `Kernel` para fechar buracos internos do tecido
5. Salve — os `params` são **exportados no `scan_plan.json`**, então o
   scanner usa exatamente os mesmos parâmetros

### Cache

A detecção é cacheada por `@st.cache_data(max_entries=16)` com chave
`(path_str, mtime, max_width, params_items)`. Mudar qualquer slider
invalida o cache automaticamente.

---

## 📷 QR codes

`qr_utils.read_qr(img)` é chamado uma vez por imagem (também cacheado em
`_load_slide_base`). O retorno esperado é uma tupla:

```python
qr_data, bbox = read_qr(img)
# qr_data: str | None  (texto decodificado)
# bbox:    list | None (coordenadas do QR na imagem, para debug)
```

### Duas implementações possíveis

**A) OpenCV nativo (recomendado para Streamlit Cloud):**

```python
# qr_utils.py
import cv2

def read_qr(img):
    detector = cv2.QRCodeDetector()
    data, points, _ = detector.detectAndDecode(img)
    if not data:
        return None, None
    bbox = points.reshape(-1, 2).astype(int).tolist() if points is not None else None
    return data, bbox
```

- ✅ Zero dependências extras
- ✅ Funciona no Cloud sem `packages.txt`
- ⚠️ Detector do OpenCV é menos robusto que `pyzbar` em QRs com
  perspectiva ou baixo contraste

**B) pyzbar (mais robusto, mas exige `packages.txt`):**

```python
# qr_utils.py
from pyzbar.pyzbar import decode
import cv2

def read_qr(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    decoded = decode(gray)
    if not decoded:
        return None, None
    obj = decoded[0]
    return obj.data.decode("utf-8"), obj.rect
```

E `packages.txt` na raiz:

```
libzbar0
```

### O que vai no `scan_plan.json`

```json
{
  "slide_id": 3,
  "qr_id": "L-2026-0042",
  ...
}
```

Se nenhum QR for detectado, `qr_id` fica `null`. A lâmina ainda pode
ser preparada e exportada — o vínculo ao LIMS é opcional.

---

## ☁️ Deploy no Streamlit Cloud

### Pré-requisitos

- **Todos os 7 módulos locais** no repositório (ver aviso crítico acima)
- **`opencv-python-headless`** em `requirements.txt` (não `opencv-python`)
- **`packages.txt`** se `qr_utils.py` usa `pyzbar`
- **`styles.css`** comitado (tem fallback: o app funciona sem, mas sem
  o estilo customizado da grade)

### Subir para o GitHub

```bash
cd "caminho/para/preparacao-laminas"

git init
git add app.py config.py storage.py processing.py qr_utils.py \
        demo.py clickable.py toolbar.py styles.css \
        requirements.txt packages.txt README.md .gitignore .streamlit/config.toml

# Se houver componente customizado:
git add frontend/

# PDF do guia (opcional):
git add "Preparação das lâminas.pdf"

git commit -m "Preparação de lâminas — v1.0"
git branch -M main
git remote add origin https://github.com/SEU-USUARIO/preparacao-laminas.git
git push -u origin main
```

### Conectar ao Streamlit Cloud

1. Acesse **https://share.streamlit.io**
2. **Sign in with GitHub** → autorize
3. **New app** → preencha:
   - **Repository**: `SEU-USUARIO/preparacao-laminas`
   - **Branch**: `main`
   - **Main file path**: `app.py`
4. **Advanced settings** → confirme que `requirements.txt` está na raiz
5. **Deploy!** (primeira vez leva ~1–2 min, dominado pelo build do
   OpenCV headless)

### O que funciona na nuvem

| Recurso | Cloud | Local |
|---|---|---|
| Grade 8×2 e navegação | ✅ | ✅ |
| Upload de imagem | ✅ | ✅ |
| Geração de demo | ✅ | ✅ |
| Detecção automática | ✅ | ✅ |
| Magic wand / toolbar | ✅ (se `clickable.py`/`toolbar.py` forem compatíveis com Cloud) | ✅ |
| Leitura de QR | ✅ | ✅ |
| Download de `scan_plan.json` | ✅ | ✅ |
| **Gravação local** (`state.json`, `images/`) | ⚠️ **Efêmera** — some no redeploy | ✅ Persiste |
| **Multi-usuário** | ❌ Estado compartilhado e sobrescrito | ❌ Mesmo (arquivo único) |
| **PDF do guia** | ✅ (se comitado) | ✅ |

### Configuração recomendada para Cloud

Se você vai usar no Cloud **além de** local:

1. **Persistência de estado** — troque `storage.py` para usar SQLite em
   `/tmp/state.db` (persiste enquanto o container está de pé) **ou**
   aceite a volatilidade e use o app apenas como demo.
2. **Imagens** — armazene em `st.session_state` se forem pequenas (a
   imagem reduzida cabe em ~1 MB), **ou** em base64 no `state.json`.
3. **`scan_plan.json`** — prefira o **download button** (que o app já
   oferece) ao invés de gravar em disco.

---

## ⚠️ Limitações conhecidas

### Do deploy

- **❌ Depende de 7 módulos locais** — não roda só com `app.py`. Ver
  aviso crítico no topo.
- **⚠️ Filesystem efêmero no Cloud** — `state.json`, `images/` e
  `scan_plan.json` **desaparecem** no redeploy. Para persistência real,
  use DB externo (Postgres, SQLite em volume persistente, S3).
- **❌ Não há autenticação** — qualquer pessoa com o link acessa e
  **sobrescreve** o estado global. Para multiusuário, adicione login
  (`streamlit-authenticator`, Auth0, etc.).
- **⚠️ Componente `clickable`/`toolbar`** — se for componente customizado
  (`frontend/`), o build precisa ser compatível com a versão de
  Streamlit no Cloud. Teste o deploy antes de divulgar o link.

### Do modelo

- **`N_TRAYS` e `SLIDES_PER_TRAY` são fixos** (definidos em `config.py`).
  O app é desenhado para 8×2 por bandeja; layouts diferentes exigem
  alterar `render_tray_grid()` (as duas fileiras de `st.columns(8)`).
- **`DISPLAY_MAX_W = 1400`** — imagens maiores são reduzidas ao carregar.
  Para detectar tecido minúsculo (<0,5 mm), aumente esse valor
  (consome mais banda e memória).
- **Coordenadas exportadas são em pixels da imagem reduzida**, não em
  milímetros. O scanner precisa saber a escala (`mm/px`) para converter
  — isso é responsabilidade do `scan_plan.json` (adicione um campo
  `"scale_mm_per_px"` se seu scanner precisar).

### Do QR

- **`cv2.QRCodeDetector`** — funciona bem em QRs frontais e nítidos,
  falha em fotos com perspectiva ou desfoque. Se suas imagens de bancada
  têm essas características, use `pyzbar` (mais robusto, requer
  `libzbar0`).
- **Apenas o primeiro QR é lido** — se a imagem tiver múltiplos QRs
  (ex.: QR da lâmina + QR do cassete), `read_qr` retorna só o primeiro.
- **QR não é re-lido** — depois de `loaded`, o `qr_id` fica congelado.
  Se você recapturar a imagem, o QR **não** é atualizado automaticamente
  (bug conhecido? verifique `render_slide_prep` linha 290:
  `if qr_data and slide.get("qr_id") != qr_data:` — só atualiza se
  diferente, OK).

### Do modo manual

- **`magic_wand_flood_fill` em CIELAB** — distância de cor é ΔE
  simplificado (não CIE76 completo). Tecidos com cor muito uniforme
  podem gerar **blobs gigantes** que pegam a lâmina inteira. Reduza o
  `threshold` (10–20) nesses casos.
- **CLAHE** — bom para tecido esmaecido, mas introduz **ruído em
  fundo limpo**. Se a imagem tem fundo branco uniforme, mantenha
  desligado.
- **Pendente "recálculo"** — se o slider mudar **enquanto** você
  processa, a região pendente é **recalculada**. Isso é feature, mas
  pode confundir: se você clicou, gostou do resultado, e mexeu no
  slider por acidente, a região muda.

### Do modo auto

- **Os 6 parâmetros são sensíveis à iluminação da bancada** — uma
  imagem capturada com lâmpada quente precisa de `params` diferentes
  de uma com LED. Salve perfis por cenário em `DEFAULT_PARAMS` (ou
  adicione presets).
- **`min_area` em px² da imagem reduzida** — `_detect_small` já escala
  `min_area` por `scale²` internamente, então o valor do slider
  corresponde a px² da imagem **original**. Isso está correto, mas
  dificulta a intuição: 5000 px² em 1400 px de largura = área pequena;
  em 4000 px de largura = área minúscula. Sempre confira a imagem.

### Do export

- **`scan_plan.json` só inclui lâminas `prepared`** — `loaded` e `empty`
  são ignoradas. Se você quer exportar mesmo as vazias (para o scanner
  registrar "não preparada"), edite `render_export()`.
- **`regions` no export omitem `kind="point"`** — pontos únicos são
  marcadores visuais no editor, não regiões de varredura. Se o seu
  scanner usa pontos como "âncoras", remova o filtro.
- **`params` exporta só se o modo foi `specific`** — `whole` exporta
  `params: {}`. Se seu scanner precisa dos parâmetros mesmo em `whole`,
  ajuste `render_export()`.

### Do Streamlit

- **`use_container_width=True`** — deprecated a partir do 1.40;
  o pin `<1.42` mantém funcionando. Para migrar, troque por
  `width="stretch"` (Streamlit ≥1.42).
- **`st.container(key=...)`** — funciona no 1.30+, mas o CSS em
  `styles.css` depende de os keys serem estáveis. Se você adicionar
  containers novos, **mantenha os keys existentes**.

---

## 📚 Referências

Visão computacional e processamento de imagem:

- **OpenCV — `QRCodeDetector`** — https://docs.opencv.org/4.x/d9/d61/tutorial_py_detect_qr_code.html
- **OpenCV — `connectedComponentsWithStats`** — https://docs.opencv.org/4.x/d3/dc0/group__imgproc__shape.html
- **OpenCV — `floodFill`** — https://docs.opencv.org/4.x/d7/d1b/group__imgproc__draw.html
- **CIE Lab color space** — base para a distância de cor do magic wand.
  https://en.wikipedia.org/wiki/CIELAB_color_space
- **Zuiderveld, K. (1994).** Contrast Limited Adaptive Histogram
  Equalization (CLAHE). *Graphics Gems IV*, 474–485.

Padrões de scanner de lâminas:

- **ISO 8037-1:2021** — *Microscopes — Slides — Part 1: Dimensions and
  optical properties*. Lâminas 26 × 76 mm.
- **OpenWSI** — referência open-source de scanner de lâminas:
  https://github.com/AndyFooGuo/OpenWSI
- **OpenFlexure** — referência de microscopia open-hardware:
  https://openflexure.org/

Streamlit e componentes:

- **Streamlit — `st.cache_data`** — https://docs.streamlit.io/library/api-reference/performance/st.cache_data
- **Streamlit — `st.pdf`** — https://docs.streamlit.io/library/api-reference/media/st.pdf
- **Streamlit — custom components** — https://docs.streamlit.io/library/components
- **streamlit-drawable-canvas** (se aplicável) — https://github.com/andfanilo/streamlit-drawable-canvas

> ⚠️ Verifique as referências nas bases primárias antes de citar. A
> API do OpenCV pode variar entre 4.8 e 4.10 em detalhes menores
> (assinatura de `QRCodeDetector`, por exemplo).

---

## 🤝 Contribuindo

Sugestões de evolução:

- **Persistência em DB** — SQLite/Supabase para sobreviver a redeploys
- **Autenticação** — login por operador + auditoria de quem preparou
  cada lâmina
- **Presets de parâmetros** — salvar `params` por cenário (lâmpada,
  tecido, coloração) e recarregar com 1 clique
- **Detecção de tecido por ML** — `cv2.dnn` com modelo leve para
  segmentação (substitui HSV+Canny, mais robusto)
- **Conversão px → mm** no export (adicionar campo `scale_mm_per_px`
  no JSON, lido de `config.py` ou de metadados EXIF da imagem)
- **Visualização 3D da bandeja** — `plotly` para navegar entre
  bandejas com zoom

## 📄 Licença

Distribuído sob a **licença MIT**. Veja [LICENSE](LICENSE) para o texto
completo. Uso acadêmico e comercial permitido, com atribuição.

## 👤 Autor

**André Rocha**
Doutorando em Ciência da Computação — PGCOMP/UFBA
📧 rocha.a@ufba.br

## 🙏 Agradecimentos

- Meu orientador de Doutorado, Prof. Dr. Luciano Oliveira
- Equipe do Laboratório de Patologia (pela validação em bancada)
- Comunidade open-source do Streamlit, OpenCV e NumPy
- [OpenFlexure](https://openflexure.org/) e [OpenWSI](https://github.com/AndyFooGuo/OpenWSI)
  — referências de hardware aberto para patologia digital

---

<p align="center">
  Feito com 🔬 e 🖌️ para patologia digital acessível
</p>
