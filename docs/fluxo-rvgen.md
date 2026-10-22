# Fluxo do rvgen (resumo para colar numa IA)

Versão curta de `docs/fluxo-rvgen.html`. Lido no commit `bd302b6`; **nada foi
executado**. Prefira este arquivo ao `rvgen/agente.py` (5.457 linhas, 340 KB).
Números de linha envelhecem: procure pelo nome da função.

## Fluxo, em ordem

1. **Entrada.** `specs/cpu.md` declara 1 ISA (`RV32I`/`RV32IM`) e 1
   microarquitetura (`single cycle`/`multicycle`/`pipeline`), mais a interface
   exata do top-level `cpu`. `contrato.ler_configuracao_cpu`.
2. **Arquitetura (2 chamadas LLM).** `_inventariar_instrucoes` (1667) descreve
   cada instrução; `_planejar` (1695) decompõe a CPU em 2–8 blocos. O último é
   sempre `cpu`. `validar_arquitetura` (276) ordena topologicamente.
3. **Contrato por bloco.** `_escrever_especificacao` (1218) grava
   `component_specs/<bloco>.comp_spec.txt` (markdown) com 6 seções fixas:
   Timing, Reset, Behavior, Operations, Edge cases, Test strategy.
4. **Revisor independente.** `_validar_especificacao_por_agente` (1439) responde
   `APPROVED` ou `REVISE`. `REVISE` → `_revisar_especificacao` (1357) e revisa de
   novo, até `--tentativas-revisao-semantica` (3). Se cita uma dependência, ela é
   revisada antes (`_revisar_dependencias_citadas`). Esgotou → `ErroGeracao`.
5. **Pilha** (`--gates-componentes`, `_gerar_com_portoes`, 4706). Para cada bloco,
   folhas primeiro: `_escrever_bloco` (VHDL) → `_testar_componentes` (testbench
   cocotb + GHDL) → `_congelar_bloco` (hash em `componentes_aprovados/`). Só
   compila o fecho de dependências do bloco (`_fontes_do_bloco`). Falha → triagem;
   orçamento esgotado → `ErroGeracao` (sessão retomável com `retomar`).
6. **Separação VHDL × teste.** Prompt do VHDL: contrato + interfaces. Prompt do
   testbench (`_escrever_testbench`, 1796): só contrato + portas, "a
   implementação não é fornecida". **Mesmo modelo** nos dois papéis (um só
   `--modelo`, hoje `gpt-5.6-luna`); a separação é de contexto.
7. **Triagem** (`_triagem_componente`, 3578). Causa ∈ `vhdl` | `testbench` |
   `spec` | `ambigua`. Regras objetivas vencem o LLM (largura de porta,
   `int(x,2)` no cocotb 2, coroutine sem `dut` → testbench). `vhdl` por assertion
   é confirmado por um teste mínimo independente. `spec` → revisa contrato,
   regenera VHDL e testbench, invalida dependentes. Toda correção reroda todos os
   testes do bloco.
8. **CPU integrada.** O bloco `cpu` é o último degrau da pilha, com testbench de
   IA (programas montados pelo GNU assembler via `riscv_asm.py`). Depois
   `_corrigir` (4948) roda `spec-riscv-test`: fumaça (1 programa) → suíte
   completa (40 programas `rv32ui`; 48 com `rv32um`).
9. **Correção.** Por falha oficial: escolhe 1 arquivo (erro do GHDL aponta; ou
   bloco com regressão fixado; ou hipóteses com VCD em `_explorar_cpu_superior`;
   ou o modelo escolhe em `_escolher`), `_reescrever` só esse arquivo, roda as
   provas do componente, mede o placar. Piorou → desfaz e anota. Orçamento
   `--iteracoes` (12).
10. **Veredito.** Fim de `gerar` (5377): suíte completa sem filtro; antes, confere
    que nenhum arquivo do validador mudou (`arquivos_protegidos`, `hash_de`). Nenhuma
    IA decide. **No código atual quem decide é o `spec-riscv-test`, não o `rvverify`**
    (ver seção Certificação).
11. **Opcional.** `quartus_testing/quartus_cpu_check.py`: Fmax, área, potência.
    Não muda o veredito.

## Certificação: specs dizem `rvverify`, código usa `spec-riscv-test`

- **Specs:** `constitution.md`: "`rvverify` é a única autoridade do veredito da CPU
  integrada"; `plan.md` e `spec.md` passo 8 idem.
- **Código:** `rvgen/executor.py`: "o veredito vem sempre do spec-riscv-test real".
  O `rvgen` nunca chama o `rvverify`. `renderizar_cpu_toml` só é usada em testes, então
  o `rvgen` não gera o `cpu.toml` que o `rvverify` exige.

| | `rvverify` | `spec-riscv-test` |
|---|---|---|
| quem chama | você: `python -m rvverify <pasta>` | o `rvgen` (fumaça, correção, veredito) |
| entrada | `cpu.toml` (manifesto) | `src/*.vhd` + interface do `cpu.md` |
| casos | 35 próprios (24 RV32I + 11 RV32M) | `riscv-tests` oficiais: 40 (48 com M) |
| esperado vem de | modelo Python (`reference.py`) | o programa oficial (`tohost`) |
| veredito | aprovado/reprovado/incompleto/parcial | aprovado se suíte completa passa |

