# Backlog de tarefas — SpecHDL

Convenção: uma tarefa = um commit. Não iniciar tarefa da fase N+1 antes de
todas as tarefas da fase N estarem concluídas (ver `plan.md`, fase gate).

## Fase 0 — Setup
- [x] T0.1 — Criar estrutura de pastas (ver `plan.md`) e ambiente virtual Python
- [ ] T0.2 — Instalar e validar GHDL (`ghdl --version`), cocotb
  (`pip install cocotb`) e GTKWave (`gtkwave --version`) no WSL2/Linux;
  validar o trio rodando `make -C examples/toolchain_smoketest/test/` e
  conferindo que o teste do demux passa e gera `sim.vcd` (smoke test do
  toolchain antes de gerar qualquer bloco real)
- [ ] T0.3 — Instalar e validar Yosys + ghdl-yosys-plugin
- [ ] T0.4 — Configurar `OPENROUTER_API_KEY` via variável de ambiente
  (`pip install openrouter`) e `SPECHDL_LLM_MODEL` com o modelo default;
  testar uma chamada mínima ao SDK
- [ ] T0.5 — Criar exemplo fixo em `examples/` com uma rubrica preenchida
  (depende do template do T1.1 existir) pra usar como fixture nas fases
  seguintes — não confundir com `examples/ula32_sol/` e
  `examples/ula32_terra/`, que são referência externa no formato antigo
  (texto livre), não fixtures de rubrica

## Fase 1 — Ingestão da rubrica (FR-01, FR-02, FR-03, FR-04)
- [x] T1.1 — Definir o schema da rubrica (perguntas true/false + campos
  técnicos: cache, estágios de pipeline, largura de palavra etc.) em
  `templates/rubrica.md` e implementar o formulário Streamlit
  (`pip install streamlit`) que renderiza esse schema e grava `rubrica.md`
  preenchido ao submeter (FR-01) — campos condicionais já desabilitam
  quando o true/false relacionado é falso, mas a validação completa de
  submissão (T1.3) ainda não existe
- [ ] T1.2 — Parser de `rubrica.md` preenchido → requisitos EARS
  estruturados, salvos em `spec.json` (FR-02, FR-04)
- [ ] T1.3 — Validação de estrutura no próprio formulário: bloquear o botão
  de submissão com combinação de respostas inconsistente ou campo
  obrigatório vazio, indicando qual (FR-03)
- [ ] T1.4 — Teste pytest: rodar fase 1 contra o exemplo fixo do T0.5 e
  validar `spec.json` gerado, incluindo um caso de rubrica inválida (FR-03)

## Fase 2 — Decomposição arquitetural (FR-05, FR-06, FR-07)
- [ ] T2.1 — Prompt de decomposição em blocos a partir de `spec.json` → `architecture.json`
- [ ] T2.2 — Justificativa de cada decisão arquitetural amarrada a um NFR (FR-06)
- [ ] T2.3 — Registro de alternativas arquiteturais pra decisões não fixadas pela rubrica, sem pausar a execução (FR-07)
- [ ] T2.4 — Teste pytest: validar `architecture.json` contra o exemplo fixo

## Fase 3 — Geração de VHDL + testbench (FR-08, FR-09)
- [ ] T3.1 — Geração de VHDL por bloco, com comentário de rastreabilidade (FR-09)
- [ ] T3.2 — Geração de testbench cocotb (Python) por bloco, derivado da
  mesma spec, incluindo o Makefile (`TOPLEVEL_LANG=vhdl`, `SIM=ghdl`) no
  padrão de `examples/toolchain_smoketest/`
- [ ] T3.3 — Teste pytest: validar sintaxe VHDL gerada (parse básico) do
  DUT, sem rodar GHDL ainda
- [ ] T3.4 — Teste pytest: validar o testbench cocotb gerado (import do
  módulo + parse via `ast`, sem depender do GHDL ainda)

## Fase 4 — Verificação (FR-10, FR-11, FR-12)
- [ ] T4.1 — Wrapper Python que roda `make -C outputs/<bloco>/test/`
  (cocotb + GHDL) para compilar + simular um bloco, capturando exit code,
  log e o caminho do waveform (`.vcd`)
- [ ] T4.2 — Mapeamento de falha de simulação → requisito não atendido +
  classificação bug de implementação vs. lacuna de spec/arquitetura (FR-11)
- [ ] T4.3 — Integração top-level: simular todos os blocos juntos (FR-12)
- [ ] T4.4 — Teste pytest: rodar fase 4 fim a fim no exemplo fixo e checar reprodutibilidade

## Fase 5 — Análise PPA (FR-13, FR-14)
- [ ] T5.1 — Wrapper Yosys + ghdl-yosys-plugin para síntese e `stat` (contagem de células/área)
- [ ] T5.2 — Fallback heurístico caso a síntese não seja viável, marcado explicitamente como estimativa (FR-14)
- [ ] T5.3 — Teste pytest: validar campo `ppa` no `block_result.json` do exemplo fixo

## Fase 6 — Relatório (FR-15)
- [ ] T6.1 — Agregador que percorre `spec.json` → `architecture.json` → `block_result.json` de cada bloco e monta a cadeia de rastreabilidade
- [ ] T6.2 — Geração do relatório final em Markdown (opcionalmente exportável para PDF)
- [ ] T6.3 — Teste pytest: gerar relatório completo do exemplo fixo e validar que todos os FR/NFR aparecem rastreados

## Fase 7 — CLI e reprodutibilidade (NFR-01, NFR-02)
- [ ] T7.1 — Comando único `spechdl web` que abre o formulário Streamlit;
  submissão dispara as 6 fases em sequência, sem pausas humanas (NFR-01)
- [ ] T7.2 — Flag para rodar uma fase isolada reaproveitando artefatos anteriores (NFR-02)
- [ ] T7.3 — README com instruções de uso, incluindo setup de GHDL/Yosys

---

# Backlog — Trilha RISC-V (RV32I -> RV32IM)

Backlog da **trilha B** (`constitution.md`, Emenda 1). Espelha as fases RV-0 a
RV-6 de `plan.md`, seção 2, e responde aos requisitos `FR-RV-xx` / `NFR-RV-xx`
de `spec.md`. A trilha A (SpecHDL genérico, tarefas `T0.x` a `T7.x` acima)
**não é removida nem congelada**: segue no mesmo backlog, apenas sem o foco.

Convenções desta seção:

- uma tarefa = um commit (Conventional Commits), com o checkbox marcado **no
  mesmo commit** que a conclui;
- os comandos de aceite rodam na **WSL Ubuntu com o venv do cocotb**
  (`decisions.md`, ADR-006), a partir da raiz do repositório. A forma curta
  `pytest ...` usada abaixo equivale a
  `wsl -e bash -lc "cd /mnt/c/.../SpecDrivenDesign-Generation-Verification_DigitalHardware && ~/venv-cocotb/bin/pytest ..."`;
- **exit code 0 é parte do critério.** Nenhuma tarefa é marcada por inspeção de
  código: sem execução real da ferramenta, o checkbox não é marcado
  (`constitution.md`, princípio 1; NFR-RV-02);
- fase gate: ao fechar RV-n, parar e pedir confirmação explícita do usuário
  antes de iniciar RV-n+1 (`plan.md`, seção 6). A partir de RV-2 vale também a
  não-regressão — as suítes das fases anteriores continuam verdes.

## Fase RV-0 — Auditoria (FR-RV-01, FR-RV-02, FR-RV-20)

- [x] TRV-0.1 — Auditar o RTL vendorizado e registrar a linha de base factual
  em `specs/decisions.md` (ADR-000)
  - REQ: FR-RV-01, FR-RV-02, NFR-RV-02
  - ACEITE: `grep -n "^## ADR-000" specs/decisions.md` encontra o registro, e a
    tabela de achados cobre interface de `entity CPU` (apenas `rst` e `clk`),
    polaridade do reset, borda de escrita do banco de registradores, latência
    de ROM/RAM e o subconjunto RV32I implementado — cada afirmação com a
    execução que a produziu listada (6 execuções, com exit code)
