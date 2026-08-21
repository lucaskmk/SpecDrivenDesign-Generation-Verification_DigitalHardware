# SpecHDL — instruções para o Claude Code

## O que é este projeto
SpecHDL é um pipeline spec-driven que parte de um documento de especificação
(enunciado de exercício de arquitetura de computadores/descomp), extrai
requisitos estruturados, decompõe em blocos de hardware (ULA, banco de
registradores, unidade de controle, muxes etc.), gera VHDL + testbenches,
verifica no GHDL e produz um relatório de trade-offs de potência/velocidade/
área (PPA).

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

## Stack
- Python 3.11+, gerenciado com uv (ou venv)
- Anthropic SDK (`pip install anthropic`) para extração de spec, decomposição
  arquitetural e geração de VHDL — usar variável de ambiente
  `ANTHROPIC_API_KEY`, nunca hardcode a chave
- GHDL para compilação/simulação VHDL (`apt install ghdl` em WSL2/Linux)
- cocotb (`pip install cocotb`) para os testbenches gerados — testbench
  escrito em Python, dirigindo o DUT VHDL através do GHDL como simulador
  (fluxo `make SIM=ghdl`; ver `specs/plan.md`, fase 3/4). Ambiente de
  referência: imagem Docker `rafaelcorsi/pl-descomp-cocotb`, usada também no
  smoke test de `examples/toolchain_smoketest/`
- GTKWave para inspeção visual do waveform (`.vcd`) na triagem manual de
  falha (ver `specs/plan.md`, fase 3/4)
- Yosys + ghdl-yosys-plugin para a análise PPA (ver `specs/plan.md`, fase 5)
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
- Não estimar métricas de PPA "no chute" — usar a saída real do
  Yosys/ghdl-yosys-plugin (fase 5); se não for viável no prazo, marcar
  claramente como heurística no relatório, nunca como medição