Não testei se o modo `virtual` do `rvverify` casa com a interface do `cpu.md`.
Divergência spec × código: o `CLAUDE.md` manda atualizar a spec antes. Opções:
(A) `rvgen` chama o `rvverify` no veredito; (B) `spec-riscv-test` julga o laço e o
`rvverify` certifica depois; (C) corrigir constituição/plano para `spec-riscv-test`.
Perguntar ao professor qual é o "certificado real".

## Flags que importam

| Flag | Efeito |
|---|---|
| (nenhuma) | contrato + revisão por bloco, VHDL de tudo, direto à suíte oficial |
| `--testes-componentes` | testbench por bloco, mas depois de escrever tudo |
| `--gates-componentes` | a pilha: contratos globais → VHDL → teste → congela, bloco a bloco |
| `--regressoes-componentes` | falha corrigida vira teste permanente |
| `--iteracoes N` | orçamento de correções (12) |
| `--provedor/--modelo` | `ollama` (padrão do código), `openrouter`, `vllm`, `google` |

Fluxo do professor = as três flags de componente juntas:

```bash
python -m rvgen gerar cpu_luna --provedor openrouter --testes-componentes --gates-componentes --regressoes-componentes
```

Nome simples grava em `experimentos/<nome>/`; caminho grava no caminho.

## Modelo: OpenRouter, sem Ollama, sem exemplos

- `.env` tem `SPECHDL_LLM_MODEL=openai/gpt-5.6-luna` e chave do OpenRouter. Esse é
  `config.MODELO_EXTERNO_PADRAO`. "luna 6" = `gpt-5.6-luna` (presumido).
- **O provedor padrão do código ainda é `ollama`.** Use `--provedor openrouter` ou
  `RVGEN_PROVEDOR=openrouter` no `.env`; senão o `rvgen` procura Ollama e falha.
- `ClienteOpenAI` (`llm.py`): POST em `/chat/completions` com `model`, `messages`,
  `temperature` 0,2. O schema JSON **não** vai para a API (só no prompt);
  `extrair_json` valida e o agente reenvia até 2 vezes.
- Sem `--exemplo`: o modelo não recebe nenhuma CPU de referência.
- Cada chamada tem mensagens novas, sem histórico. Chamadas sequenciais por padrão.
- Sem medida de tempo/custo com luna no repositório (os 17–18 min são do Ollama 14B).
  Gasto fica em `resultado.json` e em `python -m rvgen comparar`.
- GHDL/cocotb/`spec-riscv-test` rodam local ou no Docker `spechdl-toolchain`. Neste PC
  não achei `ghdl`, compilador RISC-V nem clone `riscv-tests` no PATH.

## Papéis de IA: 26 tipos de chamada, 1 modelo

Agrupamento meu, pelos nomes da etiqueta `fase` em `_chamar`:

- **Arquitetura:** `instrucoes`, `decomposicao`
- **Contrato:** `especificacao_componente`, `revisao_semantica_especificacao`, `revisao_especificacao`
- **VHDL:** `escrita`, `correcao`, `escolha`
- **Testbench (10):** `testbench`, `ampliacao_testbench`, `correcao_testbench`,
  `caso_publico_isolado`, `caso_interno_isolado`, `regressao`, `teste_interno_componente`,
  `ampliacao_teste_interno`, `orquestracao_expansao_testbench`, `orquestracao_lote_testbench`
- **Diagnóstico (8):** `triagem_componente`, `diagnostico_componente`,
  `revisao_convergencia_componente`, `diagnostico_interno_componente`,
  `planejar_diagnostico_interno`, `hipotese_exploratoria`, `revisao_hipotese`,
  `revisao_correcao_local`

Diferem pelo prompt de sistema (`contrato` × `contrato_testes`, confirmado em 8 fases)
e pelo que vai no pedido, não pelo modelo. Contexto limpo não elimina viés do modelo;
o juiz independente é o `spec-riscv-test`.

## Escrita e artefatos

A IA só escreve em `<pasta>/src/*.vhd` (`_destino` recusa o resto). Tudo mais em
`<pasta>/.rvgen/sessao-*/`: `component_specs/`, `testes/`, `testes_aprovados/`,
`componentes_aprovados/`, `regressoes/`, `testes_resultados/`, `sim/`, `build/`,
`spec-riscv-test/`, `contrato.txt`, `resultado.json`.

## RV32I agora, IM depois

`cpu.md` está em "RV32I single cycle". O código já aceita `RV32IM`
(`ISAS = ("rv32i","rv32im")`): o juiz passa a rodar 48 programas e o prompt pede o
generic `RV32M_ENABLE`, com o testbench rodando a CPU duas vezes. Atenção: `cpu.md`
exige entidade exata sem generic; parece inconsistente com o prompt de IM (não
testado). Não há tabela de referência do M em `specs/`.

## A confirmar com o professor

1. Mesma IA para VHDL e testes (viés só reduzido por contexto).
2. A "outra IA que testa a CPU" é o testbench do bloco `cpu`; a suíte oficial é
   determinística, não IA.
3. `CLAUDE.md` ainda descreve o fluxo Streamlit/Yosys; o README atual descreve o
   fluxo de terminal. O próprio CLAUDE.md manda atualizar a spec antes.
