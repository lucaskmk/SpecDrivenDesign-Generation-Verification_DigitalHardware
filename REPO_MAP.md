# Mapa do repositório

Onde cada coisa vive e por quê. A estrutura foi decidida na
[ADR-013](specs/decisions.md) e concluída nas tarefas `TRV-7.7.x` de
[`specs/tasks.md`](specs/tasks.md); a [ADR-014](specs/decisions.md) registra o
que foi de fato movido.

> **Mantenha este arquivo atualizado.** Qualquer reorganização futura de pastas
> deve editar este mapa no mesmo commit. Foi exatamente a falta disso que
> deixou meia dúzia de caminhos quebrados espalhados pelo repositório depois da
> primeira metade da ADR-013.

## As pastas de topo

As cinco da ADR-013, mais `rvgen/` (ADR-018) e `experimentos/` (ADR-019).

| pasta | o que é | leia primeiro |
|---|---|---|
| [`rvverify/`](rvverify/) | **O validador.** Manifesto (`cpu.toml`), montador, modelo de referência, harness cocotb, suíte de conformidade e diagnóstico. É o que julga uma CPU entregue. Roda por `python -m rvverify`. | [`README.md`](README.md) |
| [`rvgen/`](rvgen/) | **O gerador** (RV-9, ADR-018). Agente de fases fixas que escreve uma entrega com IA local (Ollama) ou externa (OpenRouter) e a submete ao `rvverify`, corrigindo pelo diagnóstico. Cliente do validador, nunca o contrário (NFR-RV-07). Roda por `python -m rvgen`. | [`rvgen/README.md`](rvgen/README.md) (uso e modelo dos prompts), [`specs/plan.md`](specs/plan.md) seção 9 |
| [`cpus/rv32i_pipeline/`](cpus/rv32i_pipeline/) | **A CPU de referência de 5 estágios** — o ponto de partida de quem vai modificar uma CPU. Traz `src/` (RTL), `test/` (suítes próprias), `tools/`, `programs/` (benchmarks `.asm`/`.ram`) e `compilation/`. | [`cpus/rv32i_pipeline/README.md`](cpus/rv32i_pipeline/README.md), [`RELATORIO.md`](cpus/rv32i_pipeline/RELATORIO.md) |
| [`cpus/rv32i_monociclo/`](cpus/rv32i_monociclo/) | **A CPU monociclo.** Existe como prova de que a suíte julga comportamento e não formato: outra microarquitetura, mesmo contrato, mesma suíte. | [`cpus/rv32i_monociclo/README.md`](cpus/rv32i_monociclo/README.md) |
| [`entregas/`](entregas/) | **Onde a CPU avaliada entra.** Copie `_modelo/` para `entregas/<seu_nome>/`, preencha o `cpu.toml` e ponha o VHDL em `src/`. | [`entregas/README.md`](entregas/README.md) |
| [`experimentos/`](experimentos/) | **CPUs geradas por IA** (ADR-019), uma pasta por geração do `rvgen`, com o VHDL, o manifesto e as sessões (contrato, prompts, respostas, relatórios, resultado). Versionada como registro de experimento, fora de `entregas/`. `python -m rvgen comparar` as põe lado a lado. | [`experimentos/README.md`](experimentos/README.md) |
| [`legado/`](legado/) | **A trilha A inteira, congelada.** O pipeline SpecHDL com formulário Streamlit (`src/spechdl/`, `templates/`, `scripts/`, `.streamlit/`, `abrir_formulario.bat`), mais os exercícios de ULA e o smoke test de toolchain. Preservada pelo princípio 8, fora do caminho. | [`docs/ESTADO-TRILHA-A.md`](docs/ESTADO-TRILHA-A.md) |

O montador (`rvverify/asm.py`) e o modelo de referência
(`rvverify/reference.py`) vivem no **validador**, não na CPU de exemplo: são
infraestrutura de quem julga, e deixá-los em `cpus/` invertia a direção da
dependência.

## O resto da raiz

