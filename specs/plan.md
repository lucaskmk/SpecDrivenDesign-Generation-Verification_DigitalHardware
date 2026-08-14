# Plano técnico — SpecHDL

## Stack
- Python 3.11+
- Anthropic SDK — extração de spec, decomposição arquitetural e geração de
  VHDL (chamadas de LLM)
- GHDL — compilação e simulação VHDL
- cocotb — testbench em Python, dirige o DUT VHDL através do GHDL (fluxo
  `make SIM=ghdl`); ambiente de referência é a imagem Docker
  `rafaelcorsi/pl-descomp-cocotb`, a mesma usada no smoke test de
  `examples/toolchain_smoketest/`
- Yosys + ghdl-yosys-plugin — síntese real para métricas PPA
- pytest — testes do pipeline Python
- Typer (ou argparse) — CLI

## Estrutura de pastas proposta

```
specHDL/
├── CLAUDE.md
├── specs/
│   ├── constitution.md
│   ├── spec.md
│   ├── plan.md
│   └── tasks.md
├── src/
│   └── spechdl/
│       ├── ingestion/       # fase 1 — parsing de PDF/docx, extração EARS
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
    {"id": "FR-01", "type": "functional", "text": "...", "source_excerpt": "..."},
    {"id": "NFR-01", "type": "non_functional", "category": "power|speed|area", "text": "..."}
  ]
}
```

**architecture.json** (saída da fase 2):
```json
{
  "blocks": [
    {
      "name": "alu",
      "inputs": ["a", "b", "opcode"],
      "outputs": ["result", "flags"],
      "responsibility": "...",
      "satisfies": ["FR-03", "NFR-02"],
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
  "simulation": {"status": "pass|fail", "log_path": "...", "failed_requirement": null},
  "ppa": {"cells": 0, "estimated_critical_path_ns": 0, "method": "synthesis|heuristic"}
}
```

## Fase 3/4 em detalhe — testbench via cocotb
Cada bloco gerado vem com um testbench cocotb (Python) e um `Makefile` no
padrão `TOPLEVEL_LANG = vhdl`, `SIM = ghdl`, `MODULE = test_<bloco>`,
`VHDL_SOURCES = ../src/<bloco>.vhd` — o mesmo padrão usado em
`examples/toolchain_smoketest/`. O wrapper Python da fase 4 (T4.1) roda
`make -C outputs/<bloco>/test/` e captura exit code + log, em vez de chamar
`ghdl` diretamente; quem invoca o GHDL por baixo é o próprio cocotb. Ambiente
de referência (usado também na CI de smoke test): imagem Docker
`rafaelcorsi/pl-descomp-cocotb`.

## Fase 5 em detalhe — por que síntese real em vez de a IA "chutar" PPA
Yosys, com o plugin ghdl-yosys-plugin, lê VHDL usando o GHDL como frontend,
sintetiza para uma biblioteca de células genérica e roda o comando `stat`
para contagem de células/área. Isso dá números de verdade em vez de uma
estimativa da LLM — muito mais defensável numa apresentação acadêmica. Se o
setup do plugin não for viável dentro do prazo da disciplina, cair para o
fallback heurístico do FR-13, deixando isso explícito no relatório final.

## Fase gate
Não iniciar a fase N+1 até que todas as tarefas da fase N em `tasks.md`
estejam marcadas como concluídas e o critério de aceite verificado — ver
`constitution.md`, princípio 1.