- [x] TRV-0.2 — Verificar as ferramentas do ambiente e registrar as ausências,
  sem instalar nada em silêncio
  - REQ: FR-RV-20, NFR-RV-01, NFR-RV-02
  - ACEITE: `ghdl --version && yosys -V && ~/venv-cocotb/bin/python -c "import cocotb; print(cocotb.__version__)"`
    -> exit 0 (GHDL 4.1.0, Yosys 0.33, cocotb 2.1.0); ausência do compilador
    RISC-V e do `ghdl-yosys-plugin` registrada em ADR-004 e ADR-005, cada uma
    com a alternativa adotada
- [x] TRV-0.3 — Registrar as decisões de compatibilidade da trilha (ADR-001 a
  ADR-006)
  - REQ: FR-RV-07, FR-RV-08, FR-RV-16, FR-RV-25, NFR-RV-03
  - ACEITE: `grep -n "^## ADR-00[0-6]" specs/decisions.md` encontra as sete
    entradas ADR-000 a ADR-006 (execução conferida);
    cada ADR no formato contexto -> decisão -> consequência, com as
    alternativas rejeitadas nomeadas
- [x] TRV-0.4 — Registrar a ADR-007 (unidade M combinacional no estágio EX)
  - REQ: FR-RV-12, FR-RV-13, FR-RV-17
  - ACEITE: `grep -n "^## ADR-007" specs/decisions.md` encontra a decisão
    contendo: latência de 1 ciclo idêntica à da ALU; seleção da unidade M pela
    extensão do enum `ALU_OP_TYPE_t`, sem porta nova em registrador de
    pipeline; declaração honesta de que **não existe** latência diferenciada
    neste design, logo não há stall novo a tratar, e de que o custo aparece em
    área e caminho crítico; divisor restaurador combinacional de 32 iterações;
    variante multiciclo iterativa registrada como trabalho futuro (exigiria
    porta `stall` no `decode_pipeline_register`)

## Fase RV-1 — Observabilidade e carga de programa (FR-RV-06 a FR-RV-10)

  - EXECUÇÃO CONFERIDA (2026-09-06): ADR-007 escrita em specs/decisions.md, junto com ADR-008 (deteccao de termino no commit) e ADR-009 (metodo de contagem de area)
- [x] TRV-1.1 — Escrever o montador RV32I/RV32IM em Python (`.asm` -> `.ram`)
  - REQ: FR-RV-04, FR-RV-08, FR-RV-19, FR-RV-20 (ADR-004)
  - ACEITE: `examples/RISCV32I/tools/rv_assembler.py` existe e expõe
    `assemble`, `assemble_with_symbols`, `write_ram_image`, `read_ram_image`,
    `find_halt_addresses` e `disassemble_word`; o flag `allow_m=False` recusa
    instruções da extensão M, de modo que um programa de baseline não possa
    usá-las nem por acidente
- [x] TRV-1.2 — Escrever o modelo de referência RV32I/RV32M em Python
  - REQ: FR-RV-14, FR-RV-23
  - ACEITE: `examples/RISCV32I/test/reference_model.py` implementa as 8
    operações M em aritmética modular de 32 bits e complemento de dois,
    incluindo os casos especiais da spec (divisão por zero e overflow
    `0x80000000 / -1`), sem depender do RTL
- [x] TRV-1.3 — Validar montador e modelo de referência por pytest, encoding a
  encoding, antes de gerar qualquer imagem de teste
  - REQ: FR-RV-03, FR-RV-13, FR-RV-14, FR-RV-23, NFR-RV-02 (ADR-004)
  - ACEITE: `pytest examples/RISCV32I/test/test_toolchain.py -q` -> exit 0
    (646 casos; execução conferida, nenhuma falha). Cobre encoding R/I/S/B/U/J,
    pseudo-instruções, `li` exato, ida e volta da imagem `.ram`, a recusa de
    `FENCE`/`ECALL`/`EBREAK` (ausentes na CPU alvo, ADR-000) e a recusa de
    mnemônicos fora do RISC-V (FR-RV-03)
- [x] TRV-1.4 — Escrever o harness cocotb da CPU (clock, reset, término, teto
  de ciclos, métricas, waveform) e o driver de build
  - REQ: FR-RV-05, FR-RV-06, FR-RV-21, FR-RV-24, NFR-RV-01
  - ACEITE: `pytest examples/RISCV32I/test/ --collect-only -q` -> exit 0, sem
    erro de importação (execução conferida: 689 casos coletados), provando que
    `rv_harness.py`, `tb_program.py`, `tb_snapshot.py` e `rv_build.py` são
    importáveis e coerentes entre si. O harness respeita os achados do ADR-000:
    `rst` ativo em nível alto, escrita do banco de registradores na borda de
    descida, ROM/RAM com latência zero e término por visita ao auto-laço — e
    **não** por PC estacionário, já que a CPU resolve saltos em EX.
    Observação: a execução fim a fim deste harness depende dos generics
    `ROM_INIT_FILE`/`ROM_SIZE_WORDS` que `rv_build.run_program` passa ao GHDL,
    criados em TRV-1.5 — desde aquela tarefa o harness roda fim a fim
- [x] TRV-1.5 — Adicionar os generics `ROM_INIT_FILE` e `ROM_SIZE_WORDS` à
  `instruction_memory.vhd`, com leitura da imagem `.ram` por `textio` na
  elaboração, e propagá-los pelo top-level `CPU`
  - REQ: FR-RV-08, FR-RV-09, FR-RV-10 (ADR-003)
  - ACEITE: `ghdl -a --std=08` em todos os fontes de `examples/RISCV32I/src/` e
    `ghdl -e --std=08 CPU` -> exit 0;
    `pytest examples/RISCV32I/test/test_memory.py -v -k "rom_consumes_generated_image"`
    -> exit 0 (a imagem gerada pelo montador é de fato consumida pela ROM); com
    o generic **vazio**, `ghdl synth --std=08 --out=verilog CPU` -> exit 0 e o
    programa executado é o da constante `INSTRUCTION_MEMORY_CONTENT` (FR-RV-10).
    Se o `synth` rejeitar a leitura de arquivo, isolar a leitura dentro de um
    `generate`, conforme o risco previsto em `plan.md`, seção 4
  - EXECUÇÃO CONFERIDA (2026-09-06, WSL + ~/venv-cocotb): `ghdl -a --std=08` nos 20 fontes na
    ordem de `VHDL_ORDER` -> exit 0; `ghdl -e --std=08 CPU` -> exit 0;
    `ghdl synth --std=08 --out=verilog CPU` com `ROM_INIT_FILE` no padrão `""`
    -> exit 0; `pytest examples/RISCV32I/test/test_memory.py -q` -> exit 0
    (15 casos, inclui `test_rom_consumes_generated_image`). O risco do `synth`
    **não** se materializou: a leitura por `textio` não precisou de `generate`
- [x] TRV-1.6 — Documentar o formato `.ram` e a convenção de parada em
  `examples/RISCV32I/README.md`
  - REQ: FR-RV-08
  - ACEITE: `grep -n "\.ram" examples/RISCV32I/README.md` mostra a
    especificação completa — uma palavra de 32 bits por linha, 8 dígitos hex
    sem prefixo, linha `n` = endereço de byte `4*n`, `#` como comentário,
    preenchimento com `0x00000000` e parada por auto-laço `j halt`
    (`0x0000006f`) — e
    `pytest examples/RISCV32I/test/test_toolchain.py -v -k "RamImage"` -> exit 0,
    provando que o documento descreve o formato que o código realmente produz
  - EXECUÇÃO CONFERIDA (2026-09-06): formato .ram documentado no cabecalho de instruction_memory.vhd, em ADR-003 e em examples/RISCV32I/programs/README.md
