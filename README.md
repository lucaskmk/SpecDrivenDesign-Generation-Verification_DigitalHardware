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

O `rvgen` escreve uma CPU com um agente de IA e a submete ao
**`spec-riscv-test`**, que executa programas oficiais `riscv-tests` RV32I,
corrigindo a partir do diagnóstico até o veredito. O `spec-riscv-test` é o
juiz do `rvgen` (`specs/constitution.md`); o `rvverify` valida entregas por
`cpu.toml`. Com `OPENROUTER_API_KEY` no `.env`, o provedor padrão é o
OpenRouter com o modelo de `SPECHDL_LLM_MODEL` (`openai/gpt-5.6-luna`); sem a
chave, é um modelo local no Ollama, escolhido pela memória da GPU.
`--provedor` escolhe outro (`ollama`, `openrouter`, `vllm`, `google`). Cada
geração é um experimento em `experimentos/<nome>/`, separado das entregas de
alunos.

O veredito só roda em **Linux/WSL2**: `--executor docker` é recusado nessa
etapa, porque a imagem `spechdl-toolchain` só tem binutils. No Windows, rode
tudo de dentro do WSL2.

```bash
python -m rvgen preparar     # confere Ollama, modelo e onde o GHDL roda; oferece instalar/baixar
python -m rvgen tipos        # monociclo, multiciclo, pipeline; rv32i ou rv32im
python -m rvgen gerar ia_mono_qwen14b
python -m rvgen gerar ia_mono_testada --testes-componentes
python -m rvgen gerar ia_mono_luna --provedor openrouter --modelo openai/gpt-5.6-luna
python -m rvgen gerar ia_mono_luna --max-chamadas 60 --max-tokens 2000000   # para com teto de gasto
python -m rvgen comparar     # experimentos lado a lado: veredito, casos, iteracoes, tokens, custo
```

`--max-chamadas` e `--max-tokens` param a geração com a sessão preservada
(retome com `python -m rvgen retomar`). Falhas transitórias da API (429, 5xx,
conexão interrompida) são repetidas até 3 vezes antes de desistir.

Nada é instalado nem baixado sem confirmação (`--verificar` só confere).
O veredito final requer GHDL, um compilador RISC-V, o ambiente
`spec-riscv-test/.venv` e o clone `riscv-tests`. Cada geração fica registrada
em `experimentos/<nome>/.rvgen/` (prompts, respostas, tokens e `report.json`).
Reprovar continua sendo resultado legítimo. O **passo a passo completo**
(preparar a máquina, escolher a IA, descrever a CPU, gerar, testar e
comparar IAs) e os prompts que o agente manda ao modelo estão em
[`rvgen/README.md`](rvgen/README.md); o fluxo técnico resumido está em
[`specs/plan.md`](specs/plan.md).

Com `--testes-componentes`, depois de gerar e compilar as fontes, o agente
gera e executa um testbench cocotb para cada VHDL em `src/` antes do
`spec-riscv-test`. A etapa ajuda a depurar; o veredito continua sendo apenas
da suíte oficial integrada.
Com `--regressoes-componentes`, uma falha de componente corrigida também gera
um testbench separado para o caso observado e casos similares; ele é preservado
na sessão e executado nas correções seguintes.
Com `--gates-componentes`, cada bloco é gerado, compilado e testado com apenas
suas dependências já aprovadas antes de a IA receber a tarefa do próximo bloco.

## Iterar nas specs

`python -m iteracoes` (ou dois cliques em `abrir-iteracoes.bat`) abre um app
local no navegador para ver, analisar, editar e comparar versões de
`specs/*.md`. A base fica congelada em `iteracoes/base/specs/`; cada iteração é
uma cópia em `iteracoes/it-NNN/`, com notas, diff contra a base, checagens do
contrato, o prompt que a IA recebe e o comando pronto para gerar com aquelas
specs (`RVGEN_SPECS_DIR=iteracoes/it-002/specs python -m rvgen gerar ...`).
O app nunca chama a IA. Detalhes em [`iteracoes/README.md`](iteracoes/README.md).

## Inventário de instruções gerado

Antes de decompor a CPU, o `rvgen` pede à LLM uma explicação breve de cada
instrução da ISA definida em [`specs/cpu.md`](specs/cpu.md). Após validar que
a lista contém exatamente as instruções exigidas, ele grava o resultado em
`architecture.json`:

```json
{
  "instructions": [
    {
      "mnemonic": "addi",
      "description": "Adds a sign-extended immediate to rs1 and writes the result to rd."
    }
  ],
  "blocks": []
}
```

Esse inventário é entregue à etapa seguinte para que a decomposição cubra todas
as instruções. Ele só é escrito depois que a LLM também produz uma decomposição
válida; enquanto aparece `extraindo instrucoes da CPU`, a resposta ainda está
sendo validada.

## Estrutura curta

```text
rvgen/                     gerador de CPUs por agente (IA local ou externa)
spec-riscv-test/           juiz do rvgen: programas oficiais riscv-tests
rvverify/                  validador de entregas por cpu.toml, modelo e suíte
cpus/rv32i_gabarito/       CPU de referência do contrato atual (barramento virtual)
cpus/rv32i_monociclo/      CPU de referência do contrato antigo (legado)
cpus/rv32i_pipeline/       CPU de referência do contrato antigo (legado)
entregas/_modelo/          manifesto inicial para copiar
entregas/<nome>/           CPU avaliada
experimentos/<nome>/       CPU gerada por IA, com as sessoes do gerador
quartus_testing/           análise no Quartus (Fmax, área, potência), opcional
specs/                     constituição, contrato da CPU, regras de VHDL e de teste
iteracoes/                 app de iterações das specs (base congelada + it-NNN)
```

Os arquivos de referência em `cpus/` não são a entrega do aluno; ver
[`cpus/README.md`](cpus/README.md).

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

O ambiente de execução é Linux/WSL2 com Python 3.11+, GHDL e cocotb 2
(`pip install -e ".[dev]"` declara as dependências Python). O veredito do
`rvgen` também exige um compilador RISC-V (`riscv64-unknown-elf-gcc`), o
`spec-riscv-test/.venv` e o clone `riscv-tests`. Sem GHDL, `rvverify` termina
com exit code diferente de zero e não aprova por inferência.

Os testes: `python -m pytest` na raiz. Na imagem das aulas
(`rafaelcorsi/pl-descomp-cocotb`, com GHDL e cocotb) eles rodam inteiros; o
mesmo comando roda no CI (`.github/workflows/tests.yml`).

Leia a documentação nesta ordem:

1. `entregas/README.md`
2. `specs/constitution.md`
3. `specs/spec.md`
4. `specs/plan.md`
5. `PROMPT_RISCV.md`
