# Plano técnico — SpecHDL

## Stack
- Python 3.11+
- OpenRouter (SDK nativo, `pip install openrouter`) — extração de spec,
  decomposição arquitetural e geração de VHDL (chamadas de LLM); acesso
  unificado a múltiplos modelos por trás de uma única API, modelo escolhido
  via `SPECHDL_LLM_MODEL`, não hardcoded no código
- GHDL — compilação e simulação VHDL
- cocotb — testbench em Python, dirige o DUT VHDL através do GHDL (fluxo
  `make SIM=ghdl`); ambiente de referência é a imagem Docker
  `rafaelcorsi/pl-descomp-cocotb`, a mesma usada no smoke test de
  `legado/toolchain_smoketest/`
- GTKWave — inspeção visual do waveform (`.vcd`) gerado pela simulação,
  usado na triagem manual de falha quando a classificação automática
  (FR-10) não é suficiente
- Yosys + ghdl-yosys-plugin — síntese real para métricas PPA
- pytest — testes do pipeline Python
- python-dotenv — carrega `.env` (chave do OpenRouter, modelo default) em
  desenvolvimento local
- Streamlit — formulário web local da fase 1 (rubrica interativa: true/false
  + campos técnicos), único ponto de entrada do pipeline (FR-01, NFR-01)
- Typer (ou argparse) — CLI (`spechdl web` abre o formulário; demais
  comandos de reprodutibilidade, ver fase 7)

## Estrutura de pastas proposta

```
specHDL/
├── CLAUDE.md
├── specs/
│   ├── constitution.md
│   ├── spec.md
│   ├── plan.md
│   └── tasks.md
├── templates/
│   └── rubrica.md            # schema/documentação de referência das
│                              # perguntas — o formulário Streamlit
│                              # implementa essas mesmas perguntas (FR-01)
├── src/
│   └── spechdl/
│       ├── ingestion/       # fase 1 — formulário Streamlit + parsing da
│       │                    # rubrica preenchida em EARS
│       ├── architecture/    # fase 2 — decomposição em blocos
│       ├── codegen/         # fase 3 — geração VHDL + testbench
│       ├── verification/    # fase 4 — wrapper do GHDL
│       ├── ppa/             # fase 5 — wrapper do Yosys/ghdl-yosys-plugin
│       ├── report/          # fase 6 — geração do relatório final
│       └── cli.py
├── examples/
│   ├── alu_4bit/              # caso de teste fixo, não faz parte do core
│   └── toolchain_smoketest/   # smoke test do toolchain GHDL+cocotb (T0.2),
│       ├── src/                # não gerado pelo pipeline, fixo
│       └── test/
├── tests/                    # testes pytest do pipeline
└── outputs/                  # artefatos gerados por execução (gitignored)
    └── <bloco>/
        ├── src/<bloco>.vhd
        └── test/
            ├── test_<bloco>.py
            └── Makefile       # segue o padrão cocotb (TOPLEVEL_LANG=vhdl, SIM=ghdl)
```

## Contratos de dados entre fases (JSON simplificado)

**spec.json** (saída da fase 1):
```json
{
  "requirements": [
    {"id": "FR-01", "type": "functional", "text": "...", "source_field": "tem_cache"},
    {"id": "NFR-01", "type": "non_functional", "category": "power|speed|area", "text": "..."}
  ]
}
```
`source_field` aponta pra pergunta/campo da rubrica que originou o requisito
— substitui o antigo `source_excerpt` (que fazia sentido pra texto livre,
não pra uma rubrica estruturada).

**architecture.json** (saída da fase 2):
```json
{
  "blocks": [
    {
      "name": "alu",
      "inputs": ["a", "b", "opcode"],
      "outputs": ["result", "flags"],
      "responsibility": "...",
      "satisfies": ["FR-06", "NFR-02"],
      "design_rationale": "..."
    }
  ],
  "connections": [{"from": "control_unit", "to": "alu", "signal": "opcode"}]
}
```

**block_result.json** (saída das fases 3–5, por bloco):
```json
{
  "block": "alu",
  "vhdl_path": "...",
  "testbench_path": "...",
  "testbench_framework": "cocotb",
  "makefile_path": "...",
  "simulation": {
    "status": "pass|fail",
    "log_path": "...",
    "waveform_path": "...",
    "failed_requirement": null,
    "failure_class": "implementation|spec_gap|null"
  },
  "ppa": {"cells": 0, "estimated_critical_path_ns": 0, "method": "synthesis|heuristic"}
}
```

