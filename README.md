# SpecHDL: CPUs RISC-V em VHDL geradas por IA a partir de especificações e julgadas sem IA

Bancada de pesquisa para gerar hardware com LLM sem "vibe coding". O `rvgen`
transforma especificações em Markdown (`specs/`) numa CPU RISC-V em VHDL,
bloco a bloco, com contrato revisado, testes de componente e portões entre
etapas. Quem decide se a CPU funciona é um juiz determinístico, sem IA: o
`spec-riscv-test` (programas `riscv-tests`). O `rvverify` (casos próprios com
modelo de referência) valida entregas e serve de segunda opinião. Os dois
foram testados antes com uma CPU escrita à mão.

- **Documento do projeto (único, sempre atualizado):** [`docs/projeto.html`](docs/projeto.html).
  Traz o fluxo do gerador, os resultados, as mudanças desde o código do
  professor, as CPUs e modelos possíveis, os próximos passos e o histórico.
- Artigo (rascunho): [`docs/artigo.md`](docs/artigo.md)
- Experimentos e como ler uma sessão: [`experimentos/README.md`](experimentos/README.md)

## Resultados

| CPU | Origem | `spec-riscv-test` | `rvverify` | Custo do modelo |
|---|---|---|---|---|
| [`cpus/rv32i_gabarito`](cpus/rv32i_gabarito/) | escrita à mão, 1 arquivo, contrato virtual | 40/40 `rv32ui` | 24/24 RV32I | (não se aplica) |
| [`experimentos/luna6_prof_3`](experimentos/luna6_prof_3/) | gerada por `openai/gpt-6-luna`, RV32I monociclo, fluxo completo | 40/40 `rv32ui` | 24/24 RV32I | 78 chamadas, 743.978 + 124.821 tokens, cerca de US$ 0,137 |
| [`cpus/rv32im_gabarito`](cpus/rv32im_gabarito/) | escrita à mão, gabarito I + extensão M | 48/48 (`rv32ui` + `rv32um`); 8/8 só no M | 24/24 RV32I (etapa M pulada) | (não se aplica) |
| [`experimentos/luna6_evolui_im_3`](experimentos/luna6_evolui_im_3/) | **evoluída** da `luna6_prof_3` com decomposição livre: bloco novo `rv32m_unit` para o M, `cpu` só integra, 4 blocos iguais | 48/48; 8/8 só no M | não rodado | 28 chamadas, 380.089 + 52.818 tokens, cerca de US$ 0,064 |
| [`experimentos/luna6_evolui_im_2`](experimentos/luna6_evolui_im_2/) | **evoluída** da `luna6_prof_3` (RV32I → RV32IM) com `--evoluir-de`; só `decoder` e `cpu` mudaram | 48/48; 8/8 só no M | não rodado | 26 chamadas, 388.021 + 41.988 tokens, cerca de US$ 0,060 |
| [`experimentos/luna6_im_1`](experimentos/luna6_im_1/) | gerada por `openai/gpt-6-luna`, RV32IM monociclo, fluxo completo | 48/48; 8/8 só no M | não rodado | 68 chamadas, 740.595 + 115.218 tokens, cerca de US$ 0,132 |

Na coluna `rvverify`, 24/24 é a etapa RV32I (`--etapa rv32i`); o veredito do
`rvverify` para essas CPUs é `parcial`, porque ele só aprova a suíte completa e
a etapa RV32M exige um generic que o contrato atual não tem.

A CPU gerada (5 blocos, 647 linhas de VHDL) passou no juiz sem nenhuma
iteração de correção. 44 das 78 chamadas foram gastas expandindo testes de
componente. Ambiente, ameaças à validade e os defeitos do gerador achados
nessas rodadas estão no [artigo](docs/artigo.md).

## Reproduzir

O veredito do `rvgen` precisa de GHDL, cocotb, um compilador RISC-V e o clone
`riscv-tests`. A imagem [`docker/veredito`](docker/veredito/README.md) reúne
tudo, com a imagem base fixa por digest, o compilador RISC-V com versão fixa e o
`riscv-tests` fixo num commit; o repositório entra montado em
`/repo` e o `.env` é lido de lá (nada é copiado para a imagem).

```bash
docker build -t rvgen-veredito docker/veredito

# juiz no gabarito (espera-se 40/40)
docker run --rm -v "$PWD:/repo" rvgen-veredito \
  spec-riscv-test --cpu cpus/rv32i_gabarito --riscv-tests /opt/riscv-tests --isa rv32i --out /tmp/o

# gerar uma CPU com a configuração do luna6_prof_3
docker run --rm -it -v "$PWD:/repo" rvgen-veredito \
  python3 -m rvgen gerar luna6_novo --provedor openrouter --modelo openai/gpt-6-luna \
  --testes-componentes --gates-componentes --regressoes-componentes --max-casos-teste 4 \
  --executor local
```

Os comandos acima são para Linux/WSL2; as variantes para Git Bash
(`MSYS_NO_PATHCONV=1`) e PowerShell, e o `retomar` no container, estão em
[`docker/veredito/README.md`](docker/veredito/README.md).

Testes do próprio repositório, na raiz:

```bash
python -m pytest
```

Sem GHDL, os testes de simulação são pulados. Na imagem das aulas
(`rafaelcorsi/pl-descomp-cocotb`, com GHDL e cocotb) eles rodam inteiros. O CI
(`.github/workflows/tests.yml`) roda as mesmas pastas do `testpaths` do
`pyproject.toml`, sem e com simulador:

```bash
docker run --rm -v "$PWD:/repo" -w /repo rafaelcorsi/pl-descomp-cocotb:latest python3 -m pytest
```

## Gerar uma CPU com IA, local ou externa