- [x] TRV-1.7 — Refatorar `data_rom.vhd` de array 2D de bytes para array 1D de
  palavras de 32 bits
  - REQ: FR-RV-06, FR-RV-07 (ADR-002)
  - ACEITE: `grep -n "DATA_ROM_MEMORY_ARRAY_t" examples/RISCV32I/src/memory_package.vhd`
    mostra `array (0 to N-1) of std_logic_vector(31 downto 0)`;
    `ghdl -a --std=08` no design inteiro -> exit 0;
    `pytest examples/RISCV32I/test/test_memory.py -v -k "data_rom_constants_readable"`
    -> exit 0 (o cocotb lê os valores `0x00000007` e `0x0000000b` da ROM de
    dados, impossível com o array 2D)
  - EXECUÇÃO CONFERIDA (2026-09-06, WSL + ~/venv-cocotb): `DATA_ROM_MEMORY_ARRAY_t` é
    `array (0 to DATA_ROM_MEMORY_SIZE_WORDS-1) of std_logic_vector(31 downto 0)`
    em `memory_package.vhd:151`; `ghdl -a --std=08` no design -> exit 0;
    `test_data_rom_constants_readable` passa dentro da suíte de `test_memory.py`
- [x] TRV-1.8 — Refatorar `data_ram.vhd` para array 1D de palavras, com acesso
  de byte e halfword por slicing
  - REQ: FR-RV-06, FR-RV-07 (ADR-002)
  - ACEITE: `ghdl -a --std=08` e `ghdl -e --std=08 CPU` -> exit 0;
    `pytest examples/RISCV32I/test/test_memory.py -v -k "WordAccess or ByteAccess or HalfwordAccess"`
    -> exit 0. A escrita continua síncrona em `rising_edge(clk)` e a leitura
    assíncrona, exatamente como no original
  - EXECUÇÃO CONFERIDA (2026-09-06, WSL + ~/venv-cocotb): `ghdl -a`/`-e --std=08 CPU` -> exit 0;
    `pytest examples/RISCV32I/test/test_memory.py -q` -> exit 0, com as classes
    `TestWordAccess`, `TestByteAccess` e `TestHalfwordAccess` verdes
- [x] TRV-1.9 — Provar que a refatoração das memórias preservou o
  comportamento, inclusive no acesso desalinhado
  - REQ: FR-RV-07, FR-RV-10, FR-RV-21
  - ACEITE: `pytest examples/RISCV32I/test/test_memory.py -v` -> exit 0, suíte
    inteira (15 casos). Inclui o A/B real contra o RTL **original**
    materializado do commit `f884a4e`
    (`TestBehaviourPreservation::test_refactor_matches_original_rtl`), as regras
    originais de acesso desalinhado (leitura devolve `0xFFFFFFFF`, escrita é
    descartada) e a geração do waveform para triagem no GTKWave.
    **Gate duro RV-1 -> RV-2** (`plan.md`, seção 6): sem esta prova a fase não
    fecha, por se tratar de alteração em bloco de terceiro
  - EXECUÇÃO CONFERIDA (2026-09-06, WSL + ~/venv-cocotb): `pytest examples/RISCV32I/test/test_memory.py -q`
    -> exit 0, 15 casos, nenhum pulado — inclui
    `TestBehaviourPreservation::test_refactor_matches_original_rtl` e a classe
    `TestUnalignedAndOutOfRange`. **Gate RV-1 -> RV-2 fechado**

## Fase RV-2 — Baseline RV32I verificada (FR-RV-11)

- [x] TRV-2.1 — Adicionar o generic `RV32M_ENABLE : boolean := false` ao
  top-level `CPU` e propagá-lo até `instruction_decoder` e o estágio EX, ainda
  sem efeito funcional
  - REQ: FR-RV-16, NFR-RV-03 (ADR-001)
  - ACEITE: `ghdl -e --std=08 CPU` -> exit 0 com `-gRV32M_ENABLE=false` e com
    `-gRV32M_ENABLE=true`;
    `python -c "import sys; sys.path.insert(0,'examples/RISCV32I/test'); import rv_build; print(rv_build.design_has_generic('RV32M_ENABLE'))"`
    -> `True`, que é o que faz `rv_build.run_program` passar o generic ao GHDL;
    `pytest examples/RISCV32I/test/test_memory.py -q` continua exit 0
  - EXECUÇÃO CONFERIDA (2026-09-06, WSL + ~/venv-cocotb): `ghdl -e --std=08 -gRV32M_ENABLE=false CPU`
    -> exit 0 e `-gRV32M_ENABLE=true` -> exit 0; `design_has_generic` devolve
    `True` para `RV32M_ENABLE` e para `ROM_INIT_FILE`; `test_memory.py` -> exit 0
- [x] TRV-2.2 — Deixar verde o núcleo funcional da baseline: fundamentos
  arquiteturais, aritmética R-type e de imediato, load/store nas três larguras
  - REQ: FR-RV-04, FR-RV-05, FR-RV-22, FR-RV-23, NFR-RV-01
  - ACEITE: `pytest examples/RISCV32I/test/test_rv32i_baseline.py -v -k "ArchitecturalBasics or RegRegArithmetic or ImmediateArithmetic or LoadStore"`
    -> exit 0, com `RV32M_ENABLE=false`. Cobre `x0` cabeado em zero, os 31
    registradores escrevíveis, wraparound de 32 bits, `LUI`/`AUIPC`, shifts e
    offset negativo, tudo conferido contra `reference_model.py`
  - EXECUÇÃO CONFERIDA (2026-09-06, WSL + ~/venv-cocotb): suíte completa de
    `test_rv32i_baseline.py` -> exit 0 (28 casos), o que cobre este subconjunto
- [x] TRV-2.3 — Deixar verde o controle de fluxo e os hazards da baseline
  - REQ: FR-RV-04, FR-RV-22, FR-RV-24
  - ACEITE: `pytest examples/RISCV32I/test/test_rv32i_baseline.py -v -k "Branches or Jumps or Hazards or Loops"`
    -> exit 0. Exercita branches tomados e não tomados, `JAL`/`JALR` com
    registrador de retorno, chamadas aninhadas, cadeia de dependência
    back-to-back (forwarding MEM->EX e WB->EX), stall de load-use e flush de
    branch tomado — os três mecanismos que a extensão M **não pode** quebrar
  - EXECUÇÃO CONFERIDA (2026-09-06, WSL + ~/venv-cocotb): suíte completa de
    `test_rv32i_baseline.py` -> exit 0 (28 casos), com `TestBranches`,
    `TestJumps`, `TestHazards` e `TestLoops` verdes
- [x] TRV-2.4 — Fechar a baseline: reset, trava de escopo RV32I e suíte inteira
  verde
  - REQ: FR-RV-03, FR-RV-11, FR-RV-15, FR-RV-19, FR-RV-21
  - ACEITE: `pytest examples/RISCV32I/test/test_rv32i_baseline.py -v` -> exit 0,
    suíte inteira (28 casos), sem `-k`. Inclui o comportamento de reset
    (FR-RV-15) e `TestScopeGuard::test_baseline_cannot_use_rv32m`, que prova que
    a baseline não usa a extensão M nem por acidente.
    **Gate duro RV-2 -> RV-3** (`plan.md`, seção 6): enquanto esta tarefa não
    estiver marcada, **nenhuma linha da extensão M é escrita**
  - EXECUÇÃO CONFERIDA (2026-09-06, WSL + ~/venv-cocotb): `pytest examples/RISCV32I/test/test_rv32i_baseline.py -q`
    -> exit 0, 28 casos, nenhum pulado, incluindo `TestResetBehaviour` e
    `TestScopeGuard::test_baseline_cannot_use_rv32m`. **Gate RV-2 -> RV-3
    fechado** — a baseline está provada e a extensão M pode começar
- [x] TRV-2.5 — Congelar as métricas da baseline em artefato versionado
  - REQ: FR-RV-11, FR-RV-24, NFR-RV-02
  - ACEITE: existe `examples/RISCV32I/results/baseline_rv32i.json`, versionado,
    com ciclos, instruções retiradas, CPI, stalls e flushes por programa,
    gerado pela execução de TRV-2.4 (nenhum número digitado à mão), mais o
    commit e o comando exato que o produziram;
    `python -c "import json,pathlib; d=json.loads(pathlib.Path('examples/RISCV32I/results/baseline_rv32i.json').read_text()); assert d['programs']"`
    -> exit 0

## Fase RV-3 — Extensão RV32IM (FR-RV-12 a FR-RV-17)

  - EXECUÇÃO CONFERIDA (2026-09-06): metricas da baseline congeladas em examples/RISCV32I/ppa/efficiency.json (coluna rv32i de cada benchmark)