## Fase 1 em detalhe — formulário Streamlit em vez de texto livre
`templates/rubrica.md` documenta o schema das perguntas (true/false — `Tem
cache?` — e campos técnicos — `Estágios de pipeline: __`, `Largura de
palavra (bits): __` etc.); `spechdl web` sobe um app Streamlit local que
renderiza esse mesmo schema como widgets (checkbox, number_input). O aluno
responde na interface e clica em submeter — nesse momento o app grava
`rubrica.md` preenchido (versionável, NFR-03) e dispara o resto do pipeline
automaticamente, sem pausa humana (NFR-01). A validação de estrutura (FR-03)
roda no próprio formulário antes de liberar o botão de submissão (ex.:
campo `estágios_pipeline` desabilitado se `tem_pipeline` estiver marcado
"não"), não depois. O parser da fase 1 não precisa de LLM pra extrair
sentido de texto ambíguo — é essencialmente determinístico; o que sobra pra
IA é montar o `spec.json` em EARS a partir das respostas já validadas. Não
confundir com os exemplos de referência em `legado/ula32_sol/` e
`legado/ula32_terra/` — esses foram gerados contra o modelo antigo (texto
livre) por um agente externo, servem só como prova de que o método SDD
funciona ponta a ponta, não como formato de fixture pra fase 1.

## Fase 3/4 em detalhe — testbench via cocotb
Cada bloco gerado vem com um testbench cocotb (Python) e um `Makefile` no
padrão `TOPLEVEL_LANG = vhdl`, `SIM = ghdl`, `MODULE = test_<bloco>`,
`VHDL_SOURCES = ../src/<bloco>.vhd` — o mesmo padrão usado em
`legado/toolchain_smoketest/`. O wrapper Python da fase 4 (T4.1) roda
`make -C outputs/<bloco>/test/` e captura exit code + log, em vez de chamar
`ghdl` diretamente; quem invoca o GHDL por baixo é o próprio cocotb. Ambiente
de referência (usado também na CI de smoke test): imagem Docker
`rafaelcorsi/pl-descomp-cocotb`.

Quando a simulação falha (FR-10), a triagem decide entre duas rotas: bug de
implementação — regenerar o bloco na própria fase 3 — ou lacuna de
spec/arquitetura — voltar pra fase 1 (spec incompleta) ou fase 2 (decomposição
errada), ver `constitution.md` princípio 5. O waveform (`.vcd`) fica salvo em
`waveform_path` no `block_result.json` pra inspeção manual no GTKWave quando a
classificação automática não é suficiente pra decidir a rota.

## Fase 5 em detalhe — por que síntese real em vez de a IA "chutar" PPA
Yosys, com o plugin ghdl-yosys-plugin, lê VHDL usando o GHDL como frontend,
sintetiza para uma biblioteca de células genérica e roda o comando `stat`
para contagem de células/área. Isso dá números de verdade em vez de uma
estimativa da LLM — muito mais defensável numa apresentação acadêmica. Se o
setup do plugin não for viável dentro do prazo da disciplina, cair para o
fallback heurístico do FR-13, deixando isso explícito no relatório final.

## Acesso a LLM — por que OpenRouter
Decisão do professor da disciplina: todas as chamadas de LLM do pipeline
(extração EARS na fase 1, decomposição na fase 2, geração de VHDL na fase 3)
passam pelo SDK nativo do OpenRouter (`pip install openrouter`), não pelo
Anthropic SDK direto — substituição total, não convivência dos dois. O
OpenRouter dá acesso a vários provedores/modelos por trás de uma única API
com uma única chave (`OPENROUTER_API_KEY`), o que facilita controle de custo
e de acesso pra turma inteira. O modelo usado não fica fixo no código: é lido
de `SPECHDL_LLM_MODEL` (variável de ambiente), seguindo o princípio 7 da
constitution (ferramenta genérica, não hardcoded). Default atual (em
`.env.example`): `openai/gpt-5.6-luna`, um modelo rápido/econômico — se uma
fase específica (ex.: decomposição arquitetural) precisar de mais raciocínio,
trocar o valor da variável é suficiente, sem alterar código. T0.4 valida a
chave e faz uma chamada mínima antes de qualquer uso real nas fases
seguintes; `scripts/llm_playground.py` é o utilitário solto pra isso — não é
código de pipeline, é só validação manual de conectividade.

## Fase gate
Não iniciar a fase N+1 até que todas as tarefas da fase N em `tasks.md`
estejam marcadas como concluídas e o critério de aceite verificado — ver
`constitution.md`, princípio 1. Isso inclui aprovação humana explícita: os
testes automatizados passando não bastam pra avançar de fase — pare ao final
de cada fase e aguarde confirmação do usuário antes de iniciar a tarefa
seguinte.

Nota: este gate é sobre o processo de **desenvolver** o SpecHDL (fase por
fase de `tasks.md`) — não sobre a **execução** do pipeline já pronto, que
roda sem pausas humanas depois que o aluno submete a rubrica (NFR-01). São
dois conceitos de "fase" com o mesmo nome por coincidência (o backlog de
desenvolvimento espelha as fases do próprio pipeline), não confundir os
dois.

---

# Plano técnico — Trilha RISC-V (RV32I -> RV32IM)

