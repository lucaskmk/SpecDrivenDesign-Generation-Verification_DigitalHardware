# Relatório — CPU RISC-V: de RV32I para RV32IM

Trilha B do projeto SpecHDL. Parte de uma CPU RV32I que já existia, estabelece
uma baseline verificada, estende para RV32IM e mede o que a extensão custou e
o que ela devolveu.

**Regra que governa este relatório:** nenhum número aqui é estimativa, exceto
onde está escrito **ESTIMATIVA**. Cada valor veio de uma execução real de
ferramenta cujo comando está na seção 9.

---

## 1. Diagnóstico inicial

A auditoria completa está em [`specs/decisions.md`](../../specs/decisions.md),
ADR-000. O essencial:

| Pergunta | Resposta (verificada por execução) |
|---|---|
| Onde está a CPU? | `examples/RISCV32I/src/CPU.vhd` |
| Está implementada ou prevista? | **Implementada e funcional.** `simple_RISCV_RV32I_vhdl`, de Morgan Demange, vendorizada no commit `f884a4e` |
| ROM e RAM existem? | Sim: `instruction_memory.vhd`, `data_rom.vhd`, `data_ram.vhd` |
| Entidades e portas | `entity CPU` tem **apenas** `rst` e `clk`. Nenhuma saída observável |
| Clock e reset | um domínio `clk`; `rst` **ativo em nível alto**, assíncrono. O banco de registradores escreve na **borda de descida** (decisão original para reduzir hazards) |
| Latência da ROM | **zero.** `instruction_memory` é combinacional, sem porta de clock |
| Latência da RAM | leitura **zero** (assíncrona); escrita síncrona em `rising_edge(clk)` |
| Acesso a instruções | `pc_f` → `instruction_memory.addr`; instrução disponível no mesmo ciclo |
| Acesso a dados | `alu_result_m` → `data_memory`, que roteia RAM ou ROM por comparação de endereço |
| Mapa de memória | instruções em `0x00000000`+; DATA_ROM em `0x00FC8000` (8 B); DATA_RAM em `0x00FC8100` (512 B) |
| Subconjunto RV32I | **base completo**, exceto `FENCE`, `ECALL` e `EBREAK`, que o decoder marca como inválidas. Sem CSR, sem interrupções |
| Há pipeline? | Sim: **5 estágios** (fetch, decode, execute, memory, write-back), Harvard |
| Hazards | forwarding MEM→EX e WB→EX; stall de 1 ciclo em load-use; flush em salto tomado; preditor **always-not-taken** |
| Arquivos de simulação | `CPU_tb.vhd` existia mas **nunca rodou**: literais `5ns`, `12ns`, `1ms` sem espaço, ilegais em VHDL, falham até com `-frelaxed` |
| Ferramentas instaladas | GHDL 4.1.0 (mcode), Yosys 0.33, cocotb 2.1.0, GTKWave, make — na WSL Ubuntu 24.04 |
| Compilador RISC-V | **ausente.** Nem no Windows nem na WSL |
| `ghdl-yosys-plugin` | **ausente** |
| Fluxo cocotb + GHDL existente | **não existia** para esta CPU. Só havia o smoke test genérico de `examples/toolchain_smoketest/` |

**Os três problemas reais** não estavam na CPU, que funciona:

1. **Observabilidade.** As memórias usavam array 2-D (`array (0 to N, 3 downto 0) of std_logic_vector(7 downto 0)`), e o VPI do GHDL **não expõe arrays 2-D**. O cocotb não conseguia ler nenhum resultado da RAM.
2. **Carga de programa.** O programa era uma **constante VHDL**. Trocar de programa exigia rodar um Makefile, converter binário para texto e **copiar e colar** dentro de `memory_package.vhd`. E o cocotb **não consegue escrever na ROM**: `dut.instruction_memory.memory[0].value = ...` é silenciosamente ignorado pelo VPI do GHDL.
3. **Sem toolchain de software.** Sem compilador RISC-V, não havia como produzir programas de teste.

---

## 2. Arquivos encontrados

