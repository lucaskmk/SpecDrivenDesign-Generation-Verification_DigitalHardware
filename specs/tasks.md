# Backlog de tarefas — SpecHDL

Convenção: uma tarefa = um commit. Não iniciar tarefa da fase N+1 antes de
todas as tarefas da fase N estarem concluídas (ver `plan.md`, fase gate).

## Fase 0 — Setup
- [ ] T0.1 — Criar estrutura de pastas (ver `plan.md`) e ambiente virtual Python
- [ ] T0.2 — Instalar e validar GHDL (`ghdl --version`) e cocotb
  (`pip install cocotb`) no WSL2/Linux; validar o par rodando
  `make -C examples/toolchain_smoketest/test/` e conferindo que o teste do
  demux passa (smoke test do toolchain antes de gerar qualquer bloco real)
- [ ] T0.3 — Instalar e validar Yosys + ghdl-yosys-plugin
- [ ] T0.4 — Configurar `ANTHROPIC_API_KEY` via variável de ambiente, testar chamada mínima ao SDK
- [ ] T0.5 — Criar exemplo fixo em `examples/alu_4bit/` (enunciado de teste) para usar como fixture nas fases seguintes

## Fase 1 — Ingestão e extração de spec (FR-01, FR-02, FR-03)
- [ ] T1.1 — Parser de documento (PDF/docx/txt) → texto bruto
- [ ] T1.2 — Prompt estruturado de extração EARS + parsing da resposta em `spec.json`
- [ ] T1.3 — Sinalização de requisito incompleto/ambíguo (FR-02)
- [ ] T1.4 — Teste pytest: rodar fase 1 contra `examples/alu_4bit/` e validar `spec.json` gerado

## Fase 2 — Decomposição arquitetural (FR-04, FR-05, FR-06)
- [ ] T2.1 — Prompt de decomposição em blocos a partir de `spec.json` → `architecture.json`
- [ ] T2.2 — Justificativa de cada decisão arquitetural amarrada a um NFR (FR-05)
- [ ] T2.3 — Suporte a múltiplas alternativas arquiteturais quando aplicável (FR-06)
- [ ] T2.4 — Teste pytest: validar `architecture.json` contra o exemplo fixo

## Fase 3 — Geração de VHDL + testbench (FR-07, FR-08)
- [ ] T3.1 — Geração de VHDL por bloco, com comentário de rastreabilidade (FR-08)
- [ ] T3.2 — Geração de testbench cocotb (Python) por bloco, derivado da
  mesma spec, incluindo o Makefile (`TOPLEVEL_LANG=vhdl`, `SIM=ghdl`) no
  padrão de `examples/toolchain_smoketest/`
- [ ] T3.3 — Teste pytest: validar sintaxe VHDL gerada (parse básico) do
  DUT, sem rodar GHDL ainda
- [ ] T3.4 — Teste pytest: validar o testbench cocotb gerado (import do
  módulo + parse via `ast`, sem depender do GHDL ainda)

## Fase 4 — Verificação (FR-09, FR-10, FR-11)
- [ ] T4.1 — Wrapper Python que roda `make -C outputs/<bloco>/test/`
  (cocotb + GHDL) para compilar + simular um bloco, capturando exit code e log
- [ ] T4.2 — Mapeamento de falha de simulação → requisito não atendido (FR-10)
- [ ] T4.3 — Integração top-level: simular todos os blocos juntos (FR-11)
- [ ] T4.4 — Teste pytest: rodar fase 4 fim a fim no exemplo fixo e checar reprodutibilidade

## Fase 5 — Análise PPA (FR-12, FR-13)
- [ ] T5.1 — Wrapper Yosys + ghdl-yosys-plugin para síntese e `stat` (contagem de células/área)
- [ ] T5.2 — Fallback heurístico caso a síntese não seja viável, marcado explicitamente como estimativa (FR-13)
- [ ] T5.3 — Teste pytest: validar campo `ppa` no `block_result.json` do exemplo fixo

## Fase 6 — Relatório (FR-14)
- [ ] T6.1 — Agregador que percorre `spec.json` → `architecture.json` → `block_result.json` de cada bloco e monta a cadeia de rastreabilidade
- [ ] T6.2 — Geração do relatório final em Markdown (opcionalmente exportável para PDF)
- [ ] T6.3 — Teste pytest: gerar relatório completo do exemplo fixo e validar que todos os FR/NFR aparecem rastreados

## Fase 7 — CLI e reprodutibilidade (NFR-01, NFR-02)
- [ ] T7.1 — Comando único `spechdl run <documento>` rodando as 6 fases em sequência
- [ ] T7.2 — Flag para rodar uma fase isolada reaproveitando artefatos anteriores (NFR-02)
- [ ] T7.3 — README com instruções de uso, incluindo setup de GHDL/Yosys
