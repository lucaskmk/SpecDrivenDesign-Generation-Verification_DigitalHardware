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