**RTL herdado** (19 arquivos, `examples/RISCV32I/src/`): `CPU.vhd`,
`cpu_package.vhd`, `memory_package.vhd`, `ALU.vhd`, `branching_unit.vhd`,
`control_unit.vhd`, `instruction_decoder.vhd`, `extend_32.vhd`,
`program_counter.vhd`, `register_file.vhd`, `instruction_memory.vhd`,
`data_memory.vhd`, `data_ram.vhd`, `data_rom.vhd`,
`fetch_pipeline_register.vhd`, `decode_pipeline_register.vhd`,
`execute_pipeline_register.vhd`, `mem_pipeline_register.vhd`,
`hazard_control_unit.vhd`.

**Outros:** `CPU_tb.vhd` (quebrado, nunca rodou), `compilation/` (Makefile
apontando para um toolchain xPack que não está no repositório, `main.c`,
`startup.S`, `linker.ld`, `convert_bin_to_txt.py`), `README.md` do autor
original.

---

## 3. Arquivos alterados e criados

### RTL modificado (9 arquivos, +583 −86 linhas desde `f884a4e`)

| Arquivo | O que mudou | Por quê |
|---|---|---|
| `memory_package.vhd` | tipos de ROM/RAM de 2-D para 1-D; `INSTRUCTION_WORDS_t` irrestrito | observabilidade e ROM dimensionável por generic |
| `data_ram.vhd` | armazenamento 1-D; acessos de byte/halfword por fatia | o VPI do GHDL não expõe arrays 2-D |
| `data_rom.vhd` | idem | idem |
| `instruction_memory.vhd` | generics `ROM_INIT_FILE` e `ROM_SIZE_WORDS`; leitura de imagem `.ram` por `textio` na elaboração | trocar de programa sem editar VHDL |
| `cpu_package.vhd` | 8 valores RV32M no enum `ALU_OP_TYPE_t`; `funct3`/`funct7` da extensão; função `is_rv32m_op` | o seletor da unidade M viaja por um caminho que já existia |
| `control_unit.vhd` | generic `RV32M_ENABLE`; decodifica `funct7 = 0000001` | habilitar RV32M sem tocar na decodificação RV32I |
| `instruction_decoder.vhd` | generic `RV32M_ENABLE`; `funct7 = 0000001` deixa de ser inválido | idem |
| `CPU.vhd` | generics `ROM_INIT_FILE`, `ROM_SIZE_WORDS`, `RV32M_ENABLE`; instancia `mul_div_unit` em `generate`; mux sobre `alu_result_e`; sinal `m_dispatch_e` | integrar a extensão e expor a métrica |
| **`mul_div_unit.vhd`** (novo) | MUL, MULH, MULHSU, MULHU, DIV, DIVU, REM, REMU | a extensão em si |

**Não foi tocado:** os quatro registradores de pipeline, `hazard_control_unit.vhd`,
`ALU.vhd`, `branching_unit.vhd`, `extend_32.vhd`, `program_counter.vhd`,
`register_file.vhd`, `data_memory.vhd`. Nada foi removido.

### Ferramentas e verificação (novos)

| Arquivo | Papel |
|---|---|
| `tools/rv_assembler.py` | montador RV32I/RV32IM (não há compilador RISC-V aqui) |
| `tools/build_programs.py` | `.asm` → imagem `.ram` |
| `tools/synth_ppa.py` | área e profundidade lógica por síntese real |
| `tools/bench_compare.py` | comparação de eficiência RV32I × RV32IM |
| `test/rv_harness.py` | harness cocotb: clock, reset, término, métricas |
| `test/rv_build.py` | monta o programa, gera a `.ram`, dispara o GHDL |
| `test/tb_program.py`, `test/tb_snapshot.py` | módulos cocotb |
| `test/reference_model.py` | modelo de referência RV32I/RV32M em Python |
| `test/rv_m_cases.py` | gerador de varreduras da extensão M |
| `test/test_*.py` | as sete suítes (seção 5) |
| `programs/*.c`, `*.asm`, `*.ram` | quatro benchmarks, duas ISAs cada |

