# Benchmarks — RV32I contra RV32IM

Quatro benchmarks pequenos e determinísticos. Cada um existe em **duas
versões do mesmo algoritmo**:

- `*_rv32i.asm` — só instruções RV32I, com multiplicação e divisão emuladas
  em software;
- `*_rv32im.asm` — a mesma coisa, trocando a emulação pelas instruções da
  extensão M.

As duas versões publicam **os mesmos valores nos mesmos endereços de RAM**.
Isso não é uma convenção de boa vontade: `tools/bench_compare.py` compara o
conteúdo da RAM das duas execuções e **recusa-se a reportar qualquer número de
desempenho** se elas divergirem. Comparar ciclos de dois programas que calculam
coisas diferentes não significaria nada.

> **Os arquivos `.c` NÃO são compilados neste ambiente.**
> Não existe compilador RISC-V aqui — verificado por execução: nem
> `riscv*-elf-gcc`, nem `clang`, nem `llvm-mc`, no Windows ou na WSL. Ver
> [`specs/decisions.md`](../../../specs/decisions.md), ADR-004. Os `.c` são a
> **especificação legível** do algoritmo; o que de fato é montado e executado
> na CPU são os `.asm` ao lado, traduzidos à mão e versionados.

---

## Os quatro benchmarks

Área de resultados: `RESULT_BASE = 0x00FC8100` (`DATA_RAM_BASE_ADDRESS`).
O slot *n* fica em `RESULT_BASE + 4*n`.

### `bench_mul` — multiplicação de inteiros

Os 32 bits baixos de `a * b` para oito pares que cobrem zero, positivos
pequenos, sinais mistos, os dois negativos e overflow modular de 2³².

| slot | caso | resultado |
|---|---|---|
| 0 | `7 * 6` | `0x0000002A` |
| 1 | `123 * 456` | `0x0000DB18` |
| 2 | `-3 * 5` | `0xFFFFFFF1` |
| 3 | `-7 * -8` | `0x00000038` |
| 4 | `65535 * 65537` | `0xFFFFFFFF` (o maior produto que ainda cabe) |
| 5 | `2147483647 * 2` | `0xFFFFFFFE` (overflow) |
| 6 | `-2147483648 * 3` | `0x80000000` (overflow) |
| 7 | `0 * 305419896` | `0x00000000` |

### `bench_div` — divisão e resto

Oito pares `(dividendo, divisor)`, incluindo os dois casos especiais que a
especificação RISC-V manda **não** gerar trap. O slot `2i` guarda o quociente
do caso *i*, o slot `2i+1` o resto.

| caso | par | quociente | resto |
|---|---|---|---|
| 0 | `(100, 7)` | `14` | `2` |
| 1 | `(-100, 7)` | `-14` | `-2` |
| 2 | `(100, -7)` | `-14` | `2` |
| 3 | `(-100, -7)` | `14` | `-2` |
| 4 | `(7, 0)` | `-1` | `7` | ← divisão por zero |
| 5 | `(-2147483648, -1)` | `-2147483648` | `0` | ← overflow |
| 6 | `(2147483647, 2)` | `1073741823` | `1` |
| 7 | `(-2147483648, 3)` | `-715827882` | `-2` |

A divisão trunca **em direção a zero** e o resto carrega o sinal do
**dividendo** — os casos 1 a 3 são justamente os que distinguem essa regra da
divisão euclidiana.

### `bench_dotprod` — produto escalar em laço

Dois vetores de 8 elementos na RAM, multiplicados e acumulados num laço. É o
benchmark que junta load/store, controle de laço e multiplicação.

| slot | caso | resultado |
|---|---|---|
| 0 | produto escalar | `0x540BE518` |
| 1 | soma de A | `0x000186A8` |
| 2 | soma de B | `0x00018790` |
| 3 | número de elementos | `0x00000008` |

O último par é `100000 * 100000`, que estoura 32 bits — o produto escalar é a
palavra baixa modular, não o valor matemático.

### `bench_signs` — extremos e overflow modular

Comportamento dos dois extremos da faixa com sinal sob soma, subtração,
multiplicação, comparação com e sem sinal, e os dois tipos de deslocamento à
direita. Tudo modular em 2³²: **não há saturação e não há trap**.

| slot | caso | resultado |
|---|---|---|
| 0 | `INT32_MAX + 1` | `0x80000000` |
| 1 | `INT32_MIN + (-1)` | `0x7FFFFFFF` |
| 2 | `0 - INT32_MIN` | `0x80000000` |
| 3 | `INT32_MIN * -1` | `0x80000000` |
| 4 | `INT32_MAX * 2` | `0xFFFFFFFE` |
| 5 | `INT32_MIN * INT32_MIN` | `0x00000000` |
| 6 | `INT32_MAX * INT32_MAX` | `0x00000001` |
| 7 | `INT32_MIN < INT32_MAX` (com sinal) | `1` |
| 8 | `INT32_MIN <u INT32_MAX` (sem sinal) | `0` |
| 9 | `INT32_MIN >> 31` (aritmético) | `0xFFFFFFFF` |
| 10 | `INT32_MIN >> 31` (lógico) | `0x00000001` |
| 11 | `(-1) * (-1)` | `0x00000001` |

---

## Formato `.ram`

Definido em [`specs/decisions.md`](../../../specs/decisions.md), ADR-003, e
consumido por `instruction_memory.vhd` através do generic `ROM_INIT_FILE`.

| regra | valor |
|---|---|
| uma palavra por linha | 32 bits |
| grafia | 8 dígitos hexadecimais, sem prefixo `0x`, case-insensitive |
| endereço | linha 0 → byte `0x00000000`; linha *n* → byte `4*n` |
| endianness | o little-endian está na organização de bytes da memória, não na grafia do arquivo |
| comentário | `#` até o fim da linha; linhas vazias ignoradas |
| palavras ausentes | preenchidas com `0x00000000` |
| parada | auto-laço `j halt` (`0x0000006f`) |

Exemplo (`bench_mul_rv32im.ram`):

```
# programa: bench_mul_rv32im
# fonte: cpus/rv32i_pipeline/programs/bench_mul_rv32im.asm
# isa: RV32IM
# palavras: 39   parada em: 0x98
00fc8937
10090913
00700513
...
```

## Como regenerar as imagens

```bash
python cpus/rv32i_pipeline/tools/build_programs.py
```

Monta cada `.asm` e grava o `.ram` ao lado. Os `*_rv32i.asm` são montados com
`allow_m=False`, ou seja, o montador **rejeita** qualquer instrução RV32M — é
assim que se garante que a versão de baseline é RV32I puro (FR-RV-19).

`test_programs.py` confere que as imagens versionadas continuam iguais ao que
o montador produz agora, então uma imagem esquecida desatualizada quebra o
build em vez de passar despercebida.

## Como rodar os benchmarks

```bash
# executa cada benchmark nas duas ISAs e tabula ciclos, CPI, stalls e flushes
python cpus/rv32i_pipeline/tools/bench_compare.py

# verificação funcional (resultados na RAM contra o modelo de referência)
pytest cpus/rv32i_pipeline/test/test_programs.py -v
```