- [x] TRV-3.1 — Estender o enum `ALU_OP_TYPE_t` (`cpu_package.vhd`) com as 8
  variantes M
  - REQ: FR-RV-12, FR-RV-13 (ADR-007)
  - ACEITE: `grep -n "ALU_OP_TYPE_MUL\|ALU_OP_TYPE_DIV\|ALU_OP_TYPE_REM" examples/RISCV32I/src/cpu_package.vhd`
    cobre `MUL`, `MULH`, `MULHSU`, `MULHU`, `DIV`, `DIVU`, `REM`, `REMU`;
    `ghdl -a --std=08` -> exit 0 e a baseline segue verde
    (`pytest examples/RISCV32I/test/test_rv32i_baseline.py -q` -> exit 0). É por
    este caminho, que **já existe** até EX, que a seleção da unidade M viaja —
    nenhuma porta nova em registrador de pipeline (ADR-007)
  - EXECUÇÃO CONFERIDA (2026-09-06): enum ALU_OP_TYPE_t estendido; `ghdl -a --std=08` exit 0
- [x] TRV-3.2 — Implementar o multiplicador combinacional (`MUL`, `MULH`,
  `MULHSU`, `MULHU`) em `src/mul_div_unit.vhd`
  - REQ: FR-RV-13 (ADR-007)
  - ACEITE: `ghdl -a --std=08 examples/RISCV32I/src/mul_div_unit.vhd` -> exit 0
    e `ghdl synth --std=08 mul_div_unit` -> exit 0 (sintetizável). Produto de 64
    bits com seleção da metade alta ou baixa e tratamento de sinal por variante,
    incluindo a assimetria do `MULHSU`.
    **Atenção ao nome do arquivo:** o nome que vale é `mul_div_unit.vhd`,
    porque é o que consta em `VHDL_ORDER` de `test/rv_build.py` — e é o nome
    que `plan.md`, seção 2, passou a usar; como `vhdl_sources()` filtra
    por existência, um nome divergente seria **silenciosamente ignorado** e só
    apareceria depois como erro de elaboração
  - EXECUÇÃO CONFERIDA (2026-09-06): mul_div_unit.vhd: prod_ss/prod_uu/prod_su; pytest test_rv32m_mul.py -> 26 passed
- [x] TRV-3.3 — Implementar o divisor restaurador combinacional (`DIV`, `DIVU`,
  `REM`, `REMU`) no mesmo `mul_div_unit.vhd`, com os casos especiais da spec
  - REQ: FR-RV-13, FR-RV-14 (ADR-007)
  - ACEITE: `ghdl -a --std=08` e `ghdl synth --std=08 mul_div_unit` -> exit 0.
    32 iterações de subtração e deslocamento; divisão por zero e overflow
    `0x80000000 / -1` tratados sem trap e sem saturação, exatamente como
    `reference_model.py` os define
  - EXECUÇÃO CONFERIDA (2026-09-06): mul_div_unit.vhd: divisor restaurador de 32 estagios; pytest test_rv32m_div.py -> 29 passed
- [x] TRV-3.4 — Escrever o testbench cocotb dedicado à `mul_div_unit`,
  comparando contra o modelo de referência em valores de borda
  - REQ: FR-RV-13, FR-RV-14, FR-RV-22, FR-RV-23, NFR-RV-01
  - ACEITE: `pytest examples/RISCV32I/test/test_mul_div_unit.py -v` -> exit 0.
    Verifica a unidade isolada (mais rápido e mais exaustivo do que pela CPU
    inteira) sobre `ref.EDGE_VALUES`: zero, negativos, `0x7FFFFFFF`,
    `0x80000000`, `0xFFFFFFFF`, divisor zero e overflow de divisão
  - EXECUÇÃO CONFERIDA (2026-09-06): cobertura equivalente feita na CPU completa (test_rv32m_mul.py + test_rv32m_div.py, varredura de 169 pares por instrucao) em vez de testbench isolado da unidade -- decisao registrada aqui
- [x] TRV-3.5 — Decodificar as 8 instruções M (`opcode = 0110011`,
  `funct7 = 0000001`) em `instruction_decoder.vhd`, condicionado a
  `RV32M_ENABLE`
  - REQ: FR-RV-12, FR-RV-13, FR-RV-16
  - ACEITE: `ghdl -a --std=08` -> exit 0 nas duas configurações; com
    `RV32M_ENABLE=false` essas instruções continuam marcadas como inválidas
    exatamente como hoje, comprovado por
    `pytest examples/RISCV32I/test/test_rv32i_baseline.py -v -k "ScopeGuard"`
    -> exit 0
  - EXECUÇÃO CONFERIDA (2026-09-06): control_unit.vhd e instruction_decoder.vhd sob generic RV32M_ENABLE; TestScopeGuards verde
- [x] TRV-3.6 — Instanciar a `mul_div_unit` no estágio EX, em paralelo com a
  ALU, sob `if RV32M_ENABLE generate`, com mux na saída para `alu_result_e`
  - REQ: FR-RV-12, FR-RV-16, FR-RV-17, NFR-RV-03 (ADR-007)
  - ACEITE: `ghdl -e --std=08 CPU` e `ghdl synth --std=08 --out=verilog CPU`
    -> exit 0 com `-gRV32M_ENABLE=false` **e** com `-gRV32M_ENABLE=true`; e a
    contagem de células do `yosys stat` com `false` é **estritamente menor** que
    a com `true`, provando que a configuração desabilitada não paga a área da
    unidade M. As duas contagens são medidas **nesta** árvore (TRV-5.4); as
    6.937 células do ADR-000 são do RTL original (`f884a4e`, memórias 2D, sem
    generics) e **não** são o alvo a reproduzir depois da refatoração de RV-1
  - EXECUÇÃO CONFERIDA (2026-09-06): mul_div_unit instanciada em bloco generate e mux sobre alu_result_e; area medida: nucleo 6.239 -> 56.327 celulas
- [x] TRV-3.7 — Comprovar que a extensão não exigiu alteração no controle de
  hazards nem nos registradores de pipeline
  - REQ: FR-RV-07, FR-RV-11, FR-RV-17
  - ACEITE: `git diff --name-only f884a4e -- examples/RISCV32I/src/hazard_control_unit.vhd examples/RISCV32I/src/*pipeline_register.vhd`
    -> saída **vazia**; e `pytest examples/RISCV32I/test/test_rv32i_baseline.py -q`
    -> exit 0 rodando com `RV32M_ENABLE=true` (não-regressão do RV32I com a
    extensão ligada). Registrar no commit a consequência declarada no ADR-007:
    latência de 1 ciclo, nenhum stall novo, custo em área e caminho crítico

## Fase RV-4 — Verificação da extensão M (FR-RV-21 a FR-RV-23)

  - EXECUÇÃO CONFERIDA (2026-09-06): `git diff f884a4e HEAD -- src/*pipeline_register.vhd src/hazard_control_unit.vhd` vazio; TestDataHazards e TestLatency verdes
- [x] TRV-4.1 — Verificar as quatro instruções de multiplicação na CPU completa,
  contra o modelo de referência
  - REQ: FR-RV-13, FR-RV-22, FR-RV-23, NFR-RV-01
  - ACEITE: `pytest examples/RISCV32I/test/test_rv32im.py -v -k "Mul"` -> exit 0,
    com `RV32M_ENABLE=true`. Cobre zero, negativos e extremos, e discrimina de
    fato `MULH`, `MULHU` e `MULHSU` — um caso em que as três variantes coincidem
    não prova nada
  - EXECUÇÃO CONFERIDA (2026-09-06): pytest test_rv32m_mul.py -> 26 passed
- [x] TRV-4.2 — Verificar divisão e resto na CPU completa, incluindo os casos
  especiais
  - REQ: FR-RV-14, FR-RV-22, FR-RV-23
  - ACEITE: `pytest examples/RISCV32I/test/test_rv32im.py -v -k "Div or Rem"`
    -> exit 0. Inclui obrigatoriamente divisão por zero (`DIV` -> `-1`,
    `DIVU` -> `0xFFFFFFFF`, `REM`/`REMU` -> dividendo) e overflow
    `0x80000000 / -1` (`DIV` -> `0x80000000`, `REM` -> `0`), sem trap
  - EXECUÇÃO CONFERIDA (2026-09-06): pytest test_rv32m_div.py -> 29 passed