### Documentação

`specs/constitution.md` (Emenda 1), `specs/spec.md` (FR-RV-01..25,
NFR-RV-01..03), `specs/plan.md` (fases RV-0..RV-6), `specs/tasks.md`
(backlog TRV-x.y), `specs/decisions.md` (ADR-000..009), `README.md`,
`programs/README.md`, este relatório.

---

## 4. Decisões de compatibilidade

Todas registradas em [`specs/decisions.md`](../../specs/decisions.md).

**ADR-001 — parametrizar, não duplicar.** As duas ISAs saem da **mesma árvore
de fontes**, escolhidas pelo generic `RV32M_ENABLE`. Duplicar 19 arquivos faria
qualquer correção precisar ser aplicada em dois lugares e as duas cópias
divergiriam; o A/B deixaria de ser honesto.

**ADR-002 — 2-D → 1-D nas memórias.** Alteração em bloco de terceiro, portanto
exigiu prova de comportamento preservado: `test_memory.py` materializa o RTL
**original** a partir do git (`git show f884a4e:...`) e compara o estado da CPU
sob o mesmo testbench. As regras originais de acesso desalinhado
(`0xFFFFFFFF` na leitura, escrita descartada) são testadas explicitamente.

> Armadilha encontrada durante a refatoração: a guarda de faixa e o índice do
> array **têm de ficar na mesma expressão condicional**. Separar a guarda num
> sinal próprio faz ela atrasar um delta em relação a `word_index`, e um
> endereço fora de faixa indexa o array antes de a guarda alcançar. Sintoma:
> `ghdl:error: index (1069604864) out of bounds`. O design original já fazia
> assim; a estrutura foi restaurada.

**ADR-003 — ROM carregável por arquivo, mantendo a constante.** `ROM_INIT_FILE`
vazio (o padrão) usa `INSTRUCTION_MEMORY_CONTENT`, então o comportamento
original e o caminho de síntese ficam preservados. O risco previsto —
`ghdl synth` rejeitar a função com `textio` — **não se materializou**:
`ghdl synth` retorna exit 0 com a função presente.

**ADR-004 — montador próprio em vez de instalar GCC RISC-V.** Não há compilador
RISC-V no ambiente e a instrução era explícita: não instalar ferramentas em
silêncio. Os `.c` continuam versionados como **especificação legível do
algoritmo**, marcados como não compilados aqui. O montador é código do projeto
e por isso é validado por pytest contra os encodings da especificação **antes**
de ser usado para gerar imagem de teste.

**ADR-007 — unidade M combinacional, selecionada pelo enum que já existia.**
Esta é a decisão central. As oito operações M foram **acrescentadas ao enum
`ALU_OP_TYPE_t`**, que já viaja de Decode para Execute pelo
`decode_pipeline_register`. O resultado é multiplexado sobre `alu_result_e`, de
onde os caminhos de forwarding MEM→EX e WB→EX **já partiam**.

Consequência: nenhum registrador de pipeline mudou, a `hazard_control_unit` não
mudou, e como a latência é de 1 ciclo **não existe nova fonte de stall a
tratar**. Forwarding, stall de load-use e flush continuam valendo para
instruções M sem uma linha de código nova — e isso é comprovado por teste
(seção 6, `TestDataHazards` e `TestLatency`).

Alternativa rejeitada: unidade iterativa multiciclo, que é o que um projeto real
faria para não estourar o caminho crítico. Exigiria acrescentar porta `stall` ao
`decode_pipeline_register` e reescrever a precedência stall/flush/carga na
unidade de hazard — mudança estrutural num pipeline de terceiro já verificado.
Registrada como trabalho futuro, com o custo levantado.

**ADR-008 — término detectado no commit, não na busca.** Ver seção 8.

**ADR-009 — como a área é contada.** Ver seção 7.

---

## 5. Testes executados

Todos com **GHDL 4.1.0 dirigido por cocotb 2.1.0**, na WSL Ubuntu 24.04.
Nenhum resultado abaixo foi inferido do código.

