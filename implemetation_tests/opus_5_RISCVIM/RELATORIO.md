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
| Área (Yosys, LUT4 de lógica) | RV32I **3 138** · RV32IM **12 657** — ver a ressalva da fase 5b | [`ppa/ppa.json`](ppa/ppa.json) |
| **Cabe no FPGA alvo (`5CEBA4F23C7`)?** | **NÃO** — RV32I 23 693 ALM (128 %), RV32IM 23 786 ALM (129 %) | [`fpga/quartus_output_rv32i/`](fpga/quartus_output_rv32i/), [`rv32im/`](fpga/quartus_output_rv32im/) |
| **Frequência máxima** (TimeQuest, `.sdc` de 50 MHz) | RV32I **36,73 MHz** · RV32IM **10,01 MHz** — NFR-02 **não atendido** nas duas | [`fpga/quartus_output_rv32i_a9r/reports/timing.json`](fpga/quartus_output_rv32i_a9r/reports/timing.json), [`rv32im_a9r/`](fpga/quartus_output_rv32im_a9r/reports/timing.json) |
| **Potência total** (Power Analyzer, **estimativa**) | RV32I **3 462,4 mW** · RV32IM **3 722,2 mW** — NFR-03 **não atendido**, ~7× o orçamento de 500 mW | [`fpga/quartus_output_rv32i_a9r/reports/power.json`](fpga/quartus_output_rv32i_a9r/reports/power.json), [`rv32im_a9r/`](fpga/quartus_output_rv32im_a9r/reports/power.json) |

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

A **fase 5b** (FPGA real: fit, timing e potencia) usa a OUTRA imagem, a do
Quartus (`docker/Quartus_Dockerfile`, ADR-015) -- permanentemente separada da
de cima, nunca a mesma (`repo:NFR-RV-06`):

```bash
docker build -t quartus-lite:25.1 -f docker/Quartus_Dockerfile docker   # uma vez

# uma revisao por vez: rv32i, rv32im, rv32i_a9, rv32im_a9, rv32i_a9r, rv32im_a9r
docker run --rm -v "${PWD}/implemetation_tests/opus_5_RISCVIM:/workspace" \
  quartus-lite:25.1 analyze --project rv32im_sc --revision rv32im_a9 \
  --workdir /workspace/fpga --output /workspace/fpga/quartus_output_rv32im_a9

# o caminho critico que explica o Fmax (roda sobre uma revisao ja compilada)
docker run --rm -v "${PWD}/implemetation_tests/opus_5_RISCVIM:/workspace" \
  -w /workspace/fpga --entrypoint quartus_sta quartus-lite:25.1 \
  -t report_critical_path.tcl -rev rv32im_a9
```

Detalhe das revisoes e do que cada uma responde em [`fpga/README.md`](fpga/README.md).

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
| NFR-01 (área) | — | — | Quartus Fitter: **não cabe** (128 % do device) | ver "Fase 5b" |
| NFR-02 (velocidade) | — | — | TimeQuest: **36,73 MHz** (RV32I) / **10,01 MHz** (RV32IM) contra alvo de 50 MHz | ver "Fase 5b" |
| NFR-03 (potência) | — | — | Power Analyzer: **3 462 / 3 722 mW** (estimativa) contra 500 mW | ver "Fase 5b" |
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

> **E a lição vale outra vez, contra esta própria seção.** A fase 5b mediu a
> mesma coisa no device real: a extensão M custa **1,004×**, não 4,03×. O
> LUT4 do Yosys também é uma unidade aproximada — não conhece DSP, não conhece
> block RAM, não conhece o empacotamento em ALM. Cada degrau na direção do
> silício real encolheu o custo da extensão M em cerca de uma ordem de
> grandeza: 13,4× → 4,03× → 1,004×.

## Fase 5b — FPGA real (Quartus): área, tempo e potência no device

Método: Quartus Prime Lite 25.1std.0 na imagem
[`docker/Quartus_Dockerfile`](../../docker/Quartus_Dockerfile) (ADR-015),
dirigido pelo wrapper `analyze` (`repo:FR-RV-41`). Projeto, revisões e
evidência em [`fpga/`](fpga/). Esta fase **não** substitui a fase 5: ela mede
outras grandezas, e onde as duas se tocam a do Quartus é a que vale, porque é
a que conhece o dispositivo.

Esta análise é **aditiva** — roda depois da conformidade e não altera o
veredito dela (`repo:NFR-RV-06`). A CPU continua **APROVADA** em
comportamento; o que reprova aqui é a *viabilidade física*.

### O alvo default: não cabe