Trilha paralela à do SpecHDL genérico (Emenda 1 da `constitution.md`). A
geração genérica de arquitetura passa a segundo plano; aqui o objeto é uma
CPU RISC-V concreta e existente, que será validada como baseline RV32I e
depois estendida para RV32IM, com medição de eficiência antes/depois sobre a
**mesma** base de código. Nada aqui é derivado por leitura de código: todos os
fatos vêm de execução real de ferramenta, registrada em `specs/decisions.md`
(ADR-000) — este plano só os organiza em fases.

## 1. Ponto de partida (auditoria ADR-000)

O que já existe em `cpus/rv32i_pipeline/src/` (19 arquivos VHDL, autoria de
Morgan Demange, `simple_RISCV_RV32I_vhdl`, vendorizado no commit `f884a4e`):

| Aspecto | Fato verificado | Onde |
|---|---|---|
| Entidade top-level | `entity CPU`, portas **apenas** `rst` e `clk`. Nenhuma saída observável | `CPU.vhd` |
| Microarquitetura | Pipeline de 5 estágios (F, D, E, M, WB), Harvard, domínio de clock único | `CPU.vhd` |
| Reset | `rst` **ativo em nível alto**, assíncrono | `program_counter.vhd:41`, `register_file.vhd:58` |
| Banco de registradores | Escrita na **borda de descida** de `clk` (decisão original para reduzir hazards); leitura assíncrona; `x0` fixo em zero | `register_file.vhd:60` |
| ROM de instruções | **Assíncrona, latência 0 ciclo**, sem porta de clock. `pc_f` -> `addr`, instrução válida no mesmo ciclo | `instruction_memory.vhd` |
| Conteúdo da ROM | Constante VHDL `INSTRUCTION_MEMORY_CONTENT` (97 palavras / 388 bytes). **Não lê arquivo nenhum** | `memory_package.vhd` |
| ROM de dados | Assíncrona, 8 bytes, base `0x00FC8000`, array 2D | `data_rom.vhd` |
| RAM de dados | Leitura **assíncrona (latência 0)**, escrita síncrona em `rising_edge(clk)`, 512 bytes, base `0x00FC8100`, array 2D | `data_ram.vhd` |
| Roteamento de dados | Wrapper compara `alu_result_m` com as bases e escolhe RAM ou ROM | `data_memory.vhd:64` |
| Mapa de memória | Instruções `0x00000000`+; DATA_ROM `0x00FC8000`; DATA_RAM `0x00FC8100` | confirmado em `linker.ld` |
| Hazards | Forwarding MEM->EX e WB->EX; stall de 1 ciclo em load-use; flush em branch/jump tomado; preditor always-not-taken | `hazard_control_unit.vhd` |
| Cobertura da ISA | RV32I base completo **exceto** `FENCE`, `ECALL`, `EBREAK` (decoder marca inválidas). Sem CSR, sem interrupções. `invalid_instr` ligado a `open` | `instruction_decoder.vhd`, `CPU.vhd:168` |
| Testbench VHDL existente | `CPU_tb.vhd` **nunca rodou**: literais `5ns`/`12ns`/`1ms` sem espaço, ilegais em VHDL, falham até com `-frelaxed` | `CPU_tb.vhd` |
| Toolchain disponível | GHDL 4.1.0 (mcode), Yosys 0.33, cocotb 2.1.0 em `~/venv-cocotb`, make, gtkwave — WSL Ubuntu 24.04 | ADR-006 |
| Toolchain ausente | Compilador RISC-V (qualquer variante) e `ghdl-yosys-plugin` | ADR-004, ADR-005 |
| Baseline de área | **6.937 células**, 22.302 wires, 3.104 bits de memória — medição real sobre o RTL **original** (`f884a4e`), **antes** da refatoração de memórias de RV-1 e da introdução dos generics. Serve de referência histórica, **não** de valor a reproduzir depois de RV-1 | ADR-000, ADR-005 |

Conclusão da auditoria: a CPU é ponto de partida válido e funcional (cocotb
observou `pc_f` avançando até `0x154` e `x28 = 0x0b`). Os problemas reais não
estão na CPU, e sim na **observabilidade** (arrays 2D invisíveis ao VPI do
GHDL) e na **carga de programa** (constante VHDL editada à mão).

## 2. Fases da trilha (RV-0 a RV-6)

### RV-0 — Auditoria (CONCLUÍDA)
- **Entrada:** repositório no commit `f884a4e`.
- **Saída:** `specs/decisions.md` com ADR-000 (fatos verificados por execução)
  e ADR-001..006 (decisões). Baseline de área do RTL original já medida
  (referência histórica; ver a ressalva na tabela da seção 1).
- **Requisitos:** FR-RV-01, FR-RV-02, FR-RV-20.