| Suíte | Casos | O que cobre |
|---|---:|---|
| `test_toolchain.py` | 620 (+26 skip) | encodings do montador conferidos campo a campo contra a especificação RISC-V; modelo de referência; formato `.ram` |
| `test_memory.py` | 15 | preservação de comportamento das memórias contra o RTL original extraído do git; acessos de byte/halfword/palavra; desalinhado e fora de faixa |
| `test_rv32i_baseline.py` | 28 | **baseline RV32I**: x0, load/store, aritmética, branches, saltos, hazards, laços, reset |
| `test_programs.py` | 40 | os quatro benchmarks nas duas ISAs; imagens `.ram` versionadas conferidas contra o montador |
| `test_rv32m_mul.py` | 26 | MUL, MULH, MULHSU, MULHU |
| `test_rv32m_div.py` | 29 | DIV, DIVU, REM, REMU |
| `test_rv32m_integration.py` | 37 | hazards, escopo, latência, reset, waveform, travamento |
| **total** | **795 passed, 26 skipped** | exit code 0, em 3 min 15 s |

A cobertura de valores segue a lista de casos pedida. Para cada uma das oito
instruções M há uma **varredura completa** do produto cartesiano
`EDGE_VALUES × EDGE_VALUES` (169 pares), com `EDGE_VALUES` =
`{0, 1, −1, 2, −2, 2³¹−1, −2³¹, 0x0000FFFF, 0xFFFF0000, 0x12345678, 0xDEADBEEF,
0x55555555, 0xAAAAAAAA}` — ou seja zero, negativos, e o maior e o menor valor
representável, todos contra todos. **Todo valor esperado vem do modelo de
referência em Python**, nunca de constante escrita à mão.

---

## 6. Resultado de cada teste

```
795 passed, 26 skipped in 194.93s (0:03:14)
PYTEST_EXIT=0
```

**Todas as suítes passam. Exit code 0.**

Os 26 pulados são legítimos e estão todos em `test_toolchain.py`: numa
verificação genérica de identidade do modelo de referência, os casos de divisor
zero são excluídos porque têm regra própria — e essa regra é coberta por testes
dedicados (`TestDivisionByZero`, item 14 abaixo). Nenhum teste de hardware é
pulado.

| Item pedido | Onde | Resultado |
|---|---|---|
| 1. baseline RV32I | `test_rv32i_baseline.py` | 28 passed |
| 2. MUL | `test_rv32m_mul.py::TestMul` | passed (169 pares) |
| 3. MULH | `::TestMulh` | passed (169 pares) |
| 4. MULHSU | `::TestMulhsu` | passed (169 pares) |
| 5. MULHU | `::TestMulhu` | passed (169 pares) |
| 6. DIV | `test_rv32m_div.py::TestDiv` | passed (169 pares) |
| 7. DIVU | `::TestDivu` | passed (169 pares) |
| 8. REM | `::TestRem` | passed (169 pares) |
| 9. REMU | `::TestRemu` | passed (169 pares) |
| 10. programa misto RV32I + RV32M | `test_rv32m_integration.py::TestMixedProgram` | passed — laço com load/store, branch, MUL, DIV e REM; 12 instruções M contadas |
| 11. valores zero | varreduras + `TestX0` | passed |
| 12. valores negativos | varreduras + `TestRoundingAndSign` | passed |
| 13. maior e menor representável | varreduras + `TestExtremes` | passed |
| 14. divisão por zero | `TestDivisionByZero` | passed — DIV→−1, DIVU→2³²−1, REM/REMU→dividendo, **sem trap, sem travar** |
| 15. overflow da divisão | `TestSignedOverflow` | passed — (−2³¹)/(−1)→−2³¹, (−2³¹)%(−1)→0 |
| 16. dependências entre instruções | `TestDataHazards` | passed — forwarding MEM→EX, WB→EX, cadeia M→M, resultado M como endereço, load-use com consumidor M (`stalls > 0` observado) |
| 17. hazards de pipeline | `TestControlHazards` | passed — branch dependendo de resultado M (`flushes > 0`); bolha de flush **não** conta como instrução M |