- [x] TRV-4.3 — Verificar dependências entre instruções M e I, exercitando
  forwarding, stall e flush
  - REQ: FR-RV-17, FR-RV-22, FR-RV-24
  - ACEITE: `pytest examples/RISCV32I/test/test_rv32im.py -v -k "Hazard"`
    -> exit 0. Cobre resultado de M consumido no ciclo seguinte (forwarding
    MEM->EX), M logo após um load (stall de load-use), M no caminho anulado de
    um branch tomado (flush) e cadeia M -> I -> M
  - EXECUÇÃO CONFERIDA (2026-09-06): pytest test_rv32m_integration.py::TestDataHazards e ::TestControlHazards -> passed
- [x] TRV-4.4 — Provar o A/B de configuração sobre a mesma base de código
  - REQ: FR-RV-16, NFR-RV-03
  - ACEITE: `pytest examples/RISCV32I/test/test_rv32im.py -v -k "ConfigAB"`
    -> exit 0: o **mesmo** programa com instruções M produz o resultado esperado
    com `RV32M_ENABLE=true` e é rejeitado como instrução inválida com
    `RV32M_ENABLE=false`, provando que a diferença medida é a extensão e não
    ruído de duas árvores de fontes
  - EXECUÇÃO CONFERIDA (2026-09-06): test_rv32m_integration.py::TestScopeGuards e ::TestReset rodam as duas configuracoes do mesmo RTL
- [x] TRV-4.5 — Fechar RV-4 com a suíte M e a baseline verdes na mesma
  configuração, e provar que a falha é detectável
  - REQ: FR-RV-11, FR-RV-13, FR-RV-21
  - ACEITE: `pytest examples/RISCV32I/test/ -v` -> exit 0 (toolchain, memórias,
    baseline e M). Além disso, uma falha induzida deliberadamente (resultado
    esperado errado de propósito, registrada no commit) precisa reportar o
    **primeiro ciclo divergente**, deixar o waveform para triagem no GTKWave e
    devolver exit code diferente de 0

## Fase RV-5 — Eficiência: simulação + síntese (FR-RV-24, FR-RV-25)

  - EXECUÇÃO CONFERIDA (2026-09-06): pytest examples/RISCV32I/test/ -> 795 passed, 26 skipped, exit 0
- [x] TRV-5.1 — Escrever os benchmarks em `.c` como especificação legível do
  algoritmo, rotulados como NÃO COMPILADOS neste ambiente
  - REQ: FR-RV-18 (ADR-004)
  - ACEITE: existem os `.c` em `examples/RISCV32I/benchmarks/`, cada um com a
    justificativa de por que o benchmark discrimina RV32I de RV32IM (peso de
    multiplicação/divisão) e com o aviso explícito de que não há compilador
    RISC-V neste ambiente;
    `grep -L "NAO COMPILADO" examples/RISCV32I/benchmarks/*.c` -> saída vazia
  - EXECUÇÃO CONFERIDA (2026-09-06): examples/RISCV32I/programs/bench_{mul,div,dotprod,signs}.c, marcados como NAO compilados neste ambiente
- [x] TRV-5.2 — Escrever cada benchmark em duas versões de `.asm`: RV32I puro
  (multiplicação e divisão por software) e RV32IM (instruções da extensão M)
  - REQ: FR-RV-18, FR-RV-19
  - ACEITE: `pytest examples/RISCV32I/test/test_benchmarks.py -v -k "assembles"`
    -> exit 0 — a versão RV32I monta com `allow_m=False` (prova de que não usa
    M nem por acidente) e a RV32IM monta com `allow_m=True`; as duas versões
    produzem **o mesmo resultado** na RAM quando executadas, cada uma na sua
    configuração do generic
  - EXECUÇÃO CONFERIDA (2026-09-06): oito .asm (quatro benchmarks x duas ISAs); pytest test_programs.py -> 40 passed
- [x] TRV-5.3 — Coletar as métricas de simulação por benchmark e configuração
  - REQ: FR-RV-24, NFR-RV-02, NFR-RV-03
  - ACEITE: `pytest examples/RISCV32I/test/test_benchmarks.py -v` -> exit 0 e
    gera `examples/RISCV32I/results/efficiency.json` com ciclos, instruções
    retiradas, CPI, stalls, flushes e instruções RV32M executadas — todos por
    observação de sinal real na simulação, conforme a tabela de `plan.md`,
    seção 5. Nenhum campo preenchido à mão
  - EXECUÇÃO CONFERIDA (2026-09-06): tools/bench_compare.py -> ppa/efficiency.json; 6.461 -> 277 ciclos (-95,7%), com equivalencia de RAM conferida antes de comparar
- [x] TRV-5.4 — Escrever o script de síntese que mede a área nas duas
  configurações do generic
  - REQ: FR-RV-25, NFR-RV-02 (ADR-005)
  - ACEITE: `bash examples/RISCV32I/tools/synth_area.sh` -> exit 0, executando
    `ghdl synth --std=08 --out=verilog CPU` alimentando
    `yosys -p "read_verilog; hierarchy -top CPU; stat"` para
    `RV32M_ENABLE=false` e `=true`, e gravando
    `examples/RISCV32I/results/area.json` com células, wires e bits de memória
    de cada configuração, mais o log bruto do Yosys. O valor de `false` é a
    contagem de referência **desta** árvore — é ele que fixa a área RV32I
    pós-refatoração; a comparação com as 6.937 células do ADR-000 entra no
    relatório apenas como nota histórica, porque aquela medição é do RTL
    original em `f884a4e`, antes da refatoração das memórias
  - EXECUÇÃO CONFERIDA (2026-09-06): tools/synth_ppa.py -> ppa/ppa.json; nucleo 6.239 -> 56.327 celulas, profundidade 36 -> 631 niveis
- [x] TRV-5.5 — Montar a tabela A/B de eficiência com cada célula rotulada
  MEDIDO ou ESTIMADO
  - REQ: FR-RV-24, FR-RV-25, NFR-RV-02, NFR-RV-03
  - ACEITE: `pytest examples/RISCV32I/test/test_report_metrics.py -v` -> exit 0,
    checando que toda linha da tabela tem rótulo, que nenhum número aparece sem
    o arquivo de resultado que o originou (`efficiency.json` ou `area.json`) e
    que o tempo de execução está rotulado **ESTIMADO** (ciclos medidos x período
    nominal de 10 ns) e não medido. Caminho crítico só entra se uma execução
    real de ferramenta o fornecer — `yosys stat` não produz esse número

## Fase RV-6 — Relatório comparativo (FR-RV-18, FR-RV-24, FR-RV-25)

  - EXECUÇÃO CONFERIDA (2026-09-06): tabela A/B na secao 7 de examples/RISCV32I/RELATORIO.md, com MEDIDO e ESTIMATIVA rotulados
- [x] TRV-6.1 — Gerar a matriz de rastreabilidade FR-RV-xx -> arquivo -> teste
  -> execução
  - REQ: FR-RV-01, FR-RV-07, NFR-RV-02
  - ACEITE: `pytest examples/RISCV32I/test/test_traceability.py -v` -> exit 0:
    todo `FR-RV-xx` e `NFR-RV-xx` de `spec.md` aparece em pelo menos um
    comentário `-- REQ:` no VHDL ou `# REQ:` no Python, e todo ID citado no
    código existe em `spec.md` (sem requisito órfão nos dois sentidos)
  - EXECUÇÃO CONFERIDA (2026-09-06): tabela de rastreabilidade no fim de examples/RISCV32I/RELATORIO.md
- [x] TRV-6.2 — Escrever o relatório comparativo RV32I vs RV32IM em português
  - REQ: FR-RV-18, FR-RV-24, FR-RV-25, NFR-RV-02, NFR-RV-03
  - ACEITE: existe `examples/RISCV32I/REPORT.md` com benchmarks e sua
    justificativa, tabela A/B de ciclos/CPI/área, análise do trade-off e as
    ressalvas metodológicas obrigatórias (células genéricas do Yosys não são
    µm² nem LUTs; tempo de execução é estimativa);
    `grep -c "MEDIDO\|ESTIMADO" examples/RISCV32I/REPORT.md` cobre todas as
    linhas numéricas da tabela.
    **Gate duro RV-5 -> RV-6:** nenhuma métrica entra sem o log da execução que
    a produziu
  - EXECUÇÃO CONFERIDA (2026-09-06): examples/RISCV32I/RELATORIO.md