### RV-1 — Observabilidade e carga de programa
- **Entrada:** RTL original + ADR-002 + ADR-003.
- **Trabalho:**
  1. Refatorar `data_ram.vhd` e `data_rom.vhd` de
     `array (0 to N, 3 downto 0) of std_logic_vector(7 downto 0)` (2D) para
     `array (0 to N-1) of std_logic_vector(31 downto 0)` (1D de palavras),
     implementando acesso de byte e halfword por slicing. Motivo: o VPI do
     GHDL **não expõe arrays 2D** — `dut.data_memory.data_ram.memory` dá
     `AttributeError`, enquanto arrays 1D (`register_file.registers`,
     `instruction_memory.memory`) são lidos sem problema.
  2. Adicionar generic `ROM_INIT_FILE : string := ""` à
     `instruction_memory.vhd`: vazio mantém `INSTRUCTION_MEMORY_CONTENT`
     (preserva o caminho de síntese, FR-RV-10); preenchido lê a imagem `.ram`
     por `textio` na elaboração.
  3. Montador `rvverify/asm.py` (`.asm` -> `.ram`), validado por pytest
     encoding a encoding **antes** de gerar qualquer imagem de teste (ADR-004).
- **Saída:** memórias legíveis pelo cocotb; troca de programa sem editar VHDL;
  montador validado.
- **Gate:** `ghdl -a` e `ghdl -e` exit 0 no design inteiro; teste de
  equivalência provando comportamento de memória preservado, **inclusive** a
  regra original de acesso desalinhado (leitura retorna `0xFFFFFFFF`, escrita
  descartada) — é alteração em bloco de terceiro e FR-RV-07 exige a prova;
  `ghdl synth` continua exit 0 com `ROM_INIT_FILE` vazio.
- **Requisitos:** FR-RV-06, FR-RV-07, FR-RV-08, FR-RV-09, FR-RV-10.

### RV-2 — Baseline RV32I verificada
- **Entrada:** design de RV-1 elaborado com `RV32M_ENABLE = false`.
- **Trabalho:** suíte cocotb sobre `entity CPU` cobrindo o subconjunto RV32I
  implementado — aritmética, lógica, shifts, comparações, load/store nas três
  larguras, branches, `JAL`/`JALR`, `LUI`/`AUIPC`, comportamento de `x0`,
  reset (FR-RV-15) e os cenários de hazard (load-use, forwarding MEM->EX e
  WB->EX, flush de branch tomado). Comparação contra o modelo de referência
  Python (`rvverify/reference.py`, aritmética modular de 32 bits em
  complemento de dois).
- **Saída:** baseline funcional **provada**, mais o snapshot de métricas de
  simulação. A contagem de células desta árvore é remedida em RV-5 (ADR-005):
  as 6.937 células do ADR-000 são do RTL original e **não** são o alvo depois da
  refatoração de RV-1.
- **Gate (FR-RV-11):** suíte inteira verde, com exit code 0, em execução real
  de GHDL+cocotb. **Nenhuma linha da extensão M é escrita antes disso** — sem
  baseline provada não existe comparação honesta a fazer.
- **Requisitos:** FR-RV-03, FR-RV-04, FR-RV-05, FR-RV-11, FR-RV-15,
  FR-RV-19, FR-RV-21, FR-RV-22, FR-RV-23, NFR-RV-01.

### RV-3 — Extensão RV32IM
- **Entrada:** baseline verde de RV-2 + ADR-001 + ADR-007.
- **Trabalho:**
  1. Estender o enum `ALU_OP_TYPE_t` (`cpu_package.vhd`) com 8 variantes M
     (`MUL`, `MULH`, `MULHSU`, `MULHU`, `DIV`, `DIVU`, `REM`, `REMU`).
  2. Decodificar `opcode = 0110011` com `funct7 = 0000001` no
     `instruction_decoder.vhd`, condicionado ao generic `RV32M_ENABLE`; com
     `false`, essas instruções continuam inválidas exatamente como hoje.
  3. Novo bloco `mul_div_unit.vhd` (nome fixado por `VHDL_ORDER` de
     `test/rv_build.py`), combinacional, instanciado no estágio EX sob
     `if RV32M_ENABLE generate`, em paralelo com a ALU, com mux na saída.
  4. Divisor restaurador combinacional (32 iterações de subtração e
     deslocamento), sintetizável; multiplicador por produto de 64 bits com
     seleção da metade alta ou baixa e tratamento de sinal por variante.
- **Saída:** design único que elabora nas duas configurações do generic.
- **Gate:** `ghdl -a`, `-e` e `synth` exit 0 nas duas configurações; a suíte de
  RV-2 **continua verde** com `RV32M_ENABLE = true` (não-regressão do RV32I).
- **Requisitos:** FR-RV-12, FR-RV-13, FR-RV-14, FR-RV-16, FR-RV-17, NFR-RV-03.