**Testes que provam que a verificação não é vazia** (`TestObservability`):

- programa travado (laço infinito que não é o auto-laço) → `CpuTimeout` → exit code ≠ 0;
- resultado deliberadamente errado → reprovação → exit code ≠ 0;
- waveform gerado, existe em disco e não está vazio.

**Guardas de escopo** (`TestScopeGuards`): as oito instruções M são **rejeitadas
na montagem** quando `allow_m=False`, que é a configuração da baseline — não há
como um teste RV32I passar usando a extensão por acidente. Mnemônico inventado,
instrução de outra ISA, `ecall`, `ebreak` e `fence` também são rejeitados
(FR-RV-03).

---

## 7. Comparação de eficiência: RV32I contra RV32IM

### 7.1 Simulação — medição real

Quatro benchmarks, **o mesmo algoritmo nas duas ISAs**. Antes de comparar
qualquer número, `bench_compare.py` confere que as duas versões escreveram os
**mesmos valores nos mesmos endereços de RAM** — e recusa-se a reportar se
divergirem. Nesta execução, `all_results_match = true`.

| benchmark | ciclos RV32I | ciclos RV32IM | Δ | instr. RV32I | instr. RV32IM | CPI RV32I | CPI RV32IM | instr. M |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `bench_div` | 3.125 | 52 | **−98,3 %** | 2.397 | 50 | 1,30 | 1,04 | 16 |
| `bench_dotprod` | 1.013 | 153 | −84,9 % | 717 | 133 | 1,41 | 1,15 | 8 |
| `bench_mul` | 1.037 | 39 | −96,2 % | 707 | 37 | 1,47 | 1,05 | 8 |
| `bench_signs` | 1.286 | 33 | −97,4 % | 930 | 31 | 1,38 | 1,06 | 5 |
| **TOTAL** | **6.461** | **277** | **−95,7 %** | **4.751** | **251** | — | — | **37** |

**Stalls e flushes** (o mecanismo por trás do ganho):

| benchmark | stalls I → IM | flushes I → IM |
|---|---|---|
| `bench_div` | 0 → 0 | **728 → 2** |
| `bench_dotprod` | 0 → 0 | 296 → 20 |
| `bench_mul` | 0 → 0 | 330 → 2 |
| `bench_signs` | 0 → 0 | 356 → 2 |

O ganho **não** vem de a instrução M ser mais rápida — ela custa exatamente um
ciclo, igual a um `add`, e isso é verificado diretamente por
`TestLatency::test_m_costs_the_same_cycles_as_an_add`. O ganho vem de
**eliminar os laços de emulação**: um `mul` substitui 32 iterações de
deslocamento-e-soma, e cada iteração pagava flushes de branch numa CPU
always-not-taken. É por isso que os flushes caem de 728 para 2 em `bench_div`.

**Tempo estimado de execução — ESTIMATIVA.** A 10 ns por ciclo (período nominal
do `CPU_tb.vhd` original), o total seria 64,6 µs em RV32I contra 2,77 µs em
RV32IM. **Isto é estimativa, não medição:** o período de clock realmente
atingível não foi medido, e a seção 7.2 dá uma razão forte para suspeitar que
ele piora bastante em RV32IM.

**Stalls introduzidos pela extensão M: zero.** A unidade é combinacional
(ADR-007), então não há stall de multiciclo a contar. `m_stall_cycles = 0` não
é uma medição ausente: é a consequência direta e verificada da decisão de
projeto.

### 7.2 Síntese — medição real

Fluxo (ADR-009): `ghdl synth --out=verilog` alimentando o Yosys, hierarquia
preservada e `techmap` aplicado. A mesma árvore de fontes, mudando só o generic.

| métrica | RV32I | RV32IM | Δ |
|---|---:|---:|---:|
| células de **lógica do núcleo** (sem memórias) | 6.239 | 56.327 | **+50.088 (9,03×)** |
| células **totais** (com memórias) | 100.284 | 150.372 | +50.088 (1,50×) |
| só a `mul_div_unit` | — | 49.824 | — |
| profundidade lógica da ALU (níveis) | 36 | 36 | 0 |
| profundidade lógica da `mul_div_unit` (níveis) | — | **631** | **17,5× a ALU** |

