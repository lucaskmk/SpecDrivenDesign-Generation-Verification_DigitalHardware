# Fluxo do rvgen (resumo para colar numa IA)

Versão curta de `docs/fluxo-rvgen.html`. Lido no commit `bd302b6` e atualizado
em 29/10/2026 depois das correções (lista em `docs/projeto-completo.html`,
seção 7). Prefira este arquivo ao `rvgen/agente.py` (~5.500 linhas). Números
de linha envelhecem: procure pelo nome da função.

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
    IA decide. **Quem decide é o `spec-riscv-test`** (seção Certificação).
11. **Opcional.** `quartus_testing/quartus_cpu_check.py`: Fmax, área, potência.
    Não muda o veredito.

## Certificação: o `spec-riscv-test` julga o `rvgen`

- **Decidido em 29/10:** `constitution.md`, `plan.md`, `spec.md` (passo 8) e
  `testes.md` agora dizem o que o código e os READMEs do commit `bd302b6` (Corsi)
  já faziam: o `spec-riscv-test` é a única autoridade do veredito do `rvgen`.
  Falta o Corsi confirmar.
- **O `rvverify`** continua validando entregas por `cpu.toml`. O `rvgen` não o chama
  nem gera `cpu.toml` (`renderizar_cpu_toml` só é usada em testes).

| | `rvverify` | `spec-riscv-test` |
|---|---|---|
| quem chama | você: `python -m rvverify <pasta>` | o `rvgen` (fumaça, correção, veredito) |
| entrada | `cpu.toml` (manifesto) | `src/*.vhd` + interface do `cpu.md` |
| casos | 35 próprios (24 RV32I + 11 RV32M) | `riscv-tests` oficiais: 40 (48 com M) |
| esperado vem de | modelo Python (`reference.py`) | o programa oficial (`tohost`) |
| veredito | aprovado/reprovado/incompleto/parcial | aprovado se suíte completa passa |

O modo `virtual` do `rvverify` foi testado com `cpus/rv32i_gabarito` (24/24 RV32I)
depois de duas correções no `tb_virtual`: o endereço de dados era lido antes de a
instrução assentar (stores iam para o endereço errado e a RAM terminava zerada), e
o relatório de falha derrubava o `feedback` com `AttributeError`.

Sobre o nome "oficial": `riscv-tests` são testes unitários da organização
`riscv-software-src`; a suíte que se descreve como certificação é a
`riscv-arch-test`, que o projeto não usa. E o `spec-riscv-test` roda os programas
oficiais com um ambiente próprio (sem CSR/ECALL, relinkado em 0).

## Flags que importam

| Flag | Efeito |
|---|---|
| (nenhuma) | contrato + revisão por bloco, VHDL de tudo, direto à suíte oficial |
| `--testes-componentes` | testbench por bloco, mas depois de escrever tudo |
| `--gates-componentes` | a pilha: contratos globais → VHDL → teste → congela, bloco a bloco |
| `--regressoes-componentes` | falha corrigida vira teste permanente |
| `--iteracoes N` | orçamento de correções (12) |
| `--max-chamadas N`, `--max-tokens N` | param com a sessão preservada (sem teto por padrão) |
| `--provedor/--modelo` | `openrouter` é o padrão quando há `OPENROUTER_API_KEY`; senão `ollama`. Também `vllm`, `google` |

Fluxo do professor = as três flags de componente juntas:

```bash
python -m rvgen gerar cpu_luna --provedor openrouter --testes-componentes --gates-componentes --regressoes-componentes
```

Nome simples grava em `experimentos/<nome>/`; caminho grava no caminho.

## Modelo: OpenRouter, sem Ollama, sem exemplos

- `.env` tem `SPECHDL_LLM_MODEL=openai/gpt-5.6-luna` e chave do OpenRouter. Esse é
  `config.MODELO_EXTERNO_PADRAO`. "luna 6" = `gpt-5.6-luna` (presumido).
- **Com a chave no `.env`, o padrão já é o OpenRouter** (`config.ler_config`, desde
  29/10). `RVGEN_PROVEDOR` ou `--provedor` ainda vencem.
- `ClienteOpenAI` (`llm.py`): POST em `/chat/completions` com `model`, `messages`,
  `temperature` 0,2. Falha transitória (429, 5xx, conexão) é repetida até 3 vezes
  (2 s, 4 s, ou o `Retry-After`); estouro de timeout não, porque pode já ter sido
  cobrado. O schema JSON **não** vai para a API (só no prompt); `extrair_json` valida
  e o agente reenvia até 2 vezes.
- Sem `--exemplo`: o modelo não recebe nenhuma CPU de referência.
- Cada chamada tem mensagens novas, sem histórico. Chamadas sequenciais por padrão.
- Sem medida de tempo/custo com luna no repositório (os 17–18 min são do Ollama 14B).
  Gasto fica em `resultado.json` e em `python -m rvgen comparar`.
- GHDL/cocotb/`spec-riscv-test` rodam **só no executor local (Linux/WSL)**; `--executor docker`
  é recusado para o veredito (a imagem só tem binutils). Neste PC não achei `ghdl`, compilador
  RISC-V nem clone `riscv-tests` no PATH: o caminho é WSL2.

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
(`ISAS = ("rv32i","rv32im")`): o juiz passa a rodar 48 programas. Desde 29/10 o
prompt diz que a entidade `cpu` não tem generic (antes mandava declarar
`RV32M_ENABLE`, que o `spec-riscv-test` recusa). Pendências para o IM: o `rvverify`
só roda a etapa RV32M quando há generic, e não há tabela de referência do M em
`specs/`.

## A confirmar com o professor

1. Mesma IA para VHDL e testes (viés só reduzido por contexto).
2. A "outra IA que testa a CPU" é o testbench do bloco `cpu`; a suíte oficial é
   determinística, não IA.
3. Que o juiz do `rvgen` é o `spec-riscv-test` (specs já atualizadas) e se
   "certificado real" precisa ser o `riscv-arch-test`.