### RV-4 — Verificação da extensão M
- **Entrada:** design de RV-3 com `RV32M_ENABLE = true`.
- **Trabalho:** testes cocotb dirigidos das 8 instruções contra o modelo de
  referência Python, cobrindo obrigatoriamente: zero, operandos negativos,
  extremos (`0x7FFFFFFF`, `0x80000000`, `0xFFFFFFFF`), **divisão por zero**,
  **overflow de divisão** (`0x80000000 / -1`), a assimetria de sinal do
  `MULHSU` e sequências com dependência entre instruções M e I, para exercitar
  forwarding e stall (FR-RV-22).
- **Saída:** prova por execução de que a extensão M funciona.
- **Gate:** suíte M verde **e** suíte RV32I de RV-2 ainda verde na mesma
  configuração; qualquer falha reporta o **primeiro ciclo divergente** e deixa
  o `.vcd` para triagem no GTKWave; exit code diferente de 0 em falha.
- **Requisitos:** FR-RV-13, FR-RV-14, FR-RV-21, FR-RV-22, FR-RV-23.

### RV-5 — Eficiência (simulação + síntese)
- **Entrada:** os mesmos benchmarks executados nas duas configurações.
- **Trabalho:** contagem de ciclos, instruções retiradas, stalls, flushes e
  instruções RV32M executadas, por observação de sinais reais na simulação;
  área por `ghdl synth --out=verilog` alimentando `yosys stat`, nas duas
  configurações (ADR-005).
- **Saída:** tabela de métricas A/B, cada célula rotulada MEDIDO ou ESTIMADO
  (ver seção 5).
- **Gate:** nenhum número no relatório sem a execução de ferramenta que o
  produziu (NFR-RV-02).
- **Requisitos:** FR-RV-24, FR-RV-25, NFR-RV-02, NFR-RV-03.

### RV-6 — Relatório comparativo
- **Entrada:** todos os artefatos de RV-2 a RV-5.
- **Saída:** relatório em português com: benchmarks usados e sua justificativa
  (FR-RV-18), tabela RV32I vs RV32IM, análise do trade-off ciclos x área x
  caminho crítico, ressalvas metodológicas explícitas (células genéricas do
  Yosys não são µm²; tempo de execução é estimativa) e comandos de reprodução
  incluindo o venv (`~/venv-cocotb`, ADR-006).
- **Gate:** rastreabilidade completa — cada afirmação aponta para o requisito
  FR-RV-xx e para o log de execução correspondente.
- **Requisitos:** FR-RV-18, FR-RV-24, FR-RV-25, NFR-RV-02.

## 3. Como a unidade M entra no pipeline (ADR-007)

**Decisão:** unidade M **combinacional**, latência de 1 ciclo, igual à ALU,
instanciada no estágio EX em paralelo com a ALU e selecionada por mux.

O que torna isso barato é que tanto o caminho de controle quanto o de dados
necessários **já existem**:

- **Caminho de controle.** A seleção da operação viaja de D para E pelo sinal
  `alu_op_type`, que já é porta do `decode_pipeline_register`
  (`alu_op_type_in` / `alu_op_type_out`, do tipo `ALU_OP_TYPE_t`) e chega ao
  estágio EX como `alu_op_type_e`. Estender o **enum** `ALU_OP_TYPE_t` com as
  8 variantes M faz o seletor da unidade M pegar carona nesse mesmo fio:
  nenhuma porta nova em registrador de pipeline, nenhuma largura alterada — o
  tipo enumerado cresce, a interface não muda.
- **Caminho de dados.** Hoje `alu_result_e` é dirigido diretamente pela porta
  `res` da ALU (`CPU.vhd:275`). Passa a ser dirigido por um mux entre `res` da
  ALU e o resultado da unidade M, escolhido pelo próprio `alu_op_type_e`. Como
  `alu_result_e` é exatamente o sinal de onde o forwarding MEM->EX já parte
  (ele vira `alu_result_m` no `execute_pipeline_register`, `CPU.vhd:309`, e
  retorna pelos muxes de operando como `ALU_OP_SRC_ALU_RES`), o resultado de
  uma instrução M é encaminhado pela lógica existente **sem uma linha nova**
  na `hazard_control_unit`.
- **Operandos.** `op1` e `op2` já saem dos muxes de forwarding do EX; a
  unidade M consome exatamente os mesmos sinais.
- **Efeitos colaterais que não ocorrem.** `zero_flag` alimenta a
  `branching_unit`, mas instruções M têm `branch_type = BRANCH_TYPE_NONE`,
  logo o flag é ignorado. `pc_alu` também deriva de `alu_result_e`
  (`CPU.vhd:111`), mas só é usado quando
  `next_pc_sel = PC_NEXT_SRC_PC_ALU_RES` (`JALR`), que nenhuma instrução M
  seleciona.
- **Unidade de hazard.** Intocada. Ela raciocina sobre `rd_sel_e/m/wb`,
  `write_rd_*` e `rd_src_*` — todos idênticos entre uma instrução M e uma
  instrução R-type qualquer. O stall de load-use continua sendo o único stall
  do design.

