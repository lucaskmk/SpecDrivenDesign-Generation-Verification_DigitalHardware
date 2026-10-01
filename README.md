# SpecHDL / RVVerify

Este repositório avalia CPUs RISC-V feitas por alunos ou por modelos de IA.
O fluxo principal é de terminal: a CPU entra em `entregas/`, o manifesto
`cpu.toml` descreve sua interface e `rvverify` executa testes reais com GHDL e
cocotb. Uma reprovação é um resultado esperado e útil; aprovação só acontece
quando a suíte completa passa.

## Começar

```bash
cp -r entregas/_modelo entregas/seu_nome
# edite entregas/seu_nome/cpu.toml e coloque o VHDL em src/
python -m rvverify --listar
python -m rvverify entregas/seu_nome --keep --workdir relatorio
```

Para validar todas as entregas:

```bash
python -m rvverify
```

Para automação e CI:

```bash
python -m rvverify entregas/seu_nome --eventos --json relatorio.json
```

`--eventos` emite JSON Lines com progresso. `--casos sra,mul` executa apenas
casos selecionados e sempre produz veredito `PARCIAL`; isso serve para depurar,
nunca para declarar aprovação. `--workdir` preserva `sim.log`, imagens `.ram`
e os demais artefatos de cada caso, para inspeção depois da execução.

## Gerar uma CPU com IA, local ou externa

O `rvgen` escreve uma CPU com um agente de IA e a submete ao **mesmo**
`rvverify`, corrigindo a partir do diagnóstico até o veredito. Por padrão
usa um modelo local no Ollama, escolhido pela memória da GPU; com
`OPENROUTER_API_KEY` no `.env`, `--provedor openrouter` usa um modelo
externo. Só biblioteca padrão do Python. Cada geração é um experimento em
`experimentos/<nome>/`, separado das entregas de alunos.

```bash
python -m rvgen preparar     # confere Ollama, modelo e onde o GHDL roda; oferece instalar/baixar
python -m rvgen tipos        # monociclo, multiciclo, pipeline; rv32i ou rv32im
python -m rvgen gerar ia_mono_qwen14b --tipo monociclo --isa rv32im
python -m rvgen gerar ia_mono_luna --tipo monociclo --isa rv32im --provedor openrouter --modelo openai/gpt-5.6-luna
python -m rvgen comparar     # experimentos lado a lado: veredito, casos, iteracoes, tokens, custo
```

Nada é instalado nem baixado sem confirmação (`--verificar` só confere).
Sem GHDL no host — o caso do Windows —, o validador roda na imagem
`spechdl-toolchain` com o Docker Desktop aberto. Cada geração fica registrada
em `experimentos/<nome>/.rvgen/` (prompts, respostas, tokens, relatórios do
`rvverify`).
Reprovar continua sendo resultado legítimo. O **passo a passo completo**
(preparar a máquina, escolher a IA, descrever a CPU, gerar, testar e
comparar IAs) e os prompts que o agente manda ao modelo estão em
[`rvgen/README.md`](rvgen/README.md); a arquitetura, em `specs/plan.md`,
seção 9, e na ADR-018.

## Estrutura curta

```text
rvverify/                  validador, harness, modelo e suíte
rvgen/                     gerador de CPUs por agente (IA local ou externa)
cpus/rv32i_pipeline/       CPU de referência em pipeline
cpus/rv32i_monociclo/      CPU de referência monociclo
entregas/_modelo/          manifesto inicial para copiar
entregas/<nome>/           CPU avaliada
experimentos/<nome>/       CPU gerada por IA, com as sessoes do gerador
specs/                     requisitos, decisões, plano e backlog
legado/                    trilha genérica antiga (SpecHDL Streamlit) e smoke tests
```

Os arquivos de referência em `cpus/` não são a entrega do aluno. A suíte usa
o mesmo contrato para uma CPU modificada e para uma CPU escrita do zero.

## O que é verificado

- RV32I: aritmética, shifts, comparações, `x0`, registradores, load/store,
  branches, jumps, `LUI`, `AUIPC`, dependências e parada.
- RV32IM: `MUL`, `MULH`, `MULHSU`, `MULHU`, `DIV`, `DIVU`, `REM`, `REMU`,
  divisão por zero, overflow e dependências imediatas.
- Rigor: valores esperados vêm do modelo Python, não de constantes copiadas do
  RTL; falhas mostram requisito, entrada, esperado, obtido e log.
- Métricas: ciclos, CPI e área só aparecem quando observados por simulação ou
  síntese real; o restante é marcado como não observável.

## Ferramentas

O ambiente de execução é Linux/WSL2 com Python 3.11+, GHDL e cocotb. Yosys é
necessário para a etapa opcional de síntese. Sem GHDL, `rvverify` termina com
exit code diferente de zero e não aprova por inferência.

Leia a documentação nesta ordem:

1. `entregas/README.md`
2. `specs/constitution.md`
3. `specs/spec.md`
4. `specs/plan.md`
5. `PROMPT_RISCV.md`