`5CEBA4F23C7`, o device alvo do projeto (`repo:FR-RV-37`, ADR-016):

| | RV32I | RV32IM | Δ |
|---|---|---|---|
| ALM necessárias | **23 693** / 18 480 (**128 %**) | **23 786** / 18 480 (**129 %**) | +93 (+0,4 %) |
| LAB necessárias | 2 424 / 1 848 (131 %) | 2 448 / 1 848 (132 %) | +24 (+1,0 %) |
| registradores | 33 857 | 33 857 | 0 |
| blocos DSP | 0 / 66 | **9** / 66 | +9 |
| bits de block memory | **0** / 3 153 920 | **0** / 3 153 920 | 0 |

As duas configurações reprovam por área, e o Fitter para aí:

```
Error (170012): Fitter requires 2424 LABs to implement the design,
                but the device contains only 1848 LABs
Error (11802): Can't fit design in device.
```

Sem fit não há timing nem potência, e o wrapper **não prossegue** — grava
`compilation.success: false` com `fit`, `timing` e `power` em `null`
(`repo:FR-RV-41`). Nenhum número foi inventado para preencher a lacuna.

### A extensão M quase não pesa num FPGA — a fase 5 errou o fator

Este é o achado que só a ferramenta certa podia dar. Entre RV32I e RV32IM, no
mesmo device:

| métrica | fonte | custo da extensão M |
|---|---|---|
| células genéricas | Yosys (fase 5) | **13,4×** |
| LUT4 | Yosys `abc -lut 4` (fase 5) | **4,03×** (+9 519) |
| ALM no alvo default | Quartus Fitter (fase 5b) | **1,004×** (+93 ALM, +9 DSP) |
| **ALM no par A/B casado** | **Quartus Fitter (`_a9r`)** | **0,74×** (−7 802 ALM, +9 DSP) |

No par casado a extensão M deixa o design **menor**: 29 653 ALM sem M contra
21 851 com M. Não é erro de leitura — os 9 blocos DSP absorvem os
multiplicadores e, com eles no lugar, o fitter reestrutura a lógica em volta.
Uma extensão de ISA que *reduz* a área de lógica é contraintuitivo o bastante
para merecer o número ao lado do log que o produziu.

A razão é concreta e está no log: o Quartus reconhece `*`, `/` e `mod` e
instancia megafunções — `lpm_mult` sobre **9 blocos DSP dedicados** e quatro
`lpm_divide` —, em vez de expandir tudo em lógica genérica como o fluxo
`ghdl synth` + Yosys faz. O silício tem multiplicador; o Yosys, sem biblioteca
de device, não tinha como saber disso.

Ou seja, a conclusão da fase 5 — *"NFR-01 não é atendido por causa da extensão
M, que custa 4×"* — **não se sustenta no alvo real**. A extensão M custa entre
+0,4 % e −26 % de lógica, dependendo de como o fitter empacota; em nenhuma
medição ela chega perto de 4×. Quem estoura o device é outra coisa, e ela já
estava lá no baseline RV32I.

### Quem estoura o device: a RAM que precisa ser observável

`Total block memory bits : 0 / 3 153 920 ( 0 % )`. Nenhum bit de M10K é usado.
A `data_ram` de 4 KB virou **32 768 flip-flops** mais um multiplexador
**1024:1 de 25 bits, orçado pelo próprio Quartus em 17 050 LEs**:

```
; 1024:1 ; 25 bits ; 17050 LEs ; ... ; |cpu|data_ram:data_ram_inst|Mux20
```

A causa está no RTL e é **deliberada**: [`src/data_ram.vhd`](src/data_ram.vhd)
declara o armazenamento como `signal` com leitura **assíncrona**, porque é
assim que o cocotb consegue indexá-lo pelo VHPI (FR-10, `repo:FR-RV-26`) e
porque leitura assíncrona é o que permite CPI = 1 (FR-05). Block RAM de FPGA
**não** tem leitura assíncrona: a M10K é síncrona. As duas exigências são
incompatíveis, e o custo dessa incompatibilidade é o device inteiro.

Isto **corrige** a hipótese de otimização registrada no achado 1 da fase 5
("o banco de registradores poderia ir para block RAM"): o alvo certo não é o
banco de registradores (781 ALUT + 992 FF, pequeno), é a `data_ram`. E não é
uma troca livre — mexer nela mexe no contrato de observabilidade que torna a
CPU verificável.

### Timing: 36,73 MHz sem a extensão M, 10,01 MHz com ela