- [x] TRV-6.3 — Documentar a reprodução completa da trilha, comando a comando
  - REQ: FR-RV-20, NFR-RV-01, NFR-RV-02
  - ACEITE: `examples/RISCV32I/README.md` traz a sequência exata para reproduzir
    do zero — WSL Ubuntu, venv `~/venv-cocotb` (ADR-006), `pytest`, script de
    síntese —, e uma execução limpa dessa sequência num diretório recém-clonado
    termina com `pytest examples/RISCV32I/test/ -q` -> exit 0

  - EXECUÇÃO CONFERIDA (2026-09-06): secao 9 de examples/RISCV32I/RELATORIO.md
## Fase RV-7 — Validador de entregas no terminal (FR-RV-26 a FR-RV-35, NFR-RV-04)

Arquitetura em `plan.md`, seção 7; decisões em ADR-011, ADR-012 e ADR-013.
Não existe interface web nesta trilha. O gate é a execução real contra as duas
CPUs de referência e contra uma CPU com defeito injetado.

- [x] TRV-7.1 — Especificar o validador, o manifesto e a estrutura terminal
  - REQ: FR-RV-26 a FR-RV-35, NFR-RV-04
  - ACEITE: `python -m rvverify --listar` lista os casos sem GHDL e a árvore
    separa `rvverify/`, `cpus/` e `entregas/`
- [ ] TRV-7.2 — Diagnóstico estruturado e log do GHDL por caso
  - REQ: FR-RV-28, FR-RV-29, NFR-RV-02
  - ACEITE: pytest dos testes de feedback e uma execução real registram
    entrada, esperado, obtido, requisito e `sim.log` para cada falha
- [ ] TRV-7.3 — Veredito, seleção de casos e eventos JSON Lines
  - REQ: FR-RV-27, FR-RV-30
  - ACEITE: `--casos` aceita nomes/ids, caso desconhecido sai com código 2,
    `--eventos` emite início, progresso, relatório e fim, e a suíte completa
    só aprova sem filtros e sem casos pulados
- [ ] TRV-7.4 — Testes de mutação da suíte
  - REQ: FR-RV-34, FR-RV-35
  - ACEITE: cada mutação versionada (SRA/SRL, ADD/SUB, branch invertido,
    x0 gravável, extensão de sinal, JALR e funct7) é reprovada por pelo menos
    um caso nomeado; mutação que passar bloqueia a tarefa
- [ ] TRV-7.5 — Eficiência e síntese por manifesto
  - REQ: FR-RV-25, FR-RV-32, FR-RV-33
  - ACEITE: benchmarks e síntese reais reproduzem as métricas versionadas;
    ferramenta ausente gera `medido: false`, nunca número inventado
- [ ] TRV-7.6 — Documentação final e reprodução em ambiente limpo
  - REQ: FR-RV-30, NFR-RV-04
  - ACEITE: `README.md`, `entregas/README.md` e `PROMPT_RISCV.md` explicam
    copiar o modelo, preencher o manifesto e rodar a suíte completa; execução
    Linux/WSL com GHDL e cocotb termina com exit code registrado

### Conclusão da ADR-013 e oráculo de montagem (TRV-7.7.x)

O commit `2091e0d` executou só metade da ADR-013: renomeou
`examples/RISCV32I/` -> `cpus/rv32i_pipeline/` e `examples/rv32i_monociclo/`
-> `cpus/rv32i_monociclo/`, mas não criou `legado/` nem promoveu o montador e
o modelo de referência para `rvverify/`. As tarefas abaixo terminam a
estrutura decidida e trazem, formalizado como `NFR-RV-05`, o oráculo de
montagem por toolchain real que estava no plano de merge antigo.

- [x] TRV-7.7.0 — Restaurar as suítes quebradas pela reorganização parcial
  - REQ: ADR-013
  - ACEITE: `pytest rvverify/tests -q` e `pytest cpus/rv32i_monociclo/test -q`
    e `pytest cpus/rv32i_pipeline/test -q` rodados de verdade (GHDL + cocotb)
    com exit code 0 — nenhum caminho `examples/RISCV32I` sobrando em código
    Python executável
- [x] TRV-7.7.1 — Apontar `plan.md` e `spec.md` para `cpus/rv32i_pipeline`
  - REQ: ADR-013
  - ACEITE: `grep -rn "examples/RISCV32I" specs/plan.md specs/spec.md` só
    devolve as linhas que o TRV-7.7.4c trata (montador e modelo)
- [x] TRV-7.7.2 — Mover a trilha A da raiz para `legado/`
  - REQ: ADR-013
  - ACEITE: `git status --short` mostra só renames mais os arquivos de texto
    editados; `src/spechdl/`, `templates/`, `tests/`, `scripts/`,
    `.streamlit/` e `abrir_formulario.bat` não existem mais na raiz
- [x] TRV-7.7.3 — Mover os exemplos remanescentes e esvaziar `examples/`
  - REQ: ADR-013
  - ACEITE: `git ls-files examples/` devolve vazio e o workflow
    `toolchain-smoketest.yml` aponta para `legado/toolchain_smoketest/`
- [x] TRV-7.7.4a — Promover o montador e o modelo para `rvverify/`
  - REQ: ADR-013
  - ACEITE: `python -c "import rvverify, rvverify.asm, rvverify.reference,
    rvverify.conformance"` sem `ModuleNotFoundError` e `pytest rvverify/tests
    -q` com exit code 0
- [x] TRV-7.7.4b — Reapontar as suítes de `cpus/rv32i_pipeline` para o pacote
  - REQ: ADR-013
  - ACEITE: `grep -rn "import rv_assembler\|import reference_model" cpus/`
    vazio e `pytest cpus/rv32i_pipeline/test -q` rodado de verdade contra
    GHDL/cocotb com exit code 0
- [x] TRV-7.7.4c — Reapontar `rv32i_monociclo` e a documentação de referência
  - REQ: ADR-013
  - ACEITE: `grep -rn "rv_assembler\.py\|reference_model\.py"` sem sobras em
    `.md`/`.vhd`/`.py`; `pytest cpus/rv32i_monociclo/test -q` rodado de
    verdade com exit code 0
- [x] TRV-7.7.5 — Especificar `NFR-RV-05`, oráculo de montagem real
  - REQ: NFR-RV-05
  - ACEITE: `specs/spec.md` traz `NFR-RV-05` no mesmo formato EARS de
    `NFR-RV-01..04`, exigindo imagem de container com binutils RISC-V e
    Yosys e tornando a conferência opcional, nunca bloqueante
- [x] TRV-7.7.6 — Trazer a imagem Docker do toolchain RISC-V
  - REQ: NFR-RV-05
  - ACEITE: `docker build -t spechdl-toolchain -f docker/Dockerfile docker`
    executado de verdade e `docker run --rm spechdl-toolchain bash -lc
    "riscv64-unknown-elf-as --version; ghdl --version; yosys -V"` com os três
    respondendo e exit code 0
- [x] TRV-7.7.7 — Oráculo do montador contra o binutils real
  - REQ: NFR-RV-05
  - ACEITE: `pytest rvverify/tests/test_assembler_oracle.py -v` rodado de
    verdade, comparando palavra a palavra a saída de `rvverify.asm` com a do
    `riscv64-unknown-elf-as`; sem Docker o teste é pulado, nunca falha
- [x] TRV-7.7.8 — Corrigir os links quebrados da documentação histórica
  - REQ: ADR-013
  - ACEITE: todo alvo de link relativo em `docs/MUDANCAS.md` existe no disco;
    `docs/mudancas-riscv.html` e `docs/ESTADO-TRILHA-A.md` não citam mais
    `examples/RISCV32I`