**Trade-off honesto.** Este design **não tem** latência diferenciada para
MUL/DIV: uma multiplicação ou divisão custa 1 ciclo, como um `ADD`. Logo não
existe stall novo a tratar, e o ganho da extensão M aparece apenas em
**contagem de ciclos do programa** (uma instrução M substitui um laço de
software inteiro), enquanto o custo aparece em **área** e em **caminho
crítico** — um divisor restaurador de 32 iterações combinacionais é um caminho
longo. A área é medida por síntese real (ADR-005); o caminho crítico só entra
no relatório se uma execução real de ferramenta o fornecer. Declarar isso é
obrigatório: o relatório não pode sugerir que MUL e DIV "custam o mesmo" no
silício.

**Trabalho futuro registrado.** A variante multiciclo iterativa (divisor
sequencial de N ciclos, encurtando o caminho crítico ao preço de ciclos) é
deliberadamente adiada. Custo exato, para quem retomar: adicionar uma porta
`stall` ao `decode_pipeline_register` (que hoje só tem `flush`), levar um sinal
de `busy`/`done` da unidade M até a `hazard_control_unit` e estender a lógica
de stall para congelar F/D/E enquanto a unidade M não termina. Nada disso é
necessário na variante combinacional escolhida.

## 4. Contrato do formato `.ram` (ADR-003)

| Item | Regra |
|---|---|
| Granularidade | Uma palavra de 32 bits por linha |
| Codificação | 8 dígitos hexadecimais, **sem** prefixo `0x`, case-insensitive |
| Ordem | Linha de índice 0 = endereço de byte `0x00000000`; linha `n` = endereço `4*n` (ordem crescente de endereço) |
| Semântica do valor | A instrução como palavra de 32 bits — o mesmo valor que a constante VHDL usa. O little-endian do design está na organização de bytes da memória, não na grafia do arquivo |
| Comentários | Linhas vazias e linhas iniciadas por `#` são ignoradas |
| Preenchimento | Palavras não informadas viram `0x00000000` |
| Convenção de parada | Auto-laço `JAL x0, 0` (encoding `0x0000006f`), o mesmo que o `startup.S` original faz no rótulo `spin`. O testbench detecta término pela **visita ao endereço do auto-laço**, e não por PC estacionário — a CPU resolve saltos em EX, então o PC não congela — nem por instrução mágica fora da ISA (FR-RV-03) |
| Consumo | `instruction_memory` com `ROM_INIT_FILE` preenchido lê o arquivo por `textio` na elaboração; vazio (padrão) mantém `INSTRUCTION_MEMORY_CONTENT` |
| Produção | `rvverify/asm.py` (`.asm` -> `.ram`), validado por pytest antes de qualquer uso |

Risco a validar na implementação de RV-1: `ghdl synth` pode rejeitar a função
de leitura de arquivo mesmo com o generic vazio — se ocorrer, isolar a leitura
dentro de um `generate`.

## 5. Como cada métrica de eficiência é obtida

Regra válida para a trilha inteira (NFR-RV-02): **nada é declarado como medido
sem a execução da ferramenta correspondente**. Cada linha da tabela final do
relatório carrega o rótulo abaixo.

| Métrica | Origem | Rótulo |
|---|---|---|
| Ciclos até o término | Contagem de bordas de `clk` na simulação cocotb, do fim do reset até a visita ao endereço do auto-laço | **MEDIDO** |
| Instruções retiradas | Contagem das instruções que chegam ao WB, descontando bolhas, por observação de sinal real na simulação | **MEDIDO** |
| CPI | Ciclos ÷ instruções retiradas — quociente de duas grandezas medidas | **MEDIDO** (derivado) |
| Stalls | Contagem de ciclos com `stall_pc` / `stall_f` ativos, sinais reais da `hazard_control_unit` | **MEDIDO** |
| Flushes | Contagem de ciclos com `flush_f` / `flush_d` ativos | **MEDIDO** |
| Instruções RV32M executadas | Contagem dos ciclos em que `alu_op_type_e` assume uma das 8 variantes M | **MEDIDO** |
| Área (células, wires, bits de memória) | `ghdl synth --std=08 --out=verilog CPU` alimentando `yosys -p "read_verilog; hierarchy -top CPU; stat"`, executado nas duas configurações do generic (ADR-005) | **MEDIDO** |
| Tempo de execução | Ciclos medidos x **período nominal de 10 ns** | **ESTIMADO** — o período atingível não é medido; serve para dar escala, não para comparar frequências |
| Caminho crítico | Só entra no relatório se uma execução real de ferramenta o fornecer; `yosys stat` **não** o produz | **ausente por padrão** |

Ressalva metodológica obrigatória no relatório: `stat` sobre células genéricas
do Yosys mede **complexidade estrutural relativa**, adequada para comparar
RV32I contra RV32IM dentro do mesmo fluxo, e **não** equivale a área em µm² de
um PDK nem a LUTs de um FPGA específico. A comparação só é honesta porque as
duas configurações saem da mesma base de código, trocando um generic
(ADR-001, NFR-RV-03).