Composição da `mul_div_unit`: 23.511 `$_AND_`, 13.819 `$_XOR_`, 8.617 `$_OR_`,
2.539 `$_NOT_`, 1.338 `$_MUX_`.

Por bloco, o resto do processador é **idêntico** nas duas configurações; só
`control_unit` (+243) e `instruction_decoder` (+21) crescem, e por causa da
decodificação nova.

**Caminho crítico.** `ltp -noff` dá o caminho topológico mais longo em **níveis
de lógica** — medição estrutural real do Yosys, **não** atraso em nanossegundos.
Converter níveis em tempo exigiria biblioteca de células caracterizada, que não
existe aqui, e por isso nenhum valor em ns é afirmado.

### 7.3 A leitura

A extensão M troca **95,7 % dos ciclos** por **9× mais lógica de núcleo** e um
bloco combinacional **17,5× mais profundo** que a ALU. Numa síntese com
restrição de tempo real, esse divisor restaurador de 32 estágios ditaria o
período de clock do processador inteiro — o ganho de 23× em ciclos seria
parcialmente devolvido em frequência.

É exatamente esse o argumento a favor de uma unidade **iterativa multiciclo**:
ela custaria alguns ciclos por divisão, mas manteria o caminho crítico perto do
da ALU. Esta primeira versão escolheu deliberadamente o caminho mais simples, e
o número acima é a justificativa quantitativa para revisitá-lo.

---

## 8. Limitações e pendências

1. **A unidade M é combinacional.** Correta e verificada, mas com caminho
   crítico de 631 níveis. A variante multiciclo está registrada como trabalho
   futuro no ADR-007, com o custo já levantado: porta `stall` no
   `decode_pipeline_register` e reescrita da precedência na
   `hazard_control_unit`.

2. **Os `.c` não foram compilados.** Não há compilador RISC-V no ambiente, e
   instalar um em silêncio estava fora do escopo. Os `.c` são especificação
   legível; o que executa são os `.asm` traduzidos à mão e versionados. Se
   `gcc-riscv64-unknown-elf` for instalado depois, o fluxo `.c` real passa a ser
   possível como caminho alternativo.

3. **Caminho crítico não é dado em nanossegundos.** Só em níveis de lógica,
   porque não há biblioteca de células caracterizada. Declarar ns seria chute.

4. **`ghdl-yosys-plugin` continua ausente.** Contornado pelo backend de síntese
   do próprio GHDL (ADR-005), que retorna exit 0 e produz contagem real.

5. **As 6.937 células do ADR-000 não são comparáveis** com os números da seção
   7.2: foram medidas no RTL original, antes da refatoração de memórias e com a
   receita antiga de `stat` (sem `techmap`). A referência válida é a coluna
   RV32I desta mesma árvore, remedida pelo mesmo script.

6. **`CPU_tb.vhd` continua quebrado.** Não foi consertado porque foi
   substituído pelo fluxo cocotb; permanece no repositório porque nada é
   removido (princípio 8). Consertar os literais de tempo é tarefa aberta.

7. **A comparação de área usa células genéricas do Yosys**, não um PDK nem LUTs
   de um FPGA específico. Serve para comparar as duas configurações no mesmo
   fluxo, que é o que a trilha pede, e não para afirmar área em µm².

8. **Armadilha corrigida no harness, que vale registrar** (ADR-008). A detecção
   de término contava visitas do PC de **busca** ao endereço do auto-laço. Como
   a CPU é always-not-taken e resolve saltos em EX, `pc_f` visita
   especulativamente o endereço de parada **uma vez por iteração de laço** — o
   teste "soma 1..10 = 55" parava na 4ª iteração e obtinha 6, com hardware
   correto. A detecção passou a observar o **commit**
   (`pc_e == halt_pc and jump_e = '1'`), que é imune ao fetch especulativo. A
   fórmula de contagem de instruções também estava errada, descontando duas
   vezes os ciclos de stall de load-use.