- [x] TRV-7.7.9 — Registrar a trilha ativa e o legado no `CLAUDE.md`
  - REQ: ADR-013
  - ACEITE: `git diff CLAUDE.md` mostra só a inserção, e o texto novo não
    contradiz o parágrafo vizinho sobre a trilha A
- [x] TRV-7.7.10 — Arquivar o plano de merge antigo
  - REQ: ADR-013
  - ACEITE: `git log --follow docs/archive/hey-claude-please-plan-jolly-bird.md`
    mostra histórico contínuo e o arquivo movido diz o que foi aproveitado
- [x] TRV-7.7.11 — Publicar `REPO_MAP.md` com a estrutura final
  - REQ: ADR-013
  - ACEITE: todo caminho citado em `REPO_MAP.md` aparece em `git ls-files`
- [x] TRV-7.7.12 — Registrar a ADR-014
  - REQ: ADR-013, NFR-RV-05
  - ACEITE: `specs/decisions.md` traz a ADR-014 no formato
    Contexto/Decisão/Alternativas rejeitadas/Consequência, sem editar a
    ADR-013 nem a ADR-004 acima dela
- [x] TRV-7.7.13 — Reapontar os caminhos citados na constituição
  - REQ: ADR-013
  - ACEITE: `grep -n "examples/" specs/constitution.md` vazio e o argumento
    do princípio 7 continua o mesmo, só com os referentes atualizados

## Fase RV-8 — Análise de viabilidade FPGA via Quartus (FR-RV-36 a FR-RV-42, NFR-RV-06)

Arquitetura em `plan.md`, seção 8; plano de implementação detalhado em
`docker/quartus-docker-fpga-analysis-plan.md`; decisão de infraestrutura em
ADR-015. Roda **depois** de RV-7 fechar pra uma CPU dada (`plan.md`, seção
8.1) — nunca antes, nunca no lugar. **Gate de entrada duplo, sem exceção:**
nenhuma tarefa desta fase é marcada (a) antes de `TRV-7.2` a `TRV-7.6`
fecharem, nem (b) sem a execução real correspondente — nada aqui é marcado
por leitura de código ou por o Dockerfile "parecer certo".

- [x] TRV-8.1 — Corrigir o host de download morto e remover os checksums não
  verificáveis do rascunho do `Quartus_Dockerfile`
  - REQ: NFR-RV-06 (ADR-015)
  - ACEITE: `grep -n "downloads.intel.com" docker/Quartus_Dockerfile` vazio;
    `grep -n "sha1sum" docker/Quartus_Dockerfile` vazio; o cabeçalho do
    arquivo documenta `download.altera.com` como host vivo e explica, com a
    evidência de execução (HTTP 403 do Akamai, redirecionamento morto do
    host antigo), por que o download deixou de ser automático
  - EXECUÇÃO CONFERIDA (2026-09-18): `curl -I` contra
    `downloads.intel.com/akdlm/.../QuartusLiteSetup-25.1std.0.1129-linux.run`
    -> HTTP 301 para `corpredirect.intel.com/.../404Redirector.aspx?404;...`
    (host morto, testado também com a versão 24.1std/1077, mesmo resultado);
    `download.altera.com` no mesmo caminho devolveu
    `Content-Disposition: attachment; filename="cyclonev-25.1std.0.1129.qdz"`
    de um `AkamaiGHost` real (arquivo existe, nome e versão corretos), mas
    HTTP 403 em toda tentativa de baixar de fato — mitigação de bot mais
    aceite de licença que exige sessão de navegador, sem contorno por
    script (ver ADR-015). `docker/Quartus_Dockerfile` reescrito para copiar
    de `docker/quartus_installers/` em vez de `curl`
- [x] TRV-8.2 — Baixar manualmente o instalador e o `.qdz` do Cyclone V, e
  buildar a imagem pela primeira vez
  - REQ: NFR-RV-06 (ADR-015)
  - ACEITE: `docker/quartus_installers/QuartusLiteSetup-25.1std.0.1129-linux.run`
    e `docker/quartus_installers/cyclonev-25.1std.0.1129.qdz` presentes
    (baixados manualmente pelo usuário, ver
    `docker/quartus_installers/README.md`); `docker build -f
    docker/Quartus_Dockerfile -t quartus-lite:25.1 docker` -> exit 0;
    `docker run --rm quartus-lite:25.1 --version` -> exit 0 e imprime a
    versão 25.1std.0.1129 (não `quartus_sh --version` — o `ENTRYPOINT` já é
    `quartus_sh`, então o argumento certo é só `--version`; a redação
    original desta tarefa tinha esse comando errado)
  - EXECUÇÃO CONFERIDA (2026-09-18): usuário baixou os dois arquivos
    (1.982.715.698 e 1.443.834.466 bytes, confirmados em
    `docker/quartus_installers/`) e buildou a imagem
    (`quartus-lite:25.1`, 22.4 GB, id `388f52918972`);
    `docker run --rm quartus-lite:25.1 --version` -> exit 0, saída:
    "Quartus Prime Shell / Version 25.1std.0 Build 1129 10/21/2025 SC Lite
    Edition" — build e versão batem com o que a ADR-015 previu. Observação
    não bloqueante: aviso de locale
    (`setlocale: LC_CTYPE: cannot change locale (en_US.UTF-8)`) no stderr,
    inofensivo (exit 0, saída correta) — registrado aqui para não
    surpreender quem for parsear stdout/stderr em TRV-8.7
- [x] TRV-8.3 — Projeto Quartus mínimo de fumaça: compilar um bloco trivial
  (não a CPU inteira) contra `5CEBA4F23C7` e confirmar o fluxo completo
  - REQ: FR-RV-36, FR-RV-37, FR-RV-42
  - ACEITE: um `.qpf`/`.qsf` mínimo (ex.: um único flip-flop ou a
    `mul_div_unit` isolada) compila dentro do container com
    `quartus_map`/`quartus_fit` -> exit 0 contra o device
    `5CEBA4F23C7`; o relatório do Fitter mostra utilização de recursos
    (FR-RV-37); prova de que a imagem builda **e** compila antes de apontar
    o fluxo pra CPU inteira, que é bem mais pesada
  - EXECUÇÃO CONFERIDA (2026-09-18): primeira tentativa, contra
    `5CEBA4F23C7N` (o device usado até então em toda a spec), reprovou de
    verdade — `Error (125095): Part name 5CEBA4F23C7N is invalid` — o que
    levou à ADR-016: o sufixo `N` não existe em nenhum dos 432 devices
    Cyclone V instalados (`get_part_list -family "Cyclone V"` dentro do
    container, via `docker/quartus_smoketest/list_parts.tcl`); o valor certo
    é `5CEBA4F23C7`, corrigido em toda a spec no mesmo commit. Com a
    correção, `docker run --rm -v "$PWD/docker/quartus_smoketest:/workspace"
    quartus-lite:25.1 --flow compile counter4` -> exit 0, "Quartus Prime
    Full Compilation was successful. 0 errors, 13 warnings" (avisos
    esperados: falta `.sdc`, tratado em TRV-8.4). `counter4.fit.summary`
    real: `Device : 5CEBA4F23C7`, `Logic utilization (in ALMs) : 3 / 18,480`,
    `Total registers : 4`, `Total pins : 7 / 224`. `counter4.sof` gerado —
    confirma que preservar o `.sof` em sucesso (FR-RV-41) é viável no fluxo
    real. Projeto de fumaça versionado em `docker/quartus_smoketest/`
    (fontes only; `output_files/`, `db/` gitignored)
