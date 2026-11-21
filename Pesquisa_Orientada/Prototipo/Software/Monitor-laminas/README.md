# 🔬 Monitor de Lâminas — 16 LDRs via Serial

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Local only](https://img.shields.io/badge/deploy-LOCAL%20ONLY-red.svg)](#-por-que-não-funciona-no-cloud)

Aplicação **Streamlit** que monitora em **tempo real** a presença/ausência
de **16 lâminas histológicas** em uma bandeja do scanner, lendo **16
sensores LDR** (Light Dependent Resistors) via **ADC de 10 bits** (0–1023)
de um Arduino, com **limiares ajustáveis por slot** e **modo de
comparação configurável** (maior/menor que o limiar).

- **Grid visual 8 × 2** representando os 16 slots da bandeja
- **Limiar global** + **limiar individual por slot** (sobreposição configurável)
- **Sugestão automática** de limiar com base no min/max observado
- **Estatísticas por slot** (min, máx, sugestão) com reset
- **Atualização automática** a cada 300 ms (`streamlit-autorefresh`)
- **Thread de leitura** separada (não bloqueia a UI)

---

## ⚠️ Por que não funciona no Cloud

**Este app é *local-only*.** Ele depende de acesso direto à **porta serial
USB** do Arduino — algo que o servidor do Streamlit Cloud **não tem**.

### O que acontece se você deployar no Cloud

1. O app **abre normalmente** (interface, sidebar, grid cinza, métricas zeradas)
2. `serial.tools.list_ports.comports()` retorna `[]` → a sidebar mostra
   um `text_input` com valor padrão `/dev/ttyUSB0`
3. Você clica em **▶ Iniciar**
4. A thread tenta abrir `/dev/ttyUSB0` **5 vezes** (0,6 s entre tentativas)
5. Após ~3 s, mostra o erro controlado:

   > ❌ Não foi possível abrir **/dev/ttyUSB0** após 5 tentativas.
   > **Último erro:** `[Errno 2] could not open port /dev/ttyUSB0: ...`

6. O app **não trava** — continua na tela, permite editar parâmetros e
   reiniciar. Mas **nunca lerá dados**.

### Conclusão prática

| Uso | Onde rodar |
|---|---|
| **Monitorar as 16 lâminas de verdade** | **Local** (seu PC, com o Arduino plugado) |
| Demonstrar a interface para a banca | Cloud (mas avise que não há hardware) |
| Servir de figura no artigo | **Local** (screenshot com LDRs ativos) |

Este app é **execution layer** — fala com o hardware, não faz planejamento
offline. É a evolução do app "Monitor de Bandejas" (8 slots binários via
PCF8574) para **16 slots analógicos** com ajuste fino de limiar por LDR.

---

## 📑 Índice

- [Demonstração online (limitada)](#-demonstração-online-limitada)
- [Estrutura do repositório](#-estrutura-do-repositório)
- [Hardware](#-hardware)
- [Protocolo serial](#-protocolo-serial)
- [Instalação](#-instalação)
- [Uso](#-uso)
- [Guia de sintonia dos limiares](#-guia-de-sintonia-dos-limiares)
- [Troubleshooting](#-troubleshooting)
- [Notas de arquitetura](#-notas-de-arquitetura)
- [Limitações conhecidas](#-limitações-conhecidas)
- [Referências](#-referências)
- [Licença](#-licença)

---

## 🚀 Demonstração online (limitada)

🔗 **[Abrir no Streamlit Cloud](https://SEU-USUARIO-monitor-laminas.streamlit.app)**

> ⚠️ **Na nuvem, apenas a *interface* funciona.** A leitura dos LDRs exige
> o Arduino + MUX + 16 LDRs plugados via USB no seu PC — algo que o
> servidor Cloud não tem acesso.

A versão online serve **apenas** para:

- Visualizar o layout, a sidebar e o grid antes de montar o hardware
- Mostrar a interface para orientador/banca em revisão remota
- Servir de mockup no artigo/tese (mas use um **screenshot local** com
  LDRs ativos, que fica mais convincente)

---

## 📁 Estrutura do repositório

```
Monitor-Laminas/
│
├── app.py                              # Aplicação Streamlit (ponto de entrada)
├── requirements.txt                    # Dependências (Streamlit + pandas + pyserial + autorefresh)
├── README.md                           # Este arquivo
├── LICENSE                             # Licença MIT
├── .gitignore                          # Arquivos que não devem ir ao Git
│
├── .streamlit/
│   └── config.toml                     # Tema, telemetria desligada
│
├── firmware/
│   └── SlideMonitor_16LDR_MUX.ino      # Sketch do Arduino (16 LDR via CD74HC4067)
│
└── docs/
    ├── schematic.png                   # Diagrama Arduino + MUX + LDRs
    ├── foto-bandeja.jpg                # Foto da bandeja com LDRs
    └── screenshot-painel.png           # Screenshot do grid 8×2 funcionando
```

### Descrição de cada arquivo

| Arquivo | Conteúdo |
|---|---|
| **`app.py`** | Aplicação inteira: thread de leitura serial, estado global via `cache_resource`, grid CSS 8×2, sidebar com limiares global + individual, sugestão automática, estatísticas por slot. ~380 linhas. |
| **`requirements.txt`** | Dependências (Streamlit + pandas + pyserial + streamlit-autorefresh). |
| **`README.md`** | Documentação (este arquivo). |
| **`LICENSE`** | Licença MIT. |
| **`.gitignore`** | Ignora `__pycache__/`, `.venv/`, `.streamlit/secrets.toml`. |
| **`firmware/SlideMonitor_16LDR_MUX.ino`** | Sketch do Arduino que varre 16 canais via CD74HC4067, lê cada LDR, e envia `Canal N: V` + `---`. |
| **`docs/`** | Imagens para o README e para o artigo. |

### O que **não** vai no repositório

```
__pycache__/
.venv/, venv/
*.log
.streamlit/secrets.toml
```

---

## 🔧 Hardware

### Estratégia de aquisição (16 canais analógicos)

O `app.py` espera **16 valores ADC de 10 bits** (0–1023). Há **duas
arquiteturas viáveis** — escolha a que você tem em mãos:

#### Opção A — Arduino Uno + MUX CD74HC4067 (recomendada, mais barata)

O Uno só tem 6 pinos analógicos, insuficientes para 16 LDRs. Um **MUX
analógico 16:1** (CD74HC4067) resolve com **1 pino analógico + 4 digitais
de seleção**:

```
┌──────────────────┐
│  Arduino Uno     │         ┌───────────────────┐
│                  │         │  CD74HC4067       │
│  A0 ─────────────┼─────────┼── SIG (COM)       │
│  D2 ─────────────┼─────────┼── S0              │
│  D3 ─────────────┼─────────┼── S1              │
│  D4 ─────────────┼─────────┼── S2              │
│  D5 ─────────────┼─────────┼── S3              │
│  5V ─────────────┼─────────┼── VCC + EN(GND)   │
│  GND ────────────┼─────────┼── GND             │
│                  │         │                   │
│  USB ──► PC      │         │  CH0 ── LDR #1    │
│                  │         │  CH1 ── LDR #2    │
│                  │         │   ...             │
│                  │         │  CH15 ─ LDR #16   │
└──────────────────┘         └───────────────────┘
```

Cada LDR vai em um **divisor de tensão** com resistor fixo de 10 kΩ:

```
        +5V
         │
        ┌┴┐
        │ │ LDR (GL5528 ou similar)
        └┬┘
         ├──────► canal do MUX (CHx)
        ┌┴┐
        │ │ 10 kΩ
        └┬┘
         │
        GND
```

- **Sem lâmina** → LDR recebe luz → resistência baixa → **tensão alta** (ADC alto)
- **Com lâmina** → LDR na sombra → resistência alta → **tensão baixa** (ADC baixo)

Por isso o modo padrão do app é **"Maior que o limiar" = presente** (a
lâmina bloqueia a luz). **Se o seu LDR está invertido** (luz → resistência
alta), o divisor pode trocar os papéis — o app tem a opção
**"Menor que o limiar"** exatamente para isso.

#### Opção B — Arduino Mega (16 pinos analógicos nativos)

O Mega tem **16 entradas analógicas** (A0–A15), sem MUX. Mais caro, mais
simples, menos fios. Bom se você já tem um Mega sobrando.

```
Arduino Mega
  A0  ── LDR #1  (divisor 10 kΩ)
  A1  ── LDR #2
  ...
  A15 ── LDR #16
  GND ── GND dos divisores
  5V  ── 5V dos divisores
```

### Lista de materiais (BOM)

| Componente | Especificação | Qtd (Opção A) | Qtd (Opção B) |
|---|---|---|---|
| Microcontrolador | Arduino Uno R3 | 1 | — |
| Microcontrolador | Arduino Mega 2560 | — | 1 |
| MUX analógico | CD74HC4067 (16:1) | 1 | — |
| LDR | GL5528 (ou GL5516) | 16 | 16 |
| Resistores | 10 kΩ (1/4 W) | 16 | 16 |
| Fios, jumpers | Macho-fêmea + macho-macho | — | — |
| Cabo USB | A-B (Uno/Mega) | 1 | 1 |

### Layout físico (8 × 2)

O grid do app representa a bandeja como **8 colunas × 2 linhas**:

- **L1..L8** = linha superior (slots 1–8)
- **L9..L16** = linha inferior (slots 9–16)
- Cada célula tem `aspect-ratio: 1/3` (mais alta que larga) — condizente
  com lâminas verticais de ~26 × 76 mm

**Ordene os LDRs fisicamente na mesma ordem do grid** (L1 no canto
superior esquerdo, L8 no superior direito, L9 no inferior esquerdo, etc.).
Se bagunçar, use o editor de limiares individuais para compensar — mas
é mais fácil acertar a fiação.

---

## 📡 Protocolo serial

O `app.py` **não envia nada** para o Arduino — ele só **lê**. O firmware
do Arduino deve enviar, ciclicamente, um bloco de **16 linhas + terminador**:

```
Canal 0: 812
Canal 1: 807
Canal 2: 215
Canal 3: 198
Canal 4: 790
Canal 5: 185
Canal 6: 803
Canal 7: 795
Canal 8: 210
Canal 9: 205
Canal 10: 802
Canal 11: 799
Canal 12: 808
Canal 13: 190
Canal 14: 815
Canal 15: 201
---
```

### Regras que o `app.py` espera

| Padrão | Significado |
|---|---|
| `Canal N: V` (regex `Canal\s+(\d+)\s*:\s*(\d+)`) | Canal N (0–15) leu valor V (0–1023) |
| Linha começando com `---` | Fim do bloco → os valores são commitados em `leituras` e `ciclos += 1` |
| Qualquer outra linha | Ignorada (bytes contabilizados no diagnóstico) |

### Interpretação dos valores

| Cenário físico | ADC esperado | Modo padrão ("Maior") |
|---|---|---|
| Lâmina **presente** (bloqueia luz) | baixo (~150–300) | ❌ ausente |
| Lâmina **ausente** (LDR iluminado) | alto (~700–900) | ✅ presente |

**⚠️ Os valores acima assumem divisor LDR-no-topo + 10 kΩ embaixo.**
Se a sua fiação inverter (LDR embaixo), os valores trocam de lado e
você precisa mudar o **modo** para **"Menor que o limiar"** na sidebar.
O app tem a opção exatamente para isso — veja
[Guia de sintonia dos limiares](#-guia-de-sintonia-dos-limiares).

### Firmware mínimo de referência (Opção A — CD74HC4067)

```cpp
#define SIG   A0
#define S0    2
#define S1    3
#define S2    4
#define S3    5
#define INTERVALO_MS 250

void setup() {
    Serial.begin(115200);
    pinMode(S0, OUTPUT);
    pinMode(S1, OUTPUT);
    pinMode(S2, OUTPUT);
    pinMode(S3, OUTPUT);
}

void loop() {
    for (int canal = 0; canal < 16; canal++) {
        // Seleciona canal no MUX (S3 S2 S1 S0 = bits do canal)
        digitalWrite(S0, (canal >> 0) & 1);
        digitalWrite(S1, (canal >> 1) & 1);
        digitalWrite(S2, (canal >> 2) & 1);
        digitalWrite(S3, (canal >> 3) & 1);
        delayMicroseconds(50);              // settling do MUX

        int valor = analogRead(SIG);        // 0..1023
        Serial.print("Canal ");
        Serial.print(canal);
        Serial.print(": ");
        Serial.println(valor);
    }
    Serial.println("---");
    delay(INTERVALO_MS);
}
```

Salve como `firmware/SlideMonitor_16LDR_MUX.ino`. Com
`INTERVALO_MS = 250`, o app recebe ~4 ciclos/s — o painel atualiza a
cada 300 ms, então você vê **todos** os ciclos.

Para a **Opção B (Mega)**, troque o `analogRead(SIG)` por
`analogRead(canal)` (A0 = canal 0, A1 = canal 1, ...) e remova os
`digitalWrite` do MUX.

---

## ⚙️ Instalação

### Requisitos

- Python **3.10+**
- Windows 10/11, Linux ou macOS
- **Arduino** com firmware gravado (Uno+MUX ou Mega)
- **Driver CH340** (clones) ou **FTDI** (originais) instalado
- Cabo USB com **dados** (não apenas carga)

### Passo a passo

```bash
# 1. Clone o repositório
git clone https://github.com/SEU-USUARIO/monitor-laminas.git
cd monitor-laminas

# 2. Ambiente virtual (recomendado)
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux / macOS:
source .venv/bin/activate

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Grave o firmware no Arduino
#    Abra firmware/SlideMonitor_16LDR_MUX.ino no Arduino IDE
#    Feche o Monitor Serial ANTES de rodar o Streamlit

# 5. Rode o app
streamlit run app.py
```

O navegador abre automaticamente em `http://localhost:8501`.

### Notas por sistema operacional

**Windows**
- **Feche o Monitor Serial do Arduino IDE** antes de rodar o Streamlit —
  a porta é exclusiva.
- **Feche outras abas do navegador** com este app aberto — cada aba cria
  uma sessão que tenta abrir a porta; só a primeira consegue.

**Linux**
- Adicione seu usuário ao grupo `dialout`:
  ```bash
  sudo usermod -a -G dialout $USER
  # logout e login novamente (ou: newgrp dialout)
  ```

**macOS**
- Porta típica: `/dev/tty.usbserial-XXXX` ou `/dev/cu.usbserial-XXXX`.
- Driver CH340 é built-in a partir do macOS 13.

---

## 🎮 Uso

### Fluxo básico

1. **Plugue o Arduino** no PC via USB
2. **Feche qualquer outro programa** que use a porta (IDE do Arduino,
   outra aba, `screen`, `minicom`)
3. **Sidebar → Porta serial** — selecione a porta que aparece
4. **Sidebar → Baud rate** — `115200` (o firmware de referência usa esse)
5. Clique em **▶ Iniciar**

O app:

- Abre a porta e aguarda **2 s** (auto-reset do Arduino após abrir a serial)
- Começa a ler as linhas `Canal N: V` + `---`
- Atualiza o grid 8×2 a cada **300 ms**
- Incrementa o contador de **Ciclos** a cada bloco completo
- Alimenta as estatísticas `slot_min`/`slot_max` por slot

### Lendo o grid

- **Célula verde** = lâmina **presente** (classificação pelo limiar)
- **Célula vermelha** = lâmina **ausente**
- **Célula cinza** = sem leitura ainda (antes do primeiro ciclo)
- **L1..L16** = identificador do slot
- **`✔`/`✖`** = estado classificado
- **`812`** = valor ADC bruto lido
- **`>500`** = operador + limiar aplicado naquele slot

### Métricas e diagnóstico

- **🟢 Presentes** — quantas lâminas classificadas como presentes
- **🔴 Ausentes** — quantas classificadas como ausentes
- **⚪ Sem leitura** — slots ainda sem primeiro ciclo
- **📦 Ciclos** — quantos blocos completos chegaram
- **🩺 Diagnóstico** — bytes totais, última linha crua, tabela slot a
  slot com valor + limiar aplicado

### Parando

- **⏹ Parar** — sinaliza a thread via `stop_event` e aguarda até 3 s.
  A porta é fechada.
- **Fechar a aba do navegador** — o Streamlit **não** mata a thread
  (ela é daemon e o processo continua vivo enquanto outra aba/sessão
  usar o app). **Sempre clique em Parar** antes de fechar.

---

## 🎯 Guia de sintonia dos limiares

**Este é o passo mais importante.** LDRs têm tolerância de ±20% entre
unidades do mesmo lote e respondem de forma diferente à iluminação da
bancada. Sem calibrar, o app vai classificar errado.

### Passo 1 — Verificar o modo (Maior/Menor)

Depois de clicar em Iniciar com as lâminas **todas presentes** (ou todas
ausentes):

- **Se todas as células aparecem verdes** mesmo com slots vazios →
  troque o **modo** para **"Menor que o limiar"**
- **Se todas aparecem vermelhas** com lâminas presentes → troque o
  **modo** para **"Maior que o limiar"**

O critério é simples: a direção do modo deve fazer **lâminas presentes =
verde**.

### Passo 2 — Limiar global (ponto de partida)

Com uma lâmina presente em **alguns** slots e ausente em **outros**:

- O app mostra `Faixa atual: 185 (min) … 815 (max)` na sidebar
- O app sugere um limiar (`int(vmin / 1.10)` no código atual)
- Clique em **"Aplicar sugestão global"** para usar

> ⚠️ **Atenção à heurística `vmin / 1.10`.** Ela gera um limiar **abaixo**
> do mínimo observado — o que, no modo "Maior que", faz **todos** os
> slots ficarem "presentes" (inclusive os vazios). Se o resultado
> parecer invertido, **mude para `* 1.10`** (limiar acima do máximo) ou
> ajuste o slider manualmente para o **meio da faixa** (~500 no exemplo
> acima). O próprio código reconhece essa ambiguidade em um comentário
> na linha do `sugestao = int(vmin / 1.10)`.

**Boa prática:** o limiar ideal fica na **metade da faixa dinâmica**,
entre o valor típico de "presente" (~200) e de "ausente" (~800). Comece
com **500** e ajuste.

### Passo 3 — Limiares individuais (ajuste fino)

Se **um slot específico** classifica errado mesmo com o global correto
(ex.: L5 sempre verde, mesmo vazio), é porque o LDR dele tem resposta
diferente:

1. Abra o expander **🔧 Limiares individuais por slot**
2. Marque **"Usar limiar individual"**
3. Clique em **✨ Sugestões** — preenche cada slot com base em `min/1.10`
   do próprio slot
4. Edite manualmente as células problemáticas na tabela
5. Confira no grid se a classificação ficou correta

O editor aceita **vazio** (= usa o global) ou um inteiro 0–1023.
**Limpar** volta todos a `None`.

### Passo 4 — Recalibração

Quando recalibrar:

- **Trocar lâmpada da bancada** → **🗑️ Zerar estatísticas** → repetir passo 2
- **Mudar fiação** → **🗑️ Zerar estatísticas** → repetir passo 2
- **Trocar um LDR** → ajustar só o limiar individual desse slot

As estatísticas `slot_min`/`slot_max` acumulam ao longo do tempo de
sessão — por isso o botão de zerar.

### Dica: imagem para o artigo

Para a figura do método:

1. Coloque **8 lâminas** nos slots L1–L8 (linha superior) e deixe L9–L16
   vazios
2. Calibre os limiares até o grid mostrar **8 verdes em cima + 8
   vermelhos embaixo**
3. Screenshot em zoom 150%
4. Legenda sugerida: *"Grid de monitoramento: verde = lâmina presente,
   vermelho = ausente; valores ADC por slot em tempo real."*

---

## 🩺 Troubleshooting

### "❌ Não foi possível abrir **COM5** após 5 tentativas"

O app lista 5 passos na ordem certa:

1. **Monitor Serial da IDE do Arduino está fechado?**
2. **Outra aba do navegador** com este app aberto? Feche-a.
3. **Outro `streamlit run`** em outro terminal? Feche com Ctrl+C.
4. **Desconecte e reconecte** o cabo USB (reseta o CH340).
5. **Reinicie o PC** — último recurso.

### "A porta abriu, mas nenhum dado chegou"

O app detecta e avisa. Causas comuns:

- **Baud rate errado** — firmware usa `115200`, você selecionou `9600`.
- **Firmware não envia o terminador `---`** — o app só commita o bloco
  quando vê `---`. Sem ele, `leituras` fica `None`.
- **Cabo USB de "carregador"** — sem fios de dados. Troque o cabo.
- **MUX mal endereçado** — todos os canais leem o mesmo valor. Confira
  `S0..S3` no firmware.

### "Todos os slots leem 0" ou "Todos leem 1023"

- **Divisor de tensão faltando** — LDR sem resistor de 10 kΩ puxa o
  canal direto para 5V ou GND.
- **MUX com EN (enable) alto** — o CD74HC4067 tem pino `EN` ativo-baixo;
  aterre-o.
- **Fiação invertida** — LDR e resistor trocados de posição.

### "Um slot específico sempre erra a classificação"

É a **tolerância do LDR**. Use o limiar individual para esse slot
(passo 3 do guia acima).

### "Permission denied: '/dev/ttyUSB0'" (Linux)

Usuário não está no grupo `dialout`. Veja [Notas por sistema
operacional](#notas-por-sistema-operacional).

### Estatísticas de min/máx parecem erradas

Elas **acumulam desde o Iniciar** e **não** zeram automaticamente. Se
você trocou lâmpada ou mexeu na fiação, clique em **🗑️ Zerar
estatísticas** antes de confiar na sugestão.

---

## 🏗️ Notas de arquitetura

### Estado global via `@st.cache_resource`

O `app.py` persiste `E` (a classe `Estado`) entre reruns via
`@st.cache_resource`. Sem isso, cada clique de botão (que dispara um
rerun) recriaria `E` e perderia a thread, as leituras e as estatísticas.

```python
@st.cache_resource
def _get_estado(v: int = 2):   # v=2 porque o Estado mudou (16 slots + limiares)
    return Estado()
```

**Se você editar a classe `Estado`**, **bumpe `v`** (2 → 3) — senão o
Streamlit pode reaproveitar uma instância antiga com atributos faltando
(ex.: `slot_min` não existia em `v=1`), gerando `AttributeError`.

### Thread + lock

- `E.lock` (`threading.Lock`) protege **todas** as mutações de `E` feitas
  pela thread de leitura (`bytes`, `ciclos`, `leituras`, `slot_min`,
  `slot_max`, `erro`)
- A UI lê `E.leituras`, `E.limiares_slot`, `E.slot_min`, `E.slot_max`
  **com** o lock — sem isso, você pega listas pela metade durante o
  `copy()` ou durante o commit do `buf`
- `E.stop_event` (`threading.Event`) — clicar em Parar faz `set()`,
  e a thread vê `stop.is_set()` no topo do `while` e sai

### Versionamento do editor

`st.data_editor` com `key=ed_key` reutiliza o estado interno entre
reruns. Para permitir **reset limpo** dos limiares (botão Sugestões ou
Limpar), o app usa `st.session_state.ed_ver` — a cada incremento, o
`key` muda (`ed_lim_0` → `ed_lim_1`), e o Streamlit cria um editor
novo com os valores atuais. Sem isso, os botões não surtiriam efeito.

### Por que `slot_min`/`slot_max` e não `slot_atual`?

O app **não** filtra ruído da leitura atual — ele mostra o valor ADC
cru de cada slot no grid. As estatísticas `min/max` servem apenas para
**calcular a sugestão de limiar** e para o painel de estatísticas. A
classificação (verde/vermelho) é feita sobre o **valor instantâneo**,
não sobre a média. Se você quiser mediana móvel ou filtro de Kalman,
é evolução (ver [Contribuindo](#-contribuindo)).

### Grid 8×2 vs 1×8 do app anterior

O "Monitor de Bandejas" (8 slots) usava layout **1 × 8** (bandejas
empilhadas). Este app (16 lâminas) usa **8 × 2** — mais próximo de uma
**bandeja real** de scanner (8 colunas de lâminas verticais, 2 fileiras).
Cada célula tem `aspect-ratio: 1/3` para refletir a proporção
lâmina (26 × 76 mm ≈ 1:2,9).

---

## ⚠️ Limitações conhecidas

### Do deploy

- **❌ Não funciona no Streamlit Cloud** — sem porta serial USB.
- **❌ Não funciona em container Docker sem `--device`** — precisa
  passar `/dev/ttyUSB0` explicitamente.
- **⚠️ Não funciona em rede** — a porta serial é local. Para monitorar
  de outra máquina, use SSH/port-forward para o PC que tem o Arduino.

### Do hardware

- **16 slots fixos** — `leituras = [None] * 16` é hard-coded no `Estado`,
  no `buf`, no grid. Para 24 lâminas (ex.: Pimaco de 3 fileiras), reescreva.
- **ADC 10 bits (0–1023)** — o slider vai até 1023 e o `data_editor`
  limita a 1023. Se você migrar para **ESP32** (ADC 12 bits, 0–4095),
  ajuste `st.slider`, `NumberColumn(max_value=...)` e a documentação.
- **MUX CD74HC4067** tem resistência de canal (~70 Ω) que pode introduzir
  erro de ~0,5% na leitura. Aceitável para esta aplicação (limiar
  binário), mas relevante se você quiser medição absoluta de lux.
- **Não há filtro temporal** — uma única leitura instável (ruído, piscada
  de lâmpada fluorescente) faz o slot piscar verde↔vermelho. O refresh
  de 300 ms mascara parcialmente, mas não filtra.

### Do software

- **Heurística de sugestão `vmin/1.10` é ambígua** — ver [Passo
  2](#passo-2--limiar-global-ponto-de-partida). O próprio código
  reconhece isso em comentário; ajuste manualmente se o resultado
  parecer invertido.
- **Sem log persistente** — fechar o app perde ciclo, estatísticas e
  limiares individuais. Para persistir, adicione `st.download_button`
  do `df_edit` + `json` dos limiares, ou `logging` em arquivo.
- **Sem validação de firmware** — se o firmware mudar para `CANAL:N:V`
  (maiúsculas), `canal N: V` (minúsculas) ou outro separador, o regex
  falha silenciosamente e `leituras` fica `None`. O diagnóstico mostra
  a última linha crua — use para debug.
- **Auto-reset de 2 s** — o `time.sleep(2)` após abrir a serial é para
  o Arduino reiniciar após o DTR. Se o seu não tem auto-reset, reduza
  ou remova.
- **`use_container_width=True`** em `st.button`, `st.data_editor`,
  `st.popover` — deprecated a partir do Streamlit 1.40; o pin `<1.42`
  mantém funcionando. Para migrar, troque por `width="stretch"`.
- **`st.popover` exige Streamlit ≥ 1.31** — se você fez downgrade para
  uma versão muito antiga, o app quebra nessa linha.

### Do escopo científico

- **Classificação binária simples** — o valor científico está na
  **calibração por slot** com LDRs de baixo custo (~R$ 0,50 cada), não
  no algoritmo. Comparar com **câmeras + visão computacional** ou
  **sensores indutivos** fica como trabalho futuro.
- **Sem detecção de "lâmina torta"** — o app só vê presente/ausente.
  Se a lâmina estiver fora do slot, o LDR ainda pode ler "presente"
  se ela refletir luz lateralmente. Um sensor de proximidade ajudaria.

---

## 📚 Referências

Hardware e datasheets:

- **Datasheet CD74HC4067** — *16-Channel Analog Multiplexer/Demultiplexer*.
  Texas Instruments. https://www.ti.com/lit/ds/symlink/cd74hc4067.pdf
- **Datasheet GL5528** — *Photoresistor* (LDR). Senba / genérico.
  https://www.alldatasheet.com (busque por "GL5528")
- **Arduino — `analogRead()`** — https://www.arduino.cc/reference/en/language/functions/analog-io/analogread/

Streamlit e threading:

- **Streamlit — `st.cache_resource`** — https://docs.streamlit.io/library/api-reference/performance/st.cache_resource
- **Streamlit — `st.data_editor`** — https://docs.streamlit.io/library/api-reference/data/st.data_editor
- **Streamlit — `st.popover`** — https://docs.streamlit.io/library/api-reference/layout/st.popover
- **streamlit-autorefresh** — https://github.com/kmcgrady/streamlit-autorefresh
- **Python `threading`** — https://docs.python.org/3/library/threading.html

Scanner histológico de baixo custo:

- **OpenWSI** — referência open-source de scanner de lâminas:
  https://github.com/AndyFooGuo/OpenWSI
- **OpenFlexure** — referência de microscopia open-hardware:
  https://openflexure.org/

> ⚠️ Verifique datasheets nas fontes primárias antes de citar. A
> resposta dos LDRs varia entre lotes e fabricantes — **sempre calibre**
> com a bancada real antes de confiar nos limiares sugeridos.

---

## 🤝 Contribuindo

Sugestões de evolução:

- **Filtro temporal** — mediana móvel de 3–5 leituras para eliminar
  cintilação de lâmpada fluorescente
- **Persistência** — exportar `slot_min`, `slot_max` e `limiares_slot`
  em JSON/CSV, e importar de volta na inicialização
- **Log de mudanças de estado** — timestamp + slot + estado, para
  auditoria de quando cada lâmina entrou/saiu
- **Layout configurável** — `cols` e `rows` na sidebar (suportar 8×3,
  4×4, etc.)
- **Suporte a ESP32** — ADC 12 bits (0–4095), ajustar slider e editor
- **Alerta sonoro/visual** — piscar a célula quando uma lâmina sai do
  lugar inesperadamente

## 📄 Licença

Distribuído sob a **licença MIT**. Veja [LICENSE](LICENSE) para o texto
completo. Uso acadêmico e comercial permitido, com atribuição.

## 👤 Autor

**André Rocha**
Doutorando em Ciência da Computação — PGCOMP/UFBA
📧 rocha.a@ufba.br

## 🙏 Agradecimentos

- Meu orientador de Doutorado, Prof. Dr. Luciano Oliveira
- Equipe do Laboratório de Patologia (pela validação da bandeja em bancada)
- Comunidade open-source do Streamlit, pyserial e Arduino
- [OpenFlexure](https://openflexure.org/) e [OpenWSI](https://github.com/AndyFooGuo/OpenWSI)
  — referências de hardware aberto para patologia digital

---

<p align="center">
  Feito com 🔬 e 💡 para patologia digital acessível
</p>
