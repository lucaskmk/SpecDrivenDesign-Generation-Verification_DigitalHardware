# Relatório final — CPU `rv32im_sc` (opus_5_RISCVIM)

Fase 6 do pipeline SpecHDL. Rastreabilidade requisito → bloco → arquivo VHDL →
resultado de teste → métrica PPA, como exige a
[constituição](../../specs/constitution.md), princípio 2.

> **Natureza deste diretório.** Esta CPU é **saída do pipeline**, não parte
> dele: as fases 1 a 3 (rubrica → spec → arquitetura → VHDL) foram executadas
> contra [`specs/rubrica.md`](specs/rubrica.md), e o resultado é o RTL de
> [`src/`](src/). O diretório é um **teste de implementação**: serve para
> exercitar a metodologia do repositório de ponta a ponta num alvo realista.

## Veredito

| item | resultado | evidência |
|---|---|---|
| **Conformidade RV32I + RV32IM** | **APROVADO** — 35/35 casos, exit code 0 | [`verification/conformance_result.json`](verification/conformance_result.json) |
| Etapa RV32I (baseline) | 24/24 | idem |
| Etapa RV32IM (extensão) | 11/11 | idem |
| Requisitos do validador exercitados | 6/6 atendidos | idem |
| Suítes de bloco | 10 suítes, **48/48** testes | [`verification/block_results.json`](verification/block_results.json) |
| Área (síntese real, LUT4) | RV32I **3 138** (atende NFR-01) · RV32IM **12 657** (**excede em 27 %**) | [`ppa/ppa.json`](ppa/ppa.json) |
| Frequência máxima | **NÃO MEDIDA** — sem ferramenta de timing | ver "O que não foi medido" |
| Potência | **NÃO MEDIDA** — sem ferramenta | ver "O que não foi medido" |

Nenhuma linha desta tabela foi inferida do código. Cada uma corresponde a uma
execução real cujo log está versionado ao lado (constituição, princípios 4 e
10).

## Como reproduzir

Tudo roda na imagem [`docker/Dockerfile`](../../docker/Dockerfile) do
repositório (GHDL 2.0.0 mcode, cocotb 2.0.0, Yosys 0.23, binutils RISC-V 2.40).
Nenhum passo exige instalar ferramenta no host.

```bash
docker build -t spechdl-toolchain -f docker/Dockerfile docker   # uma vez

# Fase 4 -- as 10 suites de bloco
docker run --rm -v "${PWD}:/job" spechdl-toolchain \
  sh -c 'cd /job/implemetation_tests/opus_5_RISCVIM/test && for b in */; do make -C "$b"; done'

# Fase 4b -- conformidade RV32I + RV32IM (o veredito)
docker run --rm -v "${PWD}:/job" spechdl-toolchain \
  python3 -m rvverify implemetation_tests/opus_5_RISCVIM --sem-cor

# Fase 5 -- area por sintese real (regenera ppa/ppa.json a partir dos logs)
docker run --rm -v "${PWD}:/job" spechdl-toolchain \
  sh -c 'cd /job/implemetation_tests/opus_5_RISCVIM && python3 ppa/build_ppa.py'
```

## Arquitetura verificada

RV32IM monociclo, Harvard, controle hardwired combinacional. 11 blocos, 45
instruções declaradas (37 RV32I + 8 M). Decisões e alternativas com
justificativa em NFR estão em
[`specs/architecture.json`](specs/architecture.json).

| região | faixa | tamanho |
|---|---|---|
| ROM de instruções (`.text` + `.rodata`) | `0x00000000`–`0x00000FFF` | 4 KB / 1024 palavras |
| RAM de dados (scratchpad) | `0x00FC8000`–`0x00FC8FFF` | 4 KB / 1024 palavras |

## Rastreabilidade

O `REQ` de cada arquivo VHDL vem do comentário `-- REQ:` no seu cabeçalho; a
coluna de teste vem do `results.xml` real de cada suíte.

