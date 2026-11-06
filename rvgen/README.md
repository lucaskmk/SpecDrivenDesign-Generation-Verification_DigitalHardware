# rvgen

`rvgen` usa uma LLM para gerar uma CPU RISC-V em VHDL e a submete ao
`spec-riscv-test`. A suíte oficial integrada é a autoridade final.

## Definir a CPU

Edite [`specs/cpu.md`](../specs/cpu.md). Antes de chamar a LLM, o `rvgen`
identifica no texto uma ISA e uma microarquitetura:

```md
- RV32I single cycle
```

Também são aceitos `RV32IM`, `multicycle` e `pipeline`; use somente uma ISA e
uma microarquitetura. O top-level é sempre `cpu`, pois essa é a interface
esperada pelo validador.

Para gerar com outra versão das specs (por exemplo uma iteração do app
[`python -m iteracoes`](../iteracoes/README.md)), defina `RVGEN_SPECS_DIR`
com a pasta, absoluta ou relativa à raiz:
`RVGEN_SPECS_DIR=iteracoes/it-002/specs python -m rvgen gerar it002_teste`.
O `rvgen gerar` mostra a pasta (`specs   : ...`) e a registra no evento
`inicio` da sessão.

## Gerar

```bash
python -m rvgen preparar --verificar
python -m rvgen gerar entregas/minha_cpu
```

Opções operacionais úteis:

```bash
python -m rvgen gerar entregas/minha_cpu \
  --testes-componentes --gates-componentes --regressoes-componentes
```

`--descricao` e `--descricao-arquivo` acrescentam orientação à LLM sem
alterar o contrato verificável. `--provedor`, `--modelo` e `--executor`
selecionam a infraestrutura de execução.

### Gemini API

Para usar diretamente a API do Google, crie uma chave no Google AI Studio e
guarde-a fora do Git no `.env` da raiz:

```text
GEMINI_API_KEY=...
RVGEN_PROVEDOR=google
RVGEN_GEMINI_MODEL=gemini-2.5-flash
```

Depois, use `python -m rvgen gerar entregas/minha_cpu --provedor google`.
`--modelo` substitui `RVGEN_GEMINI_MODEL` apenas nessa execução.

## Evoluir uma CPU aprovada

Em vez de gerar do zero, `--evoluir-de` parte de uma CPU que já passou no
juiz e a muda para as specs atuais (por exemplo de RV32I para RV32IM):

```bash
RVGEN_SPECS_DIR=iteracoes/it-001/specs python -m rvgen gerar luna6_evolui_im \
    --evoluir-de experimentos/luna6_prof_3 --provedor openrouter \
    --testes-componentes --gates-componentes --regressoes-componentes --max-casos-teste 4
```

Primeiro roda, sem IA, todos os testes de componente da CPU de origem e o juiz
na ISA antiga; depois a IA lê o diff entre o contrato antigo e o novo e planeja
quais blocos mudam (`.rvgen/sessao-*/evolucao/plano.md`). Só esses blocos têm
contrato e VHDL atualizados (os testes antigos deles viram regressão); os
outros ficam congelados e rodam os próprios testes de novo. O plano devolve a
decomposição-alvo inteira e pode manter, mudar, criar, dividir, juntar,
renomear e remover blocos (`--max-blocos`, padrão 16 na evolução e 8 no
`gerar`); o topo `cpu` só integra e é recusado se tiver `*`, `/`, `rem` ou
`mod` (`--permitir-conta-no-topo` desliga essa regra; sem ela, a evolução
RV32I -> RV32IM também criou um bloco próprio para o M). O juiz final roda
na ISA nova, com o laço de correção de sempre. Código em `rvgen/evolucao.py`.

## Artefatos

Cada geração preserva prompts, respostas, logs e resultados em
`<entrega>/.rvgen/sessao-*/`. O VHDL fica em `<entrega>/src/`; a suíte não usa
manifesto `cpu.toml`.

## Verificar novamente

```bash
spec-riscv-test --cpu entregas/minha_cpu --riscv-tests riscv-tests --out out
```