| caminho | o que é |
|---|---|
| [`docker/pl-descomp-cocotb/`](docker/pl-descomp-cocotb/Dockerfile) | **Imagem `pl-descomp-cocotb`: espelho, sem modificação, da imagem de referência da disciplina** (GHDL + cocotb), no mesmo digest em que a `spechdl-toolchain` a pina. Só `FROM`. Existe para o build da de baixo continuar reprodutível se a original sumir. Índice das três imagens e das tags publicadas no Docker Hub: [`docker/README.md`](docker/README.md). |
| [`docker/spechdl-toolchain/`](docker/spechdl-toolchain/Dockerfile) | **Imagem `spechdl-toolchain`: oráculo opcional do montador** (NFR-RV-05). GHDL + cocotb + binutils RISC-V real + Yosys. Serve para conferir palavra a palavra a saída de `rvverify/asm.py` contra um assemblador de verdade, em [`rvverify/tests/test_assembler_oracle.py`](rvverify/tests/test_assembler_oracle.py). **Sem ela a suíte roda igual** — a conferência é pulada, nunca reprovada. Build: `docker build -t spechdl-toolchain docker/spechdl-toolchain`. |
| [`docker/quartus-lite/`](docker/quartus-lite/Dockerfile) | **Imagem `quartus-lite:25.1`: Quartus Prime Lite para a análise de FPGA da RV-8** (NFR-RV-06, ADR-015). **Permanentemente separada** da imagem acima — nunca compartilha `FROM`, nunca vira um único Dockerfile; ausência dela nunca afeta `rvverify`. Junto do `Dockerfile` ficam o wrapper `analyze` ([`quartus_analyzer/`](docker/quartus-lite/quartus_analyzer/analyze.py)), o projeto de fumaça ([`quartus_smoketest/`](docker/quartus-lite/quartus_smoketest/README.md)) e o plano de implementação. Não baixa nada sozinha (CDN da Altera exige sessão de navegador): instalador e `.qdz` vão manualmente em [`quartus_installers/`](docker/quartus-lite/quartus_installers/README.md), fora do Git. Build: `docker build -t quartus-lite:25.1 docker/quartus-lite`. |
| [`implemetation_tests/`](implemetation_tests/) | **Saídas do pipeline, não o pipeline.** CPUs geradas pelas fases 1–5 da metodologia e depois submetidas ao mesmo `rvverify` que julga as de `cpus/`. Hoje só [`opus_5_RISCVIM/`](implemetation_tests/opus_5_RISCVIM/) (RV32IM monociclo, aprovada 35/35). A subpasta [`fpga/`](implemetation_tests/opus_5_RISCVIM/fpga/) traz o projeto Quartus da fase 5b — a análise de FPGA real da RV-8 aplicada a essa CPU (TRV-8.9). |
| [`specs/`](specs/) | `constitution.md` (princípios), `spec.md` (requisitos EARS), `plan.md` (arquitetura), `tasks.md` (backlog), `decisions.md` (ADRs). |
| [`docs/`](docs/) | `MUDANCAS.md` e `mudancas-riscv.html` (o que a trilha RISC-V mudou), `ESTADO-TRILHA-A.md`, `mapa-do-projeto.html` e `archive/`. |
| [`README.md`](README.md), [`PROMPT_RISCV.md`](PROMPT_RISCV.md) | porta de entrada e enunciado para modelos de IA. (O `CLAUDE.md`, que descrevia a trilha A, foi removido em 2026-09-30.) |
| [`pyproject.toml`](pyproject.toml) | só a configuração do pytest: `testpaths = ["rvverify/tests", "cpus"]`. `legado/` fica de fora de propósito — a trilha A não tem nenhum teste. |

## Notas

- **`docker/` tem uma pasta por imagem**, com o nome da imagem, e cada pasta é
  o build context da sua imagem (ADR-017). Uma imagem nova ganha uma pasta
  nova e uma linha em [`docker/README.md`](docker/README.md), que diz qual tag
  do Docker Hub cada pasta produz; nenhum Dockerfile fica solto na raiz de
  `docker/`.
- **`examples/` não existe mais.** A pasta misturava exercícios da trilha A com
  as CPUs de referência RISC-V, e o nome `RISCV32I` não sinalizava que aquele
  era o alvo editável. O conteúdo foi para `cpus/` e `legado/`, sempre por
  `git mv` — `git log --follow` continua seguindo cada arquivo.
- **`legado/` está congelado**, não morto. Não tem nenhum teste automatizado
  (ver [`docs/ESTADO-TRILHA-A.md`](docs/ESTADO-TRILHA-A.md)), então uma
  mudança ali não é verificável pela suíte. `legado/abrir_formulario.bat`
  passou a assumir um `.venv` dentro de `legado/`, não mais na raiz.
- **[`docs/mapa-do-projeto.html`](docs/mapa-do-projeto.html) é um mapa visual
  mais antigo e mais restrito**: cobre só as fases 0–7 da trilha A e não
  menciona RISC-V. Ficou como está por decisão explícita. Este arquivo, e não
  aquele, é o mapa atual do repositório.
- **Decisões relacionadas**, em [`specs/decisions.md`](specs/decisions.md):
  **ADR-004** (montador próprio em Python, e sua *Revisão* sobre o oráculo),
  **ADR-013** (esta estrutura), **ADR-014** (a conclusão dela e a adoção do
  oráculo) e **ADR-015** (a imagem do Quartus, separada para sempre da do
  oráculo, e por que ela não baixa nada sozinha) e **ADR-017** (uma pasta por
  imagem em `docker/`).