Medido pelo TimeQuest com o `.sdc` de 20 ns de
[`fpga/rv32im_sc.sdc`](fpga/rv32im_sc.sdc) — sem `.sdc` o número não
significaria nada (`repo:FR-RV-38`). Par A/B casado (`rv32i_a9r` × `rv32im_a9r`:
mesmo device, mesmas opções de fitter, só o generic muda):

| | RV32I | RV32IM | alvo NFR-02 |
|---|---|---|---|
| **Fmax** | **36,73 MHz** | **10,01 MHz** | 50 MHz |
| slack de setup (pior corner) | −7,228 ns | −83,204 ns | ≥ 0 |
| slack de hold | +0,171 ns (atende) | +0,172 ns (atende) | ≥ 0 |
| **veredito** | **não atende** (1,4× abaixo) | **não atende** (5,0× abaixo) | |

**Nem o baseline atinge 50 MHz.** Este é o ponto: a fase 5 atribuía o problema
de velocidade à extensão M, e de fato a M custa caro — 3,7× de frequência —,
mas mesmo sem ela o design fica 27 % abaixo do alvo.

Os caminhos críticos, extraídos com
[`fpga/report_critical_path.tcl`](fpga/report_critical_path.tcl), dizem por quê:

```
RV32I   pc_reg[2] -> regs[27][16]        arrival  31,525 ns   slack  -7,228
        pc_inst -> rom_inst -> regfile_inst -> alu_inst -> DATA_RAM_INST -> lsu_inst -> regfile_inst

RV32IM  pc_reg[6] -> regs[15][22]        arrival 104,274 ns   slack -79,937
        pc_inst -> rom_inst -> regfile_inst -> MULDIV_INST (divisor) -> regfile_inst
```

Nos dois casos é o datapath monociclo inteiro num ciclo só. Com M, o divisor
combinacional domina e leva o caminho a ~104 ns. Sem M, o caminho crítico é um
**load**, e quem está nele é a `data_ram` — o mesmo mux assíncrono 1024:1 que
estoura a área. Ou seja, o divisor e a RAM assíncrona são dois problemas
independentes: resolver só o divisor levaria a CPU a ~36 MHz, ainda abaixo do
alvo.

A fase 5 já apontava a direção em níveis de lógica (achado 3); agora está em
nanossegundos, e com o culpado do baseline identificado.

### Potência: ~3,5 W contra um orçamento de 500 mW

| componente | RV32I | RV32IM |
|---|---|---|
| dinâmica de núcleo | 2 863,81 mW | 3 117,44 mW |
| estática de núcleo | 580,17 mW | 586,34 mW |
| E/S | 18,44 mW | 18,44 mW |
| **total** | **3 462,41 mW** | **3 722,23 mW** |

**É estimativa, não medição** (`repo:FR-RV-39`), e o próprio Quartus rotula a
confiança: `Low: user provided insufficient toggle rate data` — não houve
simulação anotada para dar taxa de chaveamento real. Ainda assim, o orçamento
de NFR-03 é 500 mW e a estimativa é **cerca de 7× maior** (6,9× no baseline,
7,4× com M), uma distância grande demais para caber na incerteza da
estimativa. Potência de FPGA de verdade só
existe medindo a placa, o que está fora do escopo.

A causa é a mesma da área: 33 857 flip-flops chaveando por ciclo, mais um
divisor combinacional de 32 bits, mais um mux 1024:1 — nada disso existiria
com RAM em M10K e divisor sequencial. Note que a extensão M responde por só
+7,5 % da potência (+259,8 mW): como na área, o custo está no baseline, não na
extensão.

## Achados

### 1. NFR-01 não é atendido — mas a fase 5b mostrou que o culpado é outro

> **Revisado pela fase 5b.** O diagnóstico abaixo (a extensão M estoura a
> área) vale no fluxo Yosys e **foi derrubado no FPGA de verdade**: lá a
> extensão M custa +0,4 % de ALM, e quem não cabe é a `data_ram` — já no
> baseline RV32I. O parágrafo original fica preservado (princípio 8); leia-o
> junto da seção "Quem estoura o device: a RAM que precisa ser observável".

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

**A síntese do FPGA alvo foi rodada (fase 5b), e a hipótese estava errada nos
dois pontos.** Primeiro, nada foi para block RAM — nem o banco de
registradores nem a RAM: `0 / 3 153 920` bits de M10K usados, porque as duas
têm leitura assíncrona e a M10K é síncrona. Segundo, o alvo da otimização não
é o banco de registradores (781 ALUT + 992 FF) e sim a `data_ram` (32 768 FF
+ mux de 17 050 LEs). Registrar a hipótese como hipótese, e não como
conclusão, foi o que permitiu vê-la ser refutada por medição.

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

