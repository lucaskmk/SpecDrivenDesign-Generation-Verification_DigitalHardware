# Entregas — onde a CPU do aluno entra

Cada entrega é **uma pasta** dentro deste diretório, com um `cpu.toml` na raiz.
O validador descobre sozinho toda pasta que tenha um `cpu.toml` e roda a suíte
de conformidade em cada uma.

```
entregas/
├── _modelo/              ← copie esta pasta para começar
├── joao_silva/
│   ├── cpu.toml
│   └── src/*.vhd
└── maria_souza/
    ├── cpu.toml
    └── src/*.vhd
```

## Como entregar

```bash
cp -r entregas/_modelo entregas/seu_nome
# escreva o VHDL em entregas/seu_nome/src/ e preencha o cpu.toml
```

## Como rodar

```bash
# valida uma entrega
python -m rvverify entregas/seu_nome

# valida todas as entregas de uma vez
python -m rvverify entregas/
```

Sem argumento nenhum, o validador varre `entregas/` inteiro.

## O que você escreve e o que já vem pronto

Esta é a divisão que importa entender antes de começar.

### Já vem pronto — não reescreva

| O quê | Onde | Por quê já vem pronto |
|---|---|---|
| ROM de instruções | `instruction_memory.vhd` | carrega o programa de um arquivo `.ram` na elaboração; o cocotb **não consegue** escrever em ROM no GHDL, então isso não é opcional |
| RAM e ROM de dados | `data_ram.vhd`, `data_rom.vhd`, `data_memory.vhd` | já são arrays 1-D, que é o único formato que o cocotb consegue ler (ver restrição 1 abaixo) |
| Mapa de memória | `memory_package.vhd` | instruções em `0x00000000`, DATA_ROM em `0x00FC8000`, DATA_RAM em `0x00FC8100` |
| Multiplicador e divisor | `mul_div_unit.vhd` | as 8 instruções RV32M, já verificadas contra a especificação |
| Montador RV32I/RV32IM | `rvverify/asm.py` | `.asm` → `.ram`; não existe compilador RISC-V neste ambiente |
| Modelo de referência | `rvverify/reference.py` | os valores esperados de toda instrução, inclusive os casos especiais |
| A suíte de conformidade | `rvverify/` | é o que julga a sua CPU |

### Você escreve

O **núcleo**: busca, decodificação, banco de registradores, ALU, controle,
e o top-level que amarra o seu núcleo às memórias fornecidas.

E o `cpu.toml`, que diz ao validador onde as coisas estão.

## As três restrições que o manifesto não resolve

Não são burocracia — são limites reais do GHDL descobertos por execução, e
cada uma já causou um bug neste projeto.

**1. Arrays observáveis têm de ser 1-D.** O VPI do GHDL não expõe arrays 2-D
ao cocotb. Se o seu banco de registradores ou a sua RAM forem
`array (0 to N, 3 downto 0) of std_logic_vector(7 downto 0)`, o validador não
consegue ler resultado nenhum — e nenhum campo do `cpu.toml` conserta isso.
Use `array (0 to N) of std_logic_vector(31 downto 0)`.

**2. O programa entra na elaboração, não em runtime.** Escrever na ROM pelo
cocotb é silenciosamente ignorado pelo GHDL. Por isso a `instruction_memory.vhd`
fornecida tem o generic `ROM_INIT_FILE`, e por isso usá-la é requisito.

**3. Guarda de faixa e índice de array na mesma expressão.** Se você escrever

```vhdl
signal in_range : boolean;
in_range <= word_index < N;                              -- ERRADO
data_out <= memory(word_index) when in_range else ...;
```

o sinal `in_range` atrasa um delta em relação a `word_index`, e um endereço
fora de faixa indexa o array antes de a guarda alcançar:
`ghdl:error: index (...) out of bounds`. Mantenha os dois na mesma expressão
condicional.

## Os dois caminhos

**Modifico uma CPU que já existe.** Comece de
[`cpus/rv32i_pipeline`](../cpus/rv32i_pipeline/) — pipeline de 5 estágios, RV32I
completo, já verificada. O `cpu.toml` dela serve de referência.

**Faço do zero.** Comece de
[`cpus/rv32i_monociclo`](../cpus/rv32i_monociclo/) — monociclo, bem
mais simples de entender, usando as mesmas memórias fornecidas.

Os dois já estão no repositório e os dois passam na mesma suíte de
conformidade. Essa é a prova de que o validador julga o comportamento da sua
CPU, e não o formato dela.

## O que o validador reporta

Ele reporta o que consegue observar e diz o que não conseguiu — nunca inventa
métrica que não mediu.

| você declarou no `cpu.toml` | você recebe |
|---|---|
| só `[observe].ram` | correção funcional: as instruções, os casos de borda, divisão por zero |
| `+ [observe].registers` | verificação de registradores também |
| `+ [metrics]` | instruções, CPI, stalls, flushes, instruções RV32M |

Sem `[metrics]`, o CPI sai como `null` com o motivo — e não como um número
chutado.

## Versionamento

As pastas de entrega ficam versionadas junto com o resto. Se você preferir
manter as suas fora do git, acrescente ao `.gitignore` da raiz:

```
entregas/*
!entregas/_modelo/
!entregas/README.md
```