| requisito | blocos | arquivo VHDL | teste de bloco | células genéricas rv32i → rv32im ⚠ |
|---|---|---|---|---|
| FR-01 (palavra/endereço 32 bits) | — (transversal) | `src/cpu_pkg.vhd` | coberto via FR-06/FR-07 | — |
| FR-02 (banco de 32 registradores) | register_file | `src/register_file.vhd` | 6/6 | 8 889 → 8 889 |
| FR-03 (37 instruções RV32I) | alu, branch_unit, control_unit, immediate_generator | 4 arquivos | 18/18 | — |
| FR-04 (extensão M) | control_unit, mul_div_unit | `src/mul_div_unit.vhd` | 8/8 | 0 → 209 379 |
| FR-05 (monociclo, CPI 1) | control_unit, program_counter, register_file | 3 arquivos | 13/13 | — |
| FR-06 (mapa de memória Harvard) | data_ram, instruction_rom, load_store_unit | 3 arquivos | 17/17 | — |
| FR-07 (larguras, fora de faixa) | data_ram, instruction_rom, load_store_unit | 3 arquivos | 17/17 | — |
| FR-08 (PC-relativo, jal/jalr) | branch_unit, immediate_generator | 2 arquivos | 10/10 | 1 554 → 1 554 |
| FR-09 (reset síncrono) | program_counter | `src/program_counter.vhd` | 3/3 | 64 → 64 |
| FR-10 (interface de verificação) | data_ram (+ top-level) | `src/cpu.vhd` | 5/5 | 154 → 154 |
| FR-11 (bordas da extensão M) | mul_div_unit | `src/mul_div_unit.vhd` | 4/4 | 0 → 209 379 |
| FR-12 (barrel shifter, shamt 5 bits) | alu | `src/alu.vhd` | 4/4 | 2 291 → 2 291 |
| FR-13 (carga da ROM) | instruction_rom | `src/instruction_rom.vhd` | 5/5 | 247 → 247 |
| FR-14 (fora de escopo vira nop) | control_unit | `src/control_unit.vhd` | 4/4 | 1 311 → 1 425 |
| FR-15 (`RV32M_ENABLE`) | control_unit, cpu | `src/control_unit.vhd`, `src/cpu.vhd` | 4/4 | — |
| FR-16 (manifesto `cpu.toml`) | — | [`cpu.toml`](cpu.toml) | as 35 execuções do validador | — |
| NFR-01 (área) | — | — | — | ver "Fase 5 — área" |
| NFR-02 (velocidade) | — | — | — | ver "O que não foi medido" |
| NFR-03 (potência) | — | — | — | **não medido** |
| NFR-04 (verificabilidade) | — | — | 48/48 bloco + 35/35 conformidade | — |

⚠ A última coluna está em **células genéricas do Yosys**, não em LUT4 nem em
área física; ver "Por que a contagem de células genéricas engana". Para área,
use a tabela de LUT4.

FR-01 e FR-16 não têm suíte de bloco própria, de propósito: FR-01 é uma
propriedade transversal, exercitada por toda leitura e escrita de memória das
suítes de FR-06/FR-07; FR-16 é o próprio manifesto, e sua evidência é o
validador ter conseguido dirigir a CPU nas 35 execuções.

## Fase 4b — conformidade

O juiz é [`rvverify`](../../rvverify/), o mesmo que julga as CPUs de referência
de [`cpus/`](../../cpus/). Os valores esperados vêm do modelo de referência
executável [`rvverify/reference.py`](../../rvverify/reference.py), **não** de
tabela escrita à mão, e os programas são montados por
[`rvverify/asm.py`](../../rvverify/asm.py).

```
opus_5_RISCVIM   APROVADO
  RV32I (baseline)      24/24  ok
  RV32IM (extensao)     11/11  ok
  Requisitos: 6/6 atendidos
  Medido: 6809 ciclos em 35 programas, CPI nao observavel neste manifesto,
          532 instrucoes RV32M
```

**O baseline veio antes** (princípio 9): a etapa RV32I roda com
`RV32M_ENABLE = false`, e o relatório confirma **0 instruções RV32M nos 24
casos** dessa etapa — o gate funcionou e a base foi verificada sem a extensão.
Na etapa RV32IM os 11 casos contabilizam 532 instruções M reais.

### A aprovação não é vazia

Uma suíte que aprova tudo não prova nada. Para verificar que esta aprovação tem
conteúdo, o SRA da ALU foi trocado por deslocamento **lógico** numa cópia
descartável e a suíte foi re-executada:

```
opus_5_RISCVIM   REPROVADO
  X FR-RV-04  (0/2 casos)  -> sra, srai
  RAM[0x00fc804c] sra(0xffffffff, 0x00000001): esperado 0xffffffff (-1),
                                               obtido 0x7fffffff (2147483647)
  sugestao: Os 64 resultados de SRA coincidem com SRL. [...] confira esse bit
            no decodificador e o deslocamento com sinal.
```

A mutação foi detectada, localizada e diagnosticada corretamente. A cópia
mutante foi descartada; o RTL de `src/` não a contém.

## Fase 5 — área

Método: ADR-005 — `ghdl synth --out=verilog` alimentando o Yosys, porque o
`ghdl-yosys-plugin` não está instalado. Logs brutos em [`ppa/`](ppa/). O design
**não** é achatado, para que a área possa ser atribuída bloco a bloco.

### Células genéricas (comparação entre as duas configurações)