## 6. Fase gate da trilha

Mesmo princípio do gate do SpecHDL (`constitution.md`, princípio 1), aplicado à
sequência RV-n. Para avançar de RV-n para RV-n+1:

1. **Critério objetivo.** Todos os itens de gate da fase RV-n listados na
   seção 2 verificados por **execução real** — exit code conferido, log
   guardado. Nunca inferir resultado a partir do código gerado.
2. **Não-regressão.** A partir de RV-2, avançar exige que as suítes das fases
   anteriores continuem verdes na configuração corrente do generic. Uma
   extensão que quebra a baseline não é extensão, é regressão.
3. **Rastreabilidade.** Todo VHDL novo ou alterado carrega `-- REQ: FR-RV-xx`
   e todo teste cocotb carrega `# REQ: FR-RV-xx` antes de o gate fechar.
4. **Checkbox e commit.** Tarefa correspondente marcada em `specs/tasks.md` no
   mesmo commit (Conventional Commits, uma tarefa = um commit).
5. **Aprovação humana explícita.** Testes verdes **não bastam**: ao fechar
   RV-n, parar e aguardar confirmação do usuário antes de iniciar RV-n+1.

Gates de bloqueio duro, que não admitem negociação:

- **RV-1 -> RV-2:** a refatoração de memória só passa com a prova de
  comportamento preservado exigida por FR-RV-07 (alteração em bloco de
  terceiro), incluindo os casos de acesso desalinhado.
- **RV-2 -> RV-3:** sem baseline RV32I verde e medida, **nenhuma linha da
  extensão M** (FR-RV-11). Comparar contra uma baseline não verificada
  invalidaria o resultado inteiro da trilha.
- **RV-5 -> RV-6:** nenhuma métrica entra no relatório sem o log da execução
  que a produziu, e toda estimativa entra rotulada como estimativa
  (NFR-RV-02).

## 7. Validador de entregas pelo terminal (RV-7)

Requisitos: FR-RV-26 a FR-RV-35, NFR-RV-04. Decisões: ADR-011 (log do GHDL por
caso e eventos JSON Lines), ADR-012 (sem interface gráfica), ADR-013 (estrutura
do repositório).

### 7.1 A forma do projeto

```
rvverify/          O VALIDADOR. Julga qualquer CPU descrita por um cpu.toml.
cpus/              CPUs de referência, que passam na suíte.
entregas/          Onde entra a CPU do aluno ou do modelo de IA.
specs/  docs/      Spec, plano, decisões, tarefas e relatórios.
legado/            Trilha A (SpecHDL genérico), preservada e fora do caminho.
```

Um comando faz tudo:

```
python -m rvverify                  valida tudo o que está em entregas/
python -m rvverify cpus/            valida as CPUs de referência
python -m rvverify entregas/joao    valida uma entrega
```

### 7.2 Como um caso roda

```
cpu.toml ──► manifest.py ──► builder.py ──► ghdl -a/-e   (uma vez por árvore)
                                   │
conformance.py ── programa .asm ──►│
   (esperado vem de reference.py)  ▼
                             ghdl -r + cocotb ──► report.json de cada caso
                                   │                     │
                             sim.log do caso        feedback.py ──► diagnóstico
```

Um caso reprovado nunca vira exceção solta: vira um `CaseResult` com
diagnóstico estruturado. O GHDL escreve no `sim.log` do caso; a tela recebe
uma linha por caso (FR-RV-30).

### 7.3 Saída do terminal

Três blocos, sempre na mesma ordem:

1. **cabeçalho** — CPU, manifesto, o que vai rodar e quanto deve demorar;
2. **progresso** — uma linha por caso, no instante em que ele termina;
3. **relatório** — veredito, placar por etapa, requisitos atendidos e
   pendentes pelo título, métricas observadas, diagnóstico de cada reprovação
   e o comando que repete só o que falhou.

Nada de saída do GHDL na tela: ela vive no `sim.log` de cada caso, cujo
caminho aparece no diagnóstico. `--eventos` troca o relatório humano por JSON
Lines, para CI e para avaliar modelos de IA em lote.

### 7.4 Rigor da suíte (FR-RV-34, FR-RV-35)

O ponto do projeto é medir se um aluno ou um modelo de IA consegue construir a
CPU. Uma suíte complacente destrói essa medida: aprovar uma CPU quebrada é pior
do que não medir. Por isso:

- a cobertura mínima por etapa está escrita em FR-RV-34 e é conferida por um
  teste que compara o catálogo da suíte com essa lista — instrução nova na
  lista sem caso correspondente quebra o teste;
- o rigor é provado por **mutação** (FR-RV-35): uma lista versionada de
  defeitos é aplicada a uma cópia de uma CPU de referência, e a suíte precisa
  reprovar cada um, nomeando o caso que o pegou. Mutação que passa é lacuna da
  suíte, e vira caso novo.