O `rvgen` escreve uma CPU com um agente de IA e a submete ao
**`spec-riscv-test`**, que executa programas oficiais `riscv-tests` RV32I,
corrigindo a partir do diagnóstico até o veredito. O `spec-riscv-test` é o
juiz do `rvgen` (`specs/constitution.md`); o `rvverify` valida entregas por
`cpu.toml`. Com `OPENROUTER_API_KEY` no `.env`, o provedor padrão é o
OpenRouter com o modelo de `SPECHDL_LLM_MODEL` (ver `.env.example`); sem a
chave, é um modelo local no Ollama, escolhido pela memória da GPU.
`--provedor` escolhe outro (`ollama`, `openrouter`, `vllm`, `google`) e
`--modelo` troca o modelo. Cada geração é um experimento em
`experimentos/<nome>/`, separado das entregas de alunos.

O veredito só roda com o executor `local` (Linux/WSL2, ou dentro do container
`rvgen-veredito`): `--executor docker` é recusado nessa etapa, porque a imagem
`spechdl-toolchain` só tem binutils.

```bash
python -m rvgen preparar     # confere Ollama, modelo e onde o GHDL roda; oferece instalar/baixar
python -m rvgen gerar ia_mono_qwen14b
python -m rvgen gerar ia_mono_testada --testes-componentes
python -m rvgen gerar ia_mono_luna --provedor openrouter --modelo openai/gpt-6-luna
python -m rvgen gerar ia_mono_luna --max-chamadas 60 --max-tokens 2000000   # para com teto de gasto
python -m rvgen retomar ia_mono_luna <id-da-sessao>                           # continua uma sessão parada
python -m rvgen comparar     # experimentos lado a lado: veredito, casos, iteracoes, tokens, custo
```

`--max-chamadas` e `--max-tokens` param a geração com a sessão preservada
(retome com `python -m rvgen retomar`). Falhas transitórias da API (429, 5xx,
conexão interrompida) são tentadas até 3 vezes no total antes de desistir.

Nada é instalado nem baixado sem confirmação (`--verificar` só confere).
O veredito final requer GHDL, um compilador RISC-V, o `spec-riscv-test` e o
clone `riscv-tests` (fora do container: `spec-riscv-test/.venv` e
`riscv-tests` ao lado do repositório, ou `RVGEN_SPEC_RISCV_TEST` e
`RVGEN_RISCV_TESTS`). Cada geração fica registrada em
`experimentos/<nome>/.rvgen/` (prompts, respostas, tokens e `report.json`).
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
As três juntas são o "fluxo completo" usado em `experimentos/luna6_prof_3`.

### Inventário de instruções gerado

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

## Iterar nas specs

`python -m iteracoes` (ou dois cliques em `abrir-iteracoes.bat`) abre um app
local no navegador para ver, analisar, editar e comparar versões de
`specs/*.md`. A base fica congelada em `iteracoes/base/specs/`; cada iteração é
uma cópia em `iteracoes/it-NNN/`, com notas, diff contra a base, checagens do
contrato, o prompt que a IA recebe e o comando pronto para gerar com aquelas
specs (`RVGEN_SPECS_DIR=iteracoes/it-002/specs python -m rvgen gerar ...`).
O app nunca chama a IA. `--porta` escolhe a porta (padrão 8765) e
`--sem-navegador` só mostra o endereço. Detalhes em
[`iteracoes/README.md`](iteracoes/README.md).

## Validar entregas (`rvverify`)

O `rvverify` avalia CPUs RISC-V feitas por alunos (ou qualquer CPU descrita
por um manifesto). A CPU entra em `entregas/`, o manifesto `cpu.toml` descreve
sua interface e o `rvverify` executa testes reais com GHDL e cocotb. Uma
reprovação é um resultado esperado e útil; aprovação só acontece quando a
suíte completa passa.

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
nunca para declarar aprovação. `--etapa rv32i` roda só a etapa RV32I (veredito
`parcial`). `--workdir` preserva `sim.log`, imagens `.ram` e os demais
artefatos de cada caso, para inspeção depois da execução.

### O que é verificado

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
`spec-riscv-test` e o clone `riscv-tests`; a imagem `docker/veredito` traz
todos. Sem GHDL, `rvverify` termina com exit code diferente de zero e não
aprova por inferência. As imagens Docker do projeto estão descritas em
[`docker/README.md`](docker/README.md).

## Estrutura

```text
rvgen/                     gerador de CPUs por agente (IA local ou externa)
spec-riscv-test/           juiz do rvgen: programas oficiais riscv-tests
rvverify/                  validador de entregas por cpu.toml, modelo e suíte
cpus/rv32i_gabarito/       CPU de referência do contrato atual (barramento virtual)
cpus/rv32i_monociclo/      CPU de referência do contrato antigo (legado)
cpus/rv32i_pipeline/       CPU de referência do contrato antigo (legado)
entregas/_modelo/          manifesto inicial para copiar
entregas/<nome>/           CPU avaliada
experimentos/<nome>/       CPU gerada por IA, com as sessões do gerador
specs/                     constituição, contrato da CPU, regras de VHDL e de teste
iteracoes/                 app de iterações das specs (base congelada + it-NNN)
docker/                    imagens: aulas, toolchain, Quartus e veredito do rvgen
quartus_testing/           análise no Quartus (Fmax, área, potência), opcional
docs/                      artigo, fluxo do rvgen e mapa do projeto
```

Os arquivos de referência em `cpus/` não são a entrega do aluno; ver
[`cpus/README.md`](cpus/README.md).

Leia a documentação nesta ordem:

1. `docs/artigo.md`
2. `entregas/README.md`
3. `specs/constitution.md`
4. `specs/spec.md`
5. `specs/plan.md`
6. `PROMPT_RISCV.md`