9. **O ambiente de execução é a WSL local**, não a imagem Docker
   `rafaelcorsi/pl-descomp-cocotb` citada no plano (o daemon do Docker está
   desligado nesta máquina). A imagem continua sendo o ambiente de referência
   para CI.

---

## 9. Comandos exatos para reproduzir

Ambiente: **WSL Ubuntu 24.04**, GHDL 4.1.0 (mcode), Yosys 0.33, cocotb 2.1.0
num virtualenv de usuário. Os comandos abaixo são os que produziram todos os
números deste relatório.

```bash
# --- ponto de partida -------------------------------------------------
cd /mnt/c/Users/LKKam/Git/7semestre/SpecDrivenDesign-Generation-Verification_DigitalHardware
ghdl --version          # GHDL 4.1.0 (Ubuntu 4.1.0+dfsg-0ubuntu2.1) [Dunoon edition]
yosys -V                # Yosys 0.33 (git sha1 2584903a060)
~/venv-cocotb/bin/python -c "import cocotb; print(cocotb.__version__)"   # 2.1.0

# --- suite completa (o que fecha os criterios de aceitacao) -----------
~/venv-cocotb/bin/python -m pytest examples/RISCV32I/test/ -v

# --- por etapa --------------------------------------------------------
# montador e modelo de referencia (sem hardware)
~/venv-cocotb/bin/python -m pytest examples/RISCV32I/test/test_toolchain.py -v

# preservacao de comportamento das memorias (compara contra o RTL original)
~/venv-cocotb/bin/python -m pytest examples/RISCV32I/test/test_memory.py -v

# BASELINE RV32I -- tem de passar ANTES de olhar qualquer coisa de RV32M
~/venv-cocotb/bin/python -m pytest examples/RISCV32I/test/test_rv32i_baseline.py -v

# extensao M
~/venv-cocotb/bin/python -m pytest examples/RISCV32I/test/test_rv32m_mul.py -v
~/venv-cocotb/bin/python -m pytest examples/RISCV32I/test/test_rv32m_div.py -v
~/venv-cocotb/bin/python -m pytest examples/RISCV32I/test/test_rv32m_integration.py -v

# benchmarks .asm/.ram versionados
~/venv-cocotb/bin/python -m pytest examples/RISCV32I/test/test_programs.py -v

# --- medicoes ---------------------------------------------------------
# eficiencia: ciclos, instrucoes, CPI, stalls, flushes, instrucoes RV32M
~/venv-cocotb/bin/python examples/RISCV32I/tools/bench_compare.py
#   -> examples/RISCV32I/ppa/efficiency.json

# area e profundidade logica, por sintese real
~/venv-cocotb/bin/python examples/RISCV32I/tools/synth_ppa.py
#   -> examples/RISCV32I/ppa/ppa.json

# --- regenerar as imagens .ram ----------------------------------------
~/venv-cocotb/bin/python examples/RISCV32I/tools/build_programs.py

# --- inspecao manual --------------------------------------------------
# um teste com waveform; o caminho do .ghw sai no log
~/venv-cocotb/bin/python -m pytest \
  "examples/RISCV32I/test/test_rv32m_integration.py::TestObservability::test_waveform_is_produced" -v
gtkwave <caminho-do-.ghw>

# --- as duas configuracoes, direto no GHDL ----------------------------
cd /tmp && rm -rf rvchk && mkdir rvchk && cd rvchk
SRC=/mnt/c/Users/LKKam/Git/7semestre/SpecDrivenDesign-Generation-Verification_DigitalHardware/examples/RISCV32I/src
for f in cpu_package memory_package ALU mul_div_unit branching_unit control_unit \
         instruction_decoder extend_32 program_counter register_file data_ram \
         data_rom data_memory instruction_memory fetch_pipeline_register \
         decode_pipeline_register execute_pipeline_register mem_pipeline_register \
         hazard_control_unit CPU; do ghdl -a --std=08 $SRC/$f.vhd; done
ghdl -e --std=08 CPU                                    # exit 0
ghdl synth --std=08 -gRV32M_ENABLE=false --out=verilog CPU > cpu_rv32i.v
ghdl synth --std=08 -gRV32M_ENABLE=true  --out=verilog CPU > cpu_rv32im.v
yosys -p 'read_verilog cpu_rv32im.v; hierarchy -top CPU; proc; memory -nomap;
          opt_expr; techmap; opt_expr; stat'
```