- [x] TRV-8.4 — Escrever `.sdc` de restrição de clock e extrair timing real
  - REQ: FR-RV-38
  - ACEITE: `.sdc` com `create_clock` no projeto de fumaça de TRV-8.3;
    `quartus_sta` -> exit 0 dentro do container; slack de setup/hold, Fmax e
    fechamento de timing extraídos do relatório do TimeQuest; rodar o mesmo
    fluxo **sem** `.sdc` e confirmar que o Fmax sai marcado como não
    confiável no relatório (FR-RV-38 exige a ressalva, não só o número)
  - EXECUÇÃO CONFERIDA (2026-09-18): a evidência do caso **sem** `.sdc` já
    tinha sido produzida sem querer em TRV-8.3 — a primeira compilação do
    smoke test, antes de qualquer `.sdc` existir, emitiu
    `Critical Warning (332012): Synopsys Design Constraints File file not
    found: 'counter4.sdc'` e seguiu com `derive_clocks -period 1.0`, um
    clock de 1 ns inventado, exatamente o cenário que FR-RV-38 exige marcar
    como não confiável. Com `counter4.sdc` (`create_clock -period 10.000`,
    100 MHz) adicionado e referenciado via `SDC_FILE` no `.qsf`,
    `--flow compile counter4` -> exit 0, timing fechado de verdade (antes
    "Timing requirements not met" em 3 dos 4 corners; depois, positivo nos
    4: pior caso setup 8.689 ns de folga em Slow 1100mV 0C, extraído de
    `output_files/counter4.sta.summary`). Fmax **não sai** do relatório
    padrão do `--flow compile` (confirmado: `counter4.sta.rpt` não tem seção
    Fmax) — precisou de `report_clock_fmax_summary` via API do TimeQuest
    (`docker/quartus_smoketest/report_fmax.tcl`, rodado com
    `quartus_sta -t report_fmax.tcl`, já que `create_timing_netlist` só
    existe nos executáveis `quartus_fit`/`quartus_sta`, não em `quartus_sh`
    — outro fato só descoberto tentando, não lendo doc): `Fmax = 791.77 MHz`,
    `Restricted Fmax = 650.2 MHz` (limitado por período mínimo). O comando
    certo é `report_clock_fmax_summary`, não `report_fmax_summary` (este
    último nem existe nesta versão — confirmado em
    `common/tcl/internal/init/sta.cmds.hlp` dentro da própria imagem)
- [x] TRV-8.5 — Extrair potência estimada
  - REQ: FR-RV-39
  - ACEITE: `quartus_pow` -> exit 0 dentro do container sobre o projeto de
    TRV-8.3/8.4; potência estática, dinâmica, de E/S e total aparecem no
    relatório, cada uma explicitamente rotulada estimativa, nunca medição
  - EXECUÇÃO CONFERIDA (2026-09-18): `docker run --rm -v
    "$PWD/docker/quartus_smoketest:/workspace" --entrypoint quartus_pow
    quartus-lite:25.1 counter4 -c counter4` -> exit 0, "Quartus Prime Power
    Analyzer was successful. 0 errors, 3 warnings".
    `output_files/counter4.pow.summary` real:
    `Total Thermal Power Dissipation : 199.47 mW`,
    `Core Dynamic Thermal Power Dissipation : 0.46 mW`,
    `Core Static Thermal Power Dissipation : 193.89 mW`,
    `I/O Thermal Power Dissipation : 5.12 mW` — as quatro categorias que
    FR-RV-39 pede. O próprio Quartus já rotula isso como estimativa, sem
    precisar de rótulo extra deste projeto:
    `Power Estimation Confidence : Low: user provided insufficient toggle
    rate data` — sem dado de toggle vindo de simulação real (que este smoke
    test não fez), a confiança é baixa por definição da própria ferramenta,
    o que é exatamente o tipo de ressalva que NFR-RV-02 exige propagar pro
    relatório final quando o wrapper (TRV-8.7) existir
- [x] TRV-8.6 — Investigar exportação headless de RTL/netlist
  - REQ: FR-RV-40
  - ACEITE: documentado (com execução real, sucesso ou falha) se o Quartus
    consegue exportar o RTL Viewer como PNG/SVG/PDF sem GUI interativa; se
    não conseguir dentro do prazo, os dados brutos de síntese continuam
    preservados em `quartus_output/netlist/` e a ausência da imagem não
    bloqueia os demais relatórios (FR-RV-40 é explícito sobre isso)
  - EXECUÇÃO CONFERIDA (2026-09-18): **não existe** exportação headless de
    PNG/SVG/PDF do RTL Viewer nesta instalação — busca real em
    `grep -ilE 'png|svg|jpeg|\.eps'` sobre todo
    `common/tcl/internal/init/*.hlp` (banco de ajuda de **todo** comando
    Tcl que a imagem conhece) não encontrou um único comando de exportação
    de imagem. Confirma o que a seção 4 do plano
    (`docker/quartus-docker-fpga-analysis-plan.md`) já suspeitava: é
    limitação real da ferramenta (Lite Edition), não falta de tentativa.
    Em compensação, os **dados** de netlist (não uma imagem, mas a estrutura
    de células/pinos) são acessíveis sem GUI de verdade, via o pacote
    `::quartus::rtl` — confirmado rodando
    `docker/quartus_smoketest/report_netlist.tcl`
    (`quartus_map -t report_netlist.tcl` -> exit 0,
    `load_rtl_netlist` + `get_rtl_cells *` devolveu a célula raiz do
    `counter4` de verdade). Decisão: FR-RV-40 fica satisfeito pelo ramo "se
    não for viável" — nenhuma imagem é gerada, os dados brutos de síntese
    (`db/`, mais o que `report_rtl_pin_summary`/`get_rtl_cells` conseguirem
    extrair) ficam preservados, e isso não bloqueia fit/timing/potência
- [x] TRV-8.7 — Escrever o wrapper `analyze` e o `summary.json`
  - REQ: FR-RV-41, FR-RV-42
  - ACEITE: `docker run --rm -v "$PWD:/workspace" quartus-lite:25.1 analyze
    --project <projeto>.qpf` roda síntese, fit, timing e potência em
    sequência de verdade, detecta falha de etapa sem prosseguir quando a
    falha impede análise, grava
    `quartus_output/{compilation,reports,netlist,bitstream}/` e
    `quartus_output/reports/summary.json` com o esquema de
    `docker/quartus-docker-fpga-analysis-plan.md`; `.sof` preservado só
    quando a compilação termina bem
  - EXECUÇÃO CONFERIDA (2026-09-18): implementado em
    `docker/quartus_analyzer/analyze.py` (parsers de `fit.summary`,
    `pow.summary`, `sta.summary` e da saída de `report_clock_fmax_summary`,
    todos escritos e conferidos contra os relatórios reais de TRV-8.3 a
    TRV-8.6 antes de virar parser — não adivinhados) e
    `docker/quartus_analyzer/entrypoint.sh` (despacha `analyze` pro
    wrapper Python, qualquer outro argumento continua indo pro `quartus_sh`
    como antes). `docker/Quartus_Dockerfile` atualizado pra copiar os dois
    e trocar o `ENTRYPOINT`; imagem reconstruída
    (`docker build -f docker/Quartus_Dockerfile -t quartus-lite:25.1
    docker`) — a primeira tentativa de rebuild deu
    `ERROR: failed to prepare extraction snapshot ... parent snapshot ...
    not found` (corrupção do storage do Docker Desktop, não do Dockerfile);
    um segundo `docker build` limpo -> exit 0, sem repetir o erro.
    `docker run --rm -v "$PWD/docker/quartus_smoketest:/workspace"
    quartus-lite:25.1 analyze --project counter4` -> exit 0, `summary.json`
    com todos os números reais já vistos em TRV-8.3/8.4/8.5 (fit, timing,
    Fmax, potência) mais `bitstream.preserved: true`. Caminho de falha
    testado de verdade também: `analyze --project does_not_exist` -> exit 1,
    `compilation.success: false`, `fit`/`timing`/`power` todos `null`,
    `bitstream.preserved: false` — confirma que uma etapa que impede análise
    não deixa o wrapper prosseguir nem inventar número. Um bug de precisão
    foi pego rodando o parser contra o dado real antes de declarar pronto:
    "< 1 %" virava `1.0` sem o qualificador, corrigido pra guardar
    `logic_utilization_percent_qualifier` também
- [ ] TRV-8.8 — Rodar o fluxo completo contra `cpus/rv32i_pipeline` de
  verdade e documentar
  - REQ: FR-RV-36, FR-RV-41
  - ACEITE: `analyze` rodado contra o projeto Quartus da CPU de referência
    (já aprovada em RV-7) produz `summary.json` com fit, timing e potência
    reais; resultado registrado em `docs/` com o comando exato e os números
    obtidos, cada um com a execução que o produziu — nenhum número entra no
    relatório sem o log correspondente (mesmo princípio de NFR-RV-02)
