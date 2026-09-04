# SpecHDL — instruções para o Claude Code

## O que é este projeto
SpecHDL é um pipeline spec-driven que parte de um formulário web local
(Streamlit, `spechdl web`) — o aluno responde perguntas true/false e campos
técnicos (presença de cache, número de estágios de pipeline, largura de
palavra etc.), não um enunciado em texto livre —, extrai requisitos
estruturados, decompõe em blocos de hardware (ULA, banco de registradores,
unidade de controle, muxes etc.), gera VHDL + testbenches, verifica no GHDL
e produz um relatório de trade-offs de potência/velocidade/área (PPA). Ao
submeter o formulário, o app grava `rubrica.md` (versionável) e o pipeline
roda sozinho até o relatório final, sem pedir mais nenhuma decisão do aluno
— preencher e submeter o formulário é a única responsabilidade dele.

Quando o design alvo é um **processador RISC-V**, o pipeline gera uma CPU
nova e customizada (RV32I base + as extensões escolhidas na rubrica), usando
`examples/RISCV32I/` como referência de arquitetura — não como código a
copiar. Nesse caso entram duas fases a mais, 3b e 4b, e a CPU só é
considerada verificada depois de **executar software de verdade**: assembly
→ código de máquina (`.rm`) → ROM → simulação cocotb/GHDL → comparação do
estado final da RAM com o esperado. Ver `specs/spec.md`, fases 3b/4b.

Este projeto está sendo construído seguindo a própria metodologia que ele
implementa: nada de código antes de spec aprovada. Antes de implementar
qualquer coisa, leia, nesta ordem:

1. `specs/constitution.md` — princípios inegociáveis
2. `specs/spec.md` — requisitos funcionais e não-funcionais (formato EARS)
3. `specs/plan.md` — arquitetura técnica e decisões de stack
4. `specs/tasks.md` — backlog de tarefas atômicas, em ordem

## Regras de comportamento
- Não pule fases. Cada fase do pipeline (ver `specs/plan.md`) só é
  considerada concluída quando os critérios de aceite da tarefa
  correspondente em `specs/tasks.md` passam.
- Se o enunciado real da disciplina divergir do que está em `specs/spec.md`,
  pare e atualize `specs/spec.md` antes de mexer em código — não improvise
  em cima de uma spec desatualizada.
- Nunca declare uma simulação como "passou" sem ter rodado o GHDL de fato
  (via cocotb) e checado o exit code/saída. Não infira resultado de teste a
  partir do código gerado.
- Cada arquivo VHDL gerado deve referenciar o ID do requisito da spec que
  implementa (comentário `-- REQ: FR-xx`); cada testbench cocotb gerado faz
  o mesmo em Python (comentário `# REQ: FR-xx`).
- Uma tarefa = um commit, seguindo Conventional Commits.
- Se uma tarefa parecer ambígua ou maior que meio dia de trabalho, pare e
  proponha quebrá-la em subtarefas menores, atualizando `specs/tasks.md` —
  não tente resolver tudo de uma vez num commit gigante.
- Ao concluir uma tarefa, marque o checkbox correspondente em
  `specs/tasks.md` no mesmo commit.
- Ao terminar todas as tarefas de uma fase, pare e peça confirmação
  explícita do usuário antes de iniciar a fase seguinte — testes
  automatizados passando não bastam pra avançar (ver `specs/plan.md`, fase
  gate).

### Regras específicas de CPU RISC-V (fases 3b/4b)
- Bloco verificado isoladamente **não** fecha uma CPU. Ela só está verificada
  depois de rodar o programa de teste e a RAM final bater com o esperado
  (princípio 8). Não anuncie a CPU como pronta antes disso.
- O teste obrigatório do RV32I base (`examples/riscv_base_test/`) é fixture
  golden: você **não** escreve, edita, regrava nem "atualiza" o
  `expected_ram.json` dele. Se ele falha, o bug é da CPU gerada — conserte o
  VHDL, não o esperado (princípio 9).
- Estado de RAM esperado é derivado da semântica do assembly que você
  escreveu, e gravado **antes** de rodar a simulação. Nunca rode primeiro pra
  depois anotar o que saiu como "esperado" — isso é tautologia, não teste.
- Toda instrução declarada como implementada tem que ser exercitada. Cobertura
  é medida pelo que a CPU **aposentou** durante a simulação (`dbg_valid` +
  `dbg_instr`), não pela presença do mnemônico no fonte assembly — código
  morto ou instrução descartada em flush não conta (princípio 10).
- Cada extensão (padrão ou custom) entra com o seu próprio programa de teste,
  cobrindo todas as instruções que ela adiciona, com `-march` derivado das
  extensões declaradas no `spec.json`.