> **Nota sobre o build.** `rv_build.py` compila o design uma vez por árvore de
> fontes e guarda em `$RV_BUILD_ROOT` (padrão `~/rv32_build_cache`). Rodar duas
> suítes em paralelo exige `RV_BUILD_ROOT` diferente em cada uma, senão dois
> GHDL escrevem na mesma biblioteca. O cache é invalidado sozinho quando
> qualquer fonte muda de tamanho ou data.

---

## Rastreabilidade

| Requisito | Onde é atendido | Onde é verificado |
|---|---|---|
| FR-RV-01 auditoria antes de alterar | `specs/decisions.md` ADR-000 | seção 1 |
| FR-RV-02 reusar CPU/ROM/RAM | RTL herdado, ADR-001 | seção 3 |
| FR-RV-03 ISA estritamente RISC-V | `rv_assembler.py` | `TestScopeGuards` |
| FR-RV-04 32 bits, x0..x31, x0 = 0, load/store | RTL herdado | `test_rv32i_baseline.py`, `TestX0` |
| FR-RV-05 CPU + ROM + RAM no top-level | `CPU.vhd` | toda execução |
| FR-RV-06 estado observável | ADR-002 | `test_memory.py` |
| FR-RV-07 comportamento preservado | ADR-002 | `TestBehaviourPreservation` |
| FR-RV-08 formato `.ram` documentado | ADR-003, `programs/README.md` | `TestRamImage` |
| FR-RV-09 imagem consumida pela ROM | `instruction_memory.vhd` | toda execução com `ROM_INIT_FILE` |
| FR-RV-10 constante VHDL segue válida | `ROM_INIT_FILE = ""` | `run_builtin_snapshot`, `ghdl synth` |
| FR-RV-11 baseline antes da extensão | — | `test_rv32i_baseline.py` |
| FR-RV-12 extensão RV32IM | `mul_div_unit.vhd`, ADR-007 | `test_rv32m_*.py` |
| FR-RV-13 as oito instruções | `mul_div_unit.vhd` | varreduras de 169 pares |
| FR-RV-14 casos especiais | `mul_div_unit.vhd` | `TestDivisionByZero`, `TestSignedOverflow` |
| FR-RV-15 reset | RTL herdado | `TestReset` |
| FR-RV-16 seleção por generic | `RV32M_ENABLE` | `TestScopeGuards`, ambas as suítes |
| FR-RV-17 hazards e latência | ADR-007 | `TestDataHazards`, `TestControlHazards`, `TestLatency` |
| FR-RV-18 benchmarks `.c` | `programs/*.c` | `programs/README.md` |
| FR-RV-19 programas `.asm` | `programs/*.asm` | `test_programs.py`, `TestScopeGuards` |
| FR-RV-20 ambiente verificado | ADR-004, ADR-006 | seção 1 |
| FR-RV-21 testbench cocotb | `rv_harness.py`, `tb_program.py` | `TestObservability` |
| FR-RV-22 casos de borda | `rv_m_cases.py` | varreduras |
| FR-RV-23 modelo de referência | `reference_model.py` | todo valor esperado |
| FR-RV-24 métricas | `rv_harness.py`, `bench_compare.py` | seção 7.1 |
| FR-RV-25 área sintetizada | `synth_ppa.py`, ADR-009 | seção 7.2 |
| NFR-RV-01 GHDL + cocotb | — | toda execução |
| NFR-RV-02 nada medido sem ferramenta | — | seções 7 e 9 |
| NFR-RV-03 mesma base de código | ADR-001 | seção 7.2 |