| | RV32I | RV32IM | Δ |
|---|---|---|---|
| células genéricas (design todo) | 16 835 | 226 328 | **+209 493 (13,4×)** |
| `mul_div_unit` | 0 (não instanciada) | 209 379 | +209 379 |
| flip-flops | 1 121 | 1 121 | 0 |
| profundidade lógica no topo | 454 níveis | 573 níveis | +119 |

A `mul_div_unit` responde por **92,5 % das células genéricas** da CPU RV32IM
(em LUT4 são 75 %, ver adiante). O divisor combinacional de um ciclo é a causa: ele é o preço explicitamente aceito em
NFR-02 (`architecture.json`, `alternatives`), e a medição mostra que o preço é
de uma ordem de grandeza, não marginal.

Os 1 121 flip-flops conferem exatamente com o esperado do design — 1 024
(banco de registradores 32×32) + 32 (PC) + 65 (`dbg_pc`, `dbg_instr`,
`dbg_valid`) — e serem **idênticos** nas duas configurações confirma que a
extensão M deste design é puramente combinacional.

### LUT4 (a medição que responde NFR-01)

NFR-01 declara orçamento em "células/LUTs", e célula genérica do Yosys **não é**
LUT. Por isso a área também foi mapeada de verdade para LUT4 (`abc -lut 4`),
com ROM e RAM mantidas como macro `$mem_v2` — que num FPGA é block RAM e não
consome LUT.

| bloco | LUT4 RV32I | LUT4 RV32IM | Δ |
|---|---|---|---|
| `mul_div_unit` | 0 (não instanciada) | **9 489** | +9 489 |
| register_file | 1 785 | 1 785 | 0 |
| alu | 610 | 610 | 0 |
| load_store_unit | 225 | 225 | 0 |
| cpu (topo) | 202 | 229 | +27 |
| data_ram (lógica de acesso) | 84 | 84 | 0 |
| instruction_rom (lógica de acesso) | 66 | 66 | 0 |
| branch_unit | 64 | 63 | −1 |
| control_unit | 62 | 66 | +4 |
| immediate_generator | 40 | 40 | 0 |
| **total** | **3 138** | **12 657** | **+9 519 (4,03×)** |

Em ambas as configurações: 1 089 flip-flops (992 + 96 + 1) e 6 macros de
memória `$mem_v2`.

| | LUT4 | orçamento NFR-01 | veredito |
|---|---|---|---|
| RV32I | 3 138 | 10 000 | **atende** (31 % do orçamento) |
| RV32IM | 12 657 | 10 000 | **não atende** (127 %; excede em 2 657 LUT4) |

### Por que a contagem de células genéricas engana

Este é o resultado mais útil da fase 5, e ele **contradiz** a leitura ingênua
da tabela anterior. Em células genéricas a extensão M custa 13,4×; mapeada
para LUT4 de verdade, custa **4,03×**. A `mul_div_unit` cai de 209 379 células
genéricas para 9 489 LUT4 — um fator de 22 de compressão, porque o `abc`
empacota lógica de 2 entradas em LUTs de 4 entradas e o divisor combinacional
é justamente lógica muito regular.

Ou seja: concluir "a extensão M estoura o orçamento em 22×" a partir do
`stat` de células genéricas seria **errado por uma ordem de grandeza**. O
excesso real é de 27 %. É a diferença entre uma métrica medida na unidade
certa e uma proporção extrapolada de outra unidade — exatamente o que o
princípio 10 existe para evitar.

## Achados

### 1. NFR-01 não é atendido com a extensão M ligada — por 27 %

Medido em LUT4: 12 657 contra um orçamento de 10 000. O excesso é de 2 657
LUT4, e **75 % de toda a CPU RV32IM é a `mul_div_unit`** (9 489 LUT4).

**Isto aponta para a spec, não para o código** (princípio 5): o RTL faz
exatamente o que FR-04, FR-05 e FR-11 pedem — as oito instruções M em hardware
dedicado, sem sequenciamento multiciclo, em CPI 1. É a *combinação*
`div_hardware=True` + `cpi_alvo=1.0` + `orcamento_area=10000` da rubrica que é
internamente inconsistente. Um divisor sequencial de 32 ciclos caberia
folgadamente, mas quebraria `cpi_alvo=1.0`.

Como o excesso é de 27 % e não de uma ordem de grandeza, há saída de
engenharia sem mexer na microarquitetura — o banco de registradores custa
1 785 LUT4 por ser dual-port assíncrono e poderia ir para block RAM num FPGA
que o suporte. Isso é uma hipótese de otimização, **não** uma medição: só
valeria depois de rodar a síntese do FPGA alvo.

### 2. 171 latches em blocos especificados como combinacionais

O Yosys infere `$_DLATCH_` onde o design declara lógica puramente
combinacional: 112 em `load_store_unit`, 58 em `control_unit`, 1 em
`branch_unit` (contagem RV32IM; 167 na RV32I). As CPUs de referência de
`cpus/`, no mesmo fluxo, têm **zero**.

