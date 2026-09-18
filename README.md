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
nunca para declarar aprovação. `--workdir` preserva `sim.log`, imagens `.ram`,

## Estrutura curta

```text
rvverify/                  validador, harness, modelo e suíte
cpus/rv32i_pipeline/       CPU de referência em pipeline
cpus/rv32i_monociclo/      CPU de referência monociclo
entregas/_modelo/          manifesto inicial para copiar
entregas/<nome>/           CPU avaliada
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
