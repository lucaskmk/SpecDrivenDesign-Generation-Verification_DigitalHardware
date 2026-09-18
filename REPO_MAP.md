# Mapa do repositório

Onde cada coisa vive e por quê. A estrutura foi decidida na
[ADR-013](specs/decisions.md) e concluída nas tarefas `TRV-7.7.x` de
[`specs/tasks.md`](specs/tasks.md); a [ADR-014](specs/decisions.md) registra o
que foi de fato movido.

> **Mantenha este arquivo atualizado.** Qualquer reorganização futura de pastas
> deve editar este mapa no mesmo commit. Foi exatamente a falta disso que
> deixou meia dúzia de caminhos quebrados espalhados pelo repositório depois da
> primeira metade da ADR-013.

## As cinco pastas de topo

| pasta | o que é | leia primeiro |
|---|---|---|
| [`rvverify/`](rvverify/) | **O validador.** Manifesto (`cpu.toml`), montador, modelo de referência, harness cocotb, suíte de conformidade e diagnóstico. É o que julga uma CPU entregue. Roda por `python -m rvverify`. | [`README.md`](README.md) |
| [`cpus/rv32i_pipeline/`](cpus/rv32i_pipeline/) | **A CPU de referência de 5 estágios** — o ponto de partida de quem vai modificar uma CPU. Traz `src/` (RTL), `test/` (suítes próprias), `tools/`, `programs/` (benchmarks `.asm`/`.ram`) e `compilation/`. | [`cpus/rv32i_pipeline/README.md`](cpus/rv32i_pipeline/README.md), [`RELATORIO.md`](cpus/rv32i_pipeline/RELATORIO.md) |
| [`cpus/rv32i_monociclo/`](cpus/rv32i_monociclo/) | **A CPU monociclo.** Existe como prova de que a suíte julga comportamento e não formato: outra microarquitetura, mesmo contrato, mesma suíte. | [`cpus/rv32i_monociclo/README.md`](cpus/rv32i_monociclo/README.md) |
| [`entregas/`](entregas/) | **Onde a CPU avaliada entra.** Copie `_modelo/` para `entregas/<seu_nome>/`, preencha o `cpu.toml` e ponha o VHDL em `src/`. | [`entregas/README.md`](entregas/README.md) |
| [`legado/`](legado/) | **A trilha A inteira, congelada.** O pipeline SpecHDL com formulário Streamlit (`src/spechdl/`, `templates/`, `scripts/`, `.streamlit/`, `abrir_formulario.bat`), mais os exercícios de ULA e o smoke test de toolchain. Preservada pelo princípio 8, fora do caminho. | [`docs/ESTADO-TRILHA-A.md`](docs/ESTADO-TRILHA-A.md) |

O montador (`rvverify/asm.py`) e o modelo de referência
(`rvverify/reference.py`) vivem no **validador**, não na CPU de exemplo: são
infraestrutura de quem julga, e deixá-los em `cpus/` invertia a direção da
dependência.

## O resto da raiz

| caminho | o que é |
|---|---|
| [`docker/Dockerfile`](docker/Dockerfile) | **Oráculo opcional do montador** (NFR-RV-05). Imagem com GHDL + cocotb + binutils RISC-V real + Yosys. Serve para conferir palavra a palavra a saída de `rvverify/asm.py` contra um assemblador de verdade, em [`rvverify/tests/test_assembler_oracle.py`](rvverify/tests/test_assembler_oracle.py). **Sem ela a suíte roda igual** — a conferência é pulada, nunca reprovada. |
| [`docker/Quartus_Dockerfile`](docker/Quartus_Dockerfile) | **Imagem do Quartus Prime Lite para a análise de FPGA da RV-8** (NFR-RV-06, ADR-015). **Permanentemente separada** da imagem acima — nunca compartilha `FROM`, nunca vira um único Dockerfile; ausência dela nunca afeta `rvverify`. Não baixa nada sozinha (CDN da Altera exige sessão de navegador): instalador e `.qdz` vão manualmente em [`docker/quartus_installers/`](docker/quartus_installers/README.md), fora do Git. |
| [`specs/`](specs/) | `constitution.md` (princípios), `spec.md` (requisitos EARS), `plan.md` (arquitetura), `tasks.md` (backlog), `decisions.md` (ADRs). |
| [`docs/`](docs/) | `MUDANCAS.md` e `mudancas-riscv.html` (o que a trilha RISC-V mudou), `ESTADO-TRILHA-A.md`, `mapa-do-projeto.html` e `archive/`. |
| [`README.md`](README.md), [`PROMPT_RISCV.md`](PROMPT_RISCV.md), [`CLAUDE.md`](CLAUDE.md) | porta de entrada, enunciado para modelos de IA, instruções para o Claude Code. |
| [`pyproject.toml`](pyproject.toml) | só a configuração do pytest: `testpaths = ["rvverify/tests", "cpus"]`. `legado/` fica de fora de propósito — a trilha A não tem nenhum teste. |

## Notas

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
  oráculo, e por que ela não baixa nada sozinha).