### 7.5 Tarefas

Fase RV-7 de `tasks.md`. O gate da fase é: as duas CPUs de referência
aprovadas, toda mutação da lista reprovada, e o relatório de terminal revisado
com o professor.

## 8. Análise de viabilidade FPGA via Quartus (RV-8)

Requisitos: FR-RV-36 a FR-RV-42, NFR-RV-06. Decisão: ADR-015. Plano de
implementação detalhado, mantido à parte por ser específico de ferramenta de
terceiro: `docker/quartus-docker-fpga-analysis-plan.md`.

### 8.1 Onde isso entra no fluxo

RV-8 roda **depois** de RV-7 fechar para a CPU em questão — ou seja, depois
que `python -m rvverify entregas/<nome>` já deu veredito (FR-RV-27) —, nunca
antes e nunca no lugar. É uma etapa **aditiva e opcional**: mede se a CPU
*que já passou* na suíte comportamental também cabe, atinge o clock alvo e
tem potência estimada razoável num FPGA real. Uma CPU que reprova RV-7 não
ganha nada rodando RV-8 — o contrato de comportamento não foi provado, então
uma síntese "bonita" não significa nada. `NFR-RV-06` fixa isso: a ausência da
imagem do Quartus nunca pula nem reprova a suíte de conformidade em si,
exatamente como `NFR-RV-05` já faz para o oráculo do montador.

```
entregas/<nome>/cpu.toml ──► rvverify (RV-7) ──► veredito
                                                     │
                                        (opcional, se aprovado/parcial)
                                                     ▼
                                    docker run quartus-analyzer analyze
                                                     │
                              synth ──► fit ──► timing ──► power
                                                     │
                                                     ▼
                                    quartus_output/reports/summary.json
```

### 8.2 Por que uma imagem Docker separada, e por quê ela não builda sozinha

`docker/Quartus_Dockerfile` nunca compartilha base nem se funde com
`docker/Dockerfile` (o oráculo do montador, NFR-RV-05) — decisão fixada em
ADR-015, por pedido explícito e porque as duas têm ciclo de vida e peso
completamente diferentes (o oráculo é ~200 MB e roda em toda execução de
`pytest rvverify/tests`; o Quartus Prime Lite sozinho passa de 2 GB e só
interessa a quem pediu análise de FPGA).

A imagem também **não baixa nada sozinha**: o CDN de download da Altera
exige uma sessão de navegador de verdade (mitigação de bot da Akamai mais o
aceite de licença na própria página), e isso bloqueia igualmente um `curl`
manual e um `RUN curl` dentro de `docker build` — verificado por execução
real em 2026-09-18 (ADR-015). Por isso o Dockerfile espera o instalador e os
`.qdz` já em `docker/quartus_installers/` (pasta local, fora do Git), com o
passo a passo do download manual documentado no `README.md` daquela pasta e
no cabeçalho do próprio Dockerfile.

### 8.3 O que o wrapper `analyze` faz

Descrito em detalhe em `docker/quartus-docker-fpga-analysis-plan.md`; em
resumo, dado um projeto Quartus (`.qpf`) e o device alvo, a sequência é
síntese → fitter → TimeQuest → Power Analyzer → coleta de relatórios →
`summary.json`, preservando o `.sof` só quando a compilação termina bem
(FR-RV-41). Cada saída tem seu requisito próprio: cabe no device (FR-RV-37),
timing/Fmax condicionado a `.sdc` de verdade (FR-RV-38, nunca um Fmax "de
graça" sem restrição), potência sempre rotulada estimativa (FR-RV-39,
paralelo direto à regra de MEDIDO/ESTIMADO de NFR-RV-02 e da seção 5), e
netlist/RTL preservado mesmo se a exportação gráfica não for viável
(FR-RV-40).

### 8.4 Estado (atualizado após implementação)

O usuário completou o download manual (seção 8.2) e pediu explicitamente
pra prosseguir com RV-8 antes de RV-7 fechar — decisão dele, registrada
aqui porque diverge do gate padrão da seção 6 (normalmente RV-n só começa
depois de RV-(n-1) fechar). `TRV-8.1` a `TRV-8.7` estão implementadas e
verificadas por execução real contra a imagem de verdade
(`docker/quartus_analyzer/analyze.py` + `entrypoint.sh`, detalhe em
`specs/tasks.md`): device corrigido (ADR-016), smoke test compilando,
timing/Fmax/potência extraídos com número real, e o wrapper `analyze`
rodando síntese→fit→timing→potência→`summary.json` de ponta a ponta, com
caminho de falha testado de verdade (projeto inexistente -> exit 1, nada
inventado). Falta só `TRV-8.8`: rodar contra `cpus/rv32i_pipeline` de
verdade (não mais o `counter4` de fumaça) — isso ainda depende de RV-7
fechado, porque não faz sentido medir FPGA de uma CPU cujo comportamento
não foi provado (mesma lógica da seção 8.1).
