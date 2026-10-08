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

## Artefatos

Cada geração preserva prompts, respostas, logs e resultados em
`<entrega>/.rvgen/sessao-*/`. O VHDL fica em `<entrega>/src/`; a suíte não usa
manifesto `cpu.toml`.

## Verificar novamente

```bash
spec-riscv-test --cpu entregas/minha_cpu --riscv-tests riscv-tests --out out
```
