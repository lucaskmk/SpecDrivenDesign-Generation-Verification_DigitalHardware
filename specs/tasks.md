# Backlog de tarefas — SpecHDL

Convenção: uma tarefa = um commit. Não iniciar tarefa da fase N+1 antes de
todas as tarefas da fase N estarem concluídas (ver `plan.md`, fase gate).

As fases **3b** e **4b** só se aplicam quando o design alvo é um processador
(RISC-V). Elas entram na ordem entre 3 e 4 e entre 4 e 5, respectivamente:
3 → 3b → 4 → 4b → 5. Para um design simples (ULA, demux), são puladas — mas
para uma CPU não são opcionais (FR-29).

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
- [ ] T0.6 — Criar `docker/Dockerfile` estendendo
  `rafaelcorsi/pl-descomp-cocotb` com o binutils cruzado RISC-V e o Yosys
  (NFR-05). Aceite: na imagem construída, `riscv64-unknown-elf-as
  --version`, `ghdl --version` e `yosys -V` respondem, e
  `make -C examples/toolchain_smoketest/test/` ainda passa dentro dela
- [ ] T0.7 — Validar a cadeia de montagem de ponta a ponta na imagem do
  T0.6: montar um `.S` mínimo de RV32I com
  `as -march=rv32i -mabi=ilp32` → `ld` → `objcopy -O binary` → `objdump`.
  Aceite: ELF, disassembly e binário são gerados dentro do container, num
  clone limpo do repo, sem instalar nada na máquina host

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
- [ ] T1.5 — Estender o schema da rubrica (`ingestion/schema.py` +
  `templates/rubrica.md`) com a seleção de ISA RISC-V: ISA base (RV32I),
  extensões padrão (M, A, F, D, C, Zicsr…) e extensões custom; o parser emite
  o bloco `isa` do `spec.json`, incluindo `declared_instructions` (FR-16).
  Aceite: pytest valida que marcar a extensão M no formulário produz
  `mul/mulh/mulhu/mulhsu/div/divu/rem/remu` em `declared_instructions`

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

## Fase 3b — Software de verificação de CPU (FR-18 … FR-22)

Só se aplica a design de processador. Ver `plan.md`, "Fase 3b/4b em detalhe".

- [ ] T3b.1 — Escrever a fixture golden `examples/riscv_base_test/`:
  `program.S` (assembly escrito à mão) e `linker.ld`, cobrindo todas as
  instruções do RV32I base declaradas como implementadas, cada resultado num
  endereço distinto de RAM, incluindo obrigatoriamente chamada/retorno
  (`jal`/`jalr`), uso de stack e leitura de `.rodata` via `auipc`/`lui`.
  Termina escrevendo o sentinela e entrando em loop infinito. Aceite: monta
  na imagem do T0.6 e o `program.dasm` gerado contém todos os mnemônicos
  listados em `instructions.json`
- [ ] T3b.2 — Escrever à mão o `expected_ram.json` golden do T3b.1, derivado
  da semântica do assembly (não de simulação), com `authored_by: "golden"` e
  sentinela de término. Aceite: revisão humana entrada por entrada — este
  arquivo é o oráculo, e depois de commitado a IA não o edita (princípio 9)
- [ ] T3b.3 — `spechdl/software/build.py`: wrapper de montagem
  (`as` → objeto, `ld` → ELF, `objdump` → disassembly, `objcopy` → binário),
  com `-march`/`-mabi` derivados das extensões do `spec.json` (FR-20).
  Aceite: pytest monta a fixture do T3b.1 dentro do container e confere os
  artefatos
- [ ] T3b.4 — `spechdl/software/rm.py`: conversor binário → `.rm` no formato
  de `plan.md` (uma palavra hex de 32 bits por linha) e gerador do
  `rom_image_pkg.vhd` a partir do `.rm` (FR-21). Aceite: round-trip
  `bin → .rm → array VHDL` bate palavra por palavra com o `objdump`; teste
  de regressão contra `examples/RISCV32I/` (o `.rm` gerado reproduz o
  `INSTRUCTION_MEMORY_CONTENT` que hoje está colado à mão)
- [ ] T3b.5 — Geração dos programas de teste de extensão (FR-19): para cada
  extensão declarada, um `program.S` que exercita todas as instruções que ela
  adiciona, mais o `expected_ram.json` correspondente, gravado antes da
  simulação (FR-22). Aceite: pytest verifica que o `expected_ram.json` existe
  e está commitado antes de qualquer artefato de simulação daquele programa
