# SpecHDL

Pipeline spec-driven que parte de um enunciado de exercício de arquitetura
de computadores (ULA, banco de registradores, unidade de controle, muxes
etc.), extrai requisitos estruturados, decompõe em blocos de hardware, gera
VHDL + testbenches, verifica no GHDL e produz um relatório de trade-offs de
potência, velocidade e área (PPA).

O projeto em si é construído seguindo a metodologia que ele implementa:
**nenhuma linha de código antes de uma spec aprovada** — ver
[`specs/constitution.md`](specs/constitution.md), princípio 1.

## O pipeline

![Pipeline: documento → spec EARS → decomposição arquitetural → geração de VHDL+testbench → verificação GHDL → análise PPA → relatório final, com falha voltando para a spec](pipeline_sdd_hardware.png)

1. **Ingestão** — um documento (PDF/docx/texto) com o enunciado vira um
   conjunto de requisitos estruturados em notação EARS (`spec.json`).
2. **Decomposição arquitetural** — a spec aprovada vira uma proposta de
   blocos de hardware, cada decisão justificada por pelo menos um requisito
   não-funcional (potência, velocidade ou área).
3. **Geração de VHDL + testbench** — cada bloco vira um arquivo VHDL e um
   testbench [cocotb](https://www.cocotb.org/) (Python), ambos rastreando o
   ID do requisito que implementam.
4. **Verificação** — cada bloco (e depois o design integrado) é compilado e
   simulado de fato no GHDL, orquestrado pelo cocotb; falha de simulação é
   reportada junto do requisito não atendido.
5. **Análise PPA** — síntese real via Yosys + `ghdl-yosys-plugin` para
   contagem de células/área, em vez de a IA estimar métricas "no chute".
6. **Relatório final** — rastreia cada requisito até o bloco, o arquivo
   VHDL, o resultado do teste e a métrica de PPA correspondente.

## Estado atual

O projeto está na **Fase 0 (setup)** — a fase de especificação está
concluída e alinhada, mas o código do pipeline (`src/spechdl/`) ainda não
existe.

**Pronto:**
- Constituição, spec funcional (EARS), plano técnico e backlog de tarefas
  em [`specs/`](specs/), revisados e consistentes entre si.
- Decisão de stack para testbench (cocotb/Python sobre GHDL) registrada e
  propagada por todos os documentos.
- Smoke test de toolchain (GHDL + cocotb) em
  [`examples/toolchain_smoketest/`](examples/toolchain_smoketest/), com CI
  em [`.github/workflows/toolchain-smoketest.yml`](.github/workflows/toolchain-smoketest.yml).

**Pendente (backlog completo em [`specs/tasks.md`](specs/tasks.md)):**
- T0.1–T0.5 — estrutura de pastas do pipeline, ambiente Python, validação
  de GHDL/cocotb/Yosys, `ANTHROPIC_API_KEY` e o exemplo fixo (ex.: ALU 4
  bits) que serve de fixture pras fases seguintes.
- Todo o restante do pipeline (Fases 1 a 7): ingestão, decomposição,
  geração, verificação, PPA, relatório e CLI.

## Especificações — leia nesta ordem

| Ordem | Arquivo | Conteúdo |
|---|---|---|
| 1 | [`specs/constitution.md`](specs/constitution.md) | Princípios inegociáveis do projeto |
| 2 | [`specs/spec.md`](specs/spec.md) | Requisitos funcionais/não-funcionais (EARS) do pipeline |
| 3 | [`specs/plan.md`](specs/plan.md) | Arquitetura técnica, estrutura de pastas, contratos JSON entre fases |
| 4 | [`specs/tasks.md`](specs/tasks.md) | Backlog atômico, fase por fase |

O [`CLAUDE.md`](CLAUDE.md) na raiz resume as regras de comportamento pra
quem (ou qual agente) for implementar o pipeline em cima dessa spec.

Uma versão visual — diagrama do pipeline (com os gates de aprovação humana e
a triagem de falha), árvore do repositório e status por fase — está em
[`docs/mapa-do-projeto.html`](docs/mapa-do-projeto.html) (abra localmente no
navegador). É uma foto do estado do repo num momento; a fonte de verdade
continua sendo `specs/tasks.md`.

## Estrutura do repositório

```
.
├── CLAUDE.md                       # instruções de comportamento pro Claude Code
├── README.md
├── pipeline_sdd_hardware.png       # diagrama do pipeline (acima)
├── docs/
│   └── mapa-do-projeto.html        # versão visual: diagrama + árvore + status
├── specs/
│   ├── constitution.md
│   ├── spec.md
│   ├── plan.md
│   └── tasks.md
├── examples/
│   └── toolchain_smoketest/        # smoke test do toolchain GHDL+cocotb (T0.2)
│       ├── src/demux.vhd
│       └── test/{test_demux.py, Makefile}
└── .github/workflows/
    └── toolchain-smoketest.yml
```

`src/spechdl/`, `tests/`, `outputs/` e o exemplo real da disciplina
(`examples/alu_4bit/` ou equivalente) ainda serão criados a partir da
Fase 0 — ver estrutura completa proposta em
[`specs/plan.md`](specs/plan.md).

## Stack

- Python 3.11+ (uv ou venv)
- [Anthropic SDK](https://docs.anthropic.com/) — extração de spec,
  decomposição arquitetural e geração de VHDL (`ANTHROPIC_API_KEY` via
  variável de ambiente, nunca hardcoded)
- [GHDL](https://github.com/ghdl/ghdl) — compilação/simulação VHDL
- [cocotb](https://www.cocotb.org/) — testbenches em Python sobre o GHDL
- [GTKWave](https://gtkwave.sourceforge.net/) — inspeção visual do waveform
  (`.vcd`) na triagem manual de falha
- [Yosys](https://github.com/YosysHQ/yosys) + `ghdl-yosys-plugin` — síntese
  real para as métricas de PPA
- pytest — testes do próprio pipeline (não confundir com os testbenches
  cocotb gerados, que testam o hardware)

Ambiente de referência: Linux/WSL2, imagem Docker
`rafaelcorsi/pl-descomp-cocotb` (mesma usada no smoke test de CI).

## Próximo passo

Começar `T0.1` em [`specs/tasks.md`](specs/tasks.md): criar a estrutura de
pastas do pipeline e o ambiente virtual Python.
