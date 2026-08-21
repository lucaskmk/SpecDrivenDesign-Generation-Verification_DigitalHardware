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
  `examples/toolchain_smoketest/`
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
confundir com os exemplos de referência em `examples/ula32_sol/` e
`examples/ula32_terra/` — esses foram gerados contra o modelo antigo (texto
livre) por um agente externo, servem só como prova de que o método SDD
funciona ponta a ponta, não como formato de fixture pra fase 1.

## Fase 3/4 em detalhe — testbench via cocotb
Cada bloco gerado vem com um testbench cocotb (Python) e um `Makefile` no
padrão `TOPLEVEL_LANG = vhdl`, `SIM = ghdl`, `MODULE = test_<bloco>`,
`VHDL_SOURCES = ../src/<bloco>.vhd` — o mesmo padrão usado em
`examples/toolchain_smoketest/`. O wrapper Python da fase 4 (T4.1) roda
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