- Programa de teste é escrito **direto em assembly** (`.S`), não em C — com C
  quem escolhe as instruções emitidas é o compilador, e aí não há como
  garantir cobertura instrução por instrução (ver `specs/plan.md`, fase
  3b/4b). O `.rm` e o disassembly, ao contrário, são sempre derivados por
  ferramenta: nunca escreva código de máquina à mão.
- `examples/RISCV32I/` é referência de **arquitetura**, não código pra copiar:
  é uma CPU de terceiro, não foi gerada por este pipeline, não tem `-- REQ:`
  e não tem testbench cocotb. Gere uma CPU nova conforme a rubrica.
- A CPU gerada precisa expor a interface de verificação padrão (`clk`, `rst`,
  `dbg_pc`, `dbg_instr`, `dbg_valid` e a RAM como `signal` acessível) — sem
  ela o teste obrigatório não tem onde se acoplar (ver `specs/plan.md`).

## Stack
- Python 3.11+, gerenciado com uv (ou venv)
- Streamlit (`pip install streamlit`, `spechdl web`) para o formulário web
  local da fase 1 — único ponto de entrada do pipeline (rubrica interativa:
  true/false + campos técnicos), ver `specs/plan.md`, fase 1
- OpenRouter (`pip install openrouter`, SDK nativo) para extração de spec,
  decomposição arquitetural e geração de VHDL — acesso unificado a múltiplos
  modelos por trás de uma única API; usar variável de ambiente
  `OPENROUTER_API_KEY`, nunca hardcode a chave. Modelo default configurável
  via `SPECHDL_LLM_MODEL`, não fixo no código (ver `specs/plan.md`)
- GHDL para compilação/simulação VHDL (`apt install ghdl` em WSL2/Linux)
- cocotb (`pip install cocotb`) para os testbenches gerados — testbench
  escrito em Python, dirigindo o DUT VHDL através do GHDL como simulador
  (fluxo `make SIM=ghdl`; ver `specs/plan.md`, fase 3/4). Ambiente de
  referência: imagem Docker `rafaelcorsi/pl-descomp-cocotb`, usada também no
  smoke test de `examples/toolchain_smoketest/`
- GTKWave para inspeção visual do waveform (`.vcd`) na triagem manual de
  falha (ver `specs/plan.md`, fase 3/4)
- Yosys + ghdl-yosys-plugin para a análise PPA (ver `specs/plan.md`, fase 5)
- Binutils cruzado RISC-V (`riscv64-unknown-elf-as/ld/objcopy/objdump`) para
  montar os programas de teste de CPU da fase 3b (assembly → ELF → binário →
  `.rm`). Vem dentro da imagem `docker/Dockerfile` do projeto, junto com GHDL
  e cocotb — não instale nem referencie toolchain por caminho local da
  máquina (NFR-05)
- pytest para os testes do próprio pipeline Python — diferente dos
  testbenches cocotb gerados: pytest testa o pipeline, cocotb testa o
  hardware gerado

## Idioma
- Documentação e specs: português (é a língua do enunciado original e da
  apresentação pro professor)
- Código, nomes de variáveis, comentários dentro do VHDL: inglês (convenção
  padrão de HDL e de portfólio técnico)

## O que NÃO fazer
- Não gerar VHDL "genérico de exemplo" fora do que a spec pede
- Não pular a etapa de decomposição arquitetural e ir direto pra geração de
  código
- Não pedir decisão de arquitetura ao aluno fora da rubrica — depois da
  submissão, o pipeline decide e gera sozinho, sem checkpoint humano no meio
  (NFR-01)
- Não tentar extrair requisitos de texto livre — a entrada é sempre o
  formulário web estruturado (schema documentado em `templates/rubrica.md`)
- Não estimar métricas de PPA "no chute" — usar a saída real do
  Yosys/ghdl-yosys-plugin (fase 5); se não for viável no prazo, marcar
  claramente como heurística no relatório, nunca como medição
- Não dar uma CPU por verificada com base em testbench de bloco, em
  inspeção do VHDL gerado ou em simulação que você não rodou de fato
  (princípio 8)
- Não editar golden file pra teste passar, nem derivar estado esperado da
  saída da simulação (princípio 9)
- Não declarar uma instrução como implementada sem um programa de teste que a
  execute de verdade (princípio 10)
- Não escrever `.rm` nem disassembly à mão — são sempre derivados do ELF por
  ferramenta
- Não copiar o VHDL de `examples/RISCV32I/` como se fosse saída do pipeline —
  é referência de arquitetura de terceiro, sem rastreabilidade `-- REQ:`