- [ ] T3b.6 — Guard-rail do princípio 9: o pipeline recusa sobrescrever
  qualquer `expected_ram.json` com `authored_by: "golden"`. Aceite: pytest
  confirma que a tentativa levanta erro e não altera o arquivo

## Fase 4 — Verificação (FR-10, FR-11, FR-12)
- [ ] T4.1 — Wrapper Python que roda `make -C outputs/<bloco>/test/`
  (cocotb + GHDL) para compilar + simular um bloco, capturando exit code,
  log e o caminho do waveform (`.vcd`)
- [ ] T4.2 — Mapeamento de falha de simulação → requisito não atendido +
  classificação bug de implementação vs. lacuna de spec/arquitetura (FR-11)
- [ ] T4.3 — Integração top-level: simular todos os blocos juntos (FR-12)
- [ ] T4.4 — Teste pytest: rodar fase 4 fim a fim no exemplo fixo e checar reprodutibilidade

## Fase 4b — Verificação em nível de programa (FR-23 … FR-29)

- [ ] T4b.1 — Testbench cocotb reaproveitável `test_program.py`: solta o
  reset, roda até o sentinela de término ou `max_cycles`, lê
  `data_ram_inst.memory` e compara com o `expected_ram.json` endereço por
  endereço (FR-23, FR-28). Aceite: roda contra a fixture do T3b.1 numa CPU
  de referência e passa
- [ ] T4b.2 — Decodificador de instrução em Python (palavra de 32 bits →
  mnemônico) e coletor de cobertura dinâmica a partir de
  `dbg_instr`/`dbg_valid` (FR-25). Aceite: pytest com vetores conhecidos por
  formato de instrução (R, I, S, B, U, J), incluindo o caso de instrução
  descartada em flush, que não pode contar como coberta
- [ ] T4b.3 — Gate de cobertura: comparar `declared_instructions` do
  `spec.json` com a união das instruções aposentadas em todos os programas e
  falhar listando `declared_not_retired`; reportar `retired_not_declared`
  como lacuna de spec (FR-26, FR-27). Aceite: pytest com um caso de
  instrução declarada e não coberta, que deve falhar com a lista nominal
- [ ] T4b.4 — Relatório de falha de RAM: endereço, esperado, obtido,
  instrução e extensão envolvidas, requisito e classificação — incluindo a
  classe `non_termination` (FR-24, FR-28)
- [ ] T4b.5 — Gate do teste obrigatório: se o base test falha, não roda
  extensão nem fase 5, e o relatório declara a CPU não verificada (FR-29).
  Aceite: pytest com CPU deliberadamente quebrada confirma que a fase 5 não
  é executada
- [ ] T4b.6 — `program_result.json` por programa, no contrato de `plan.md`
  (NFR-03)
- [ ] T4b.7 — Validar a interface de verificação padrão (FR-17): checar que a
  CPU gerada expõe `clk`, `rst`, `dbg_pc`, `dbg_instr`, `dbg_valid` e a RAM
  como `signal` acessível, falhando com mensagem explícita se faltar algo —
  senão a falha aparece como erro obscuro de hierarquia do cocotb

## Fase 5 — Análise PPA (FR-13, FR-14)
- [ ] T5.1 — Wrapper Yosys + ghdl-yosys-plugin para síntese e `stat` (contagem de células/área)
- [ ] T5.2 — Fallback heurístico caso a síntese não seja viável, marcado explicitamente como estimativa (FR-14)
- [ ] T5.3 — Teste pytest: validar campo `ppa` no `block_result.json` do exemplo fixo

## Fase 6 — Relatório (FR-15)
- [ ] T6.1 — Agregador que percorre `spec.json` → `architecture.json` → `block_result.json` de cada bloco e monta a cadeia de rastreabilidade
- [ ] T6.2 — Geração do relatório final em Markdown (opcionalmente exportável para PDF)
- [ ] T6.3 — Teste pytest: gerar relatório completo do exemplo fixo e validar que todos os FR/NFR aparecem rastreados
- [ ] T6.4 — Seção de CPU no relatório: cadeia extensão → programa → `.rm` →
  resultado da comparação de RAM, mais a tabela de cobertura instrução por
  instrução (declarada vs. aposentada) (FR-15, FR-26)

## Fase 7 — CLI e reprodutibilidade (NFR-01, NFR-02)
- [ ] T7.1 — Comando único `spechdl web` que abre o formulário Streamlit;
  submissão dispara as 6 fases em sequência, sem pausas humanas (NFR-01)
- [ ] T7.2 — Flag para rodar uma fase isolada reaproveitando artefatos anteriores (NFR-02)
- [ ] T7.3 — README com instruções de uso, incluindo setup de GHDL/Yosys