**Confirmado em nanossegundos pela fase 5b:** 10,01 MHz com M, slack de setup
−83,204 ns, e o caminho crítico passa de fato pelo divisor. A previsão
qualitativa feita a partir de níveis de lógica estava certa na direção e na
ordem de grandeza — mas note que ela só virou evidência numérica quando uma
ferramenta com biblioteca de device a mediu.

## O que não foi medido

Declarado explicitamente, em vez de estimado com aparência de medição
(constituição, princípio 10; `repo:NFR-RV-02`).

> **Duas linhas desta tabela deixaram de valer** com a fase 5b: frequência
> máxima e potência **foram** obtidas, pelo Quartus. Ficam abaixo riscadas em
> vez de apagadas (princípio 8), porque a razão pela qual faltavam — a imagem
> do GHDL/Yosys não ter a ferramenta — continua verdadeira e é o motivo de
> existir uma segunda imagem.

| item | por quê |
|---|---|
| ~~**Frequência máxima / caminho crítico em ns**~~ — **medido na fase 5b: 36,73 / 10,01 MHz** | nenhuma ferramenta *daquela* imagem faz análise temporal com biblioteca de células. `ltp` dá **níveis de lógica**, não nanossegundos. Resolvido pelo TimeQuest do Quartus (`repo:FR-RV-38`). |
| ~~**Potência**~~ — **estimada na fase 5b: 3 462,4 / 3 722,2 mW** | não há estimador de potência *naquela* imagem. Resolvido pelo Power Analyzer do Quartus, e continua sendo **estimativa** rotulada, nunca medição (`repo:FR-RV-39`). |
| **Potência medida em placa física** | exigiria a placa e instrumentação; fora do escopo. O número da fase 5b é estimativa de ferramenta, com confiança rotulada `Low` pelo próprio Quartus por falta de toggle rate de simulação anotada. |
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
2. **A `data_ram` não cabe em FPGA nenhum desta família** (fase 5b) — é a
   pendência mais grave, e é de **spec**, não de código. O contrato de
   observabilidade (FR-10, `repo:FR-RV-26`: RAM como `signal` indexável pelo
   cocotb) mais CPI = 1 (FR-05, que pede leitura no mesmo ciclo) forçam
   leitura **assíncrona**, e leitura assíncrona não vira M10K. Resultado:
   32 768 flip-flops e um mux 1024:1 de 17 050 LEs, 128 % do device já no
   baseline RV32I. Não há ajuste de RTL que resolva sem tocar num dos dois
   requisitos. As saídas possíveis, todas decisões de spec:
   - RAM síncrona (vira M10K, cabe) + CPI 2 para load — **quebra FR-05**;
   - manter a RAM como está e abandonar o alvo FPGA — **quebra NFR-01**;
   - observar a RAM por outro mecanismo que não exija leitura assíncrona
     (porta de debug dedicada, dump por VHPI ao fim da simulação) — **muda o
     contrato de verificação de `repo:FR-RV-26`**, e afeta todas as CPUs
     julgadas pelo validador, não só esta.
3. **Rubrica inconsistente** (achado 1, revisado pela fase 5b) —
   `orcamento_area=10000` com `div_hardware=True` e `cpi_alvo=1.0` é de fato
   inconsistente, mas **não pelo motivo que a fase 5 apontou**: a extensão M
   custa +0,4 % de ALM no device real (os DSPs fazem o trabalho). O conflito
   real da rubrica é `cpi_alvo=1.0` + `alvo_fpga=True`, que juntos pedem
   memória de leitura assíncrona num silício cuja memória é síncrona.
4. **NFR-02 e NFR-03 reprovados por medição** (fase 5b) — 10,01 MHz com M e
   **36,73 MHz mesmo sem M**, contra 50 MHz; 3 722 / 3 462 mW contra 500 mW.
   Note que um divisor multiciclo resolveria o caminho crítico *com* M, mas
   pararia em ~36 MHz por causa do caminho de load pela `data_ram` — ou seja,
   NFR-02 depende da pendência 2 também. Decisão de spec: rever as metas ou
   rever a microarquitetura nos dois pontos.
5. **Potência sem toggle rate** — as estimativas de ~3,5 W têm confiança
   `Low` declarada pelo Quartus. Anotar a atividade real de uma simulação
   (`.vcd` das suítes cocotb → Power Analyzer) daria um número de confiança
   maior. É trabalho adicional, não correção de erro.
6. **SPEC-GAP-01 e SPEC-GAP-02** — lacunas do schema da rubrica, registradas na
   fase 1 e ainda abertas; ver [`specs/spec.md`](specs/spec.md).