A causa foi isolada por experimento, não por leitura. `branch_unit` tem um
único sinal de 1 bit (`condition`) atribuído dentro de um `case` **completo**,
com `when others` — e produz exatamente 1 latch. Reescrevendo a mesma função
como atribuição condicional concorrente, numa cópia descartável:

| | células | latches |
|---|---|---|
| `branch_unit` como processo | 1 554 | 1 |
| `branch_unit` como atribuição concorrente | 1 459 | **0** |

Ou seja: neste fluxo (`ghdl synth` → `yosys proc`), lógica combinacional
escrita como **processo** vira latch mesmo com cobertura completa de `case`;
escrita como atribuição concorrente, não. É por isso que as CPUs de referência
não têm nenhum.

**Impacto:** nenhum sobre os resultados acima — em simulação os blocos são
combinacionais e as 83 execuções passam. Mas um latch num decodificador é um
defeito real de qualidade de síntese (timing e testabilidade) e deve ser
resolvido antes de qualquer alvo FPGA/ASIC. Não foi corrigido aqui porque
mudaria três blocos que a spec não pediu para mudar; fica registrado como
pendência.

### 3. A profundidade lógica desmente a meta de 50 MHz

573 níveis de lógica no caminho topológico mais longo com M ligado (785 dentro
da `mul_div_unit` isolada), contra 454 sem. **Isto não é medição de tempo** —
ver abaixo. Note que, ao contrário da área, aqui a extensão M não é
compressível: profundidade lógica é latência, e empacotar em LUT4 reduz níveis
mas não muda a ordem de grandeza. Mas é incompatível com uma expectativa de 50 MHz num caminho único:
NFR-02 precisa ou de divisor multiciclo, ou de outra meta de clock.

## O que não foi medido

Declarado explicitamente, em vez de estimado com aparência de medição
(constituição, princípio 10; `repo:NFR-RV-02`).

| item | por quê |
|---|---|
| **Frequência máxima / caminho crítico em ns** | nenhuma ferramenta desta imagem faz análise temporal com biblioteca de células. `ltp` dá **níveis de lógica**, não nanossegundos. NFR-02 fica sem evidência numérica. |
| **Potência** | não há ferramenta de estimativa de potência na imagem. NFR-03 fica sem evidência. |
| **CPI** | o manifesto não declara `stall`/`flush_d`/`flush_f` — um monociclo não os tem. CPI = 1 é **consequência de FR-05 por construção**, não número medido, e sai como `null` no relatório do validador de propósito. |
| **Área em µm² de um PDK** | fora do alcance de `yosys stat`; a contagem serve para comparar as duas configurações entre si. |

## Reconciliação de contrato

Esta CPU foi gerada contra um contrato (fases 3b/4b, `FR-16`–`FR-29`) que
existia no branch `Implementing-.asm-and-.rm-tests` e **nunca** foi integrado a
`main`; `main` resolveu o mesmo problema com o validador `rvverify`. A
reconciliação, item por item, está em [`specs/spec.md`](specs/spec.md), seção
"Reconciliação com a spec vigente do repositório". Em resumo, custou duas
mudanças de RTL, ambas por **parametrização** e nenhuma por deleção
(princípio 8):

- `ROM_INIT_FILE` (FR-13) — o programa entra por `.ram` na elaboração; com
  `""`, o comportamento original (pacote `rom_image_pkg.vhd` gerado) é
  preservado, e é ele que a fase 5 sintetiza;
- `RV32M_ENABLE` (FR-15) — a mesma base de código serve de baseline RV32I e de
  RV32IM, que é o que dá sentido à comparação de área acima (princípio 9).

Os artefatos da fase 3b antiga estão preservados e documentados em
[`software/README.md`](software/README.md).

## Pendências

1. **Latches** (achado 2) — reescrever `load_store_unit`, `control_unit` e
   `branch_unit` como atribuições concorrentes. O caminho já está validado por
   experimento; exige re-rodar as 10 suítes de bloco e a conformidade.
2. **Rubrica inconsistente** (achado 1) — `orcamento_area=10000` com
   `div_hardware=True` e `cpi_alvo=1.0` fecha com 12 657 LUT4, 27 % acima.
   Decisão de spec: aumentar o orçamento, aceitar divisor multiciclo (perde
   CPI 1), ou mapear o banco de registradores para block RAM e re-medir.
3. **Timing e potência** — exigem ferramenta que a imagem não tem.
4. **SPEC-GAP-01 e SPEC-GAP-02** — lacunas do schema da rubrica, registradas na
   fase 1 e ainda abertas; ver [`specs/spec.md`](specs/spec.md).
