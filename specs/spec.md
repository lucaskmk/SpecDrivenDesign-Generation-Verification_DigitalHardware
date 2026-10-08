# Especificação do fluxo de geração

## Entrada

O fluxo começa com:

```bash
python -m rvgen gerar <entrega>
```

O comando valida tipo, ISA, provedor de modelo e executor antes de chamar a
LLM.

## Geração e validação

1. A LLM produz o inventário das instruções da ISA e uma breve explicação de
   cada uma; ele é salvo em `architecture.json`.
2. O agente propõe uma decomposição em blocos e dependências, cobrindo esse
   inventário.
3. O agente gera VHDL, um arquivo por bloco.
4. Opcionalmente, `--testes-componentes` gera e executa testbenches cocotb.
5. Com `--gates-componentes`, cada bloco deve compilar e passar testes antes
   da geração do próximo.
6. Uma falha de componente passa por triagem: erro de testbench corrige o
   Python; asserção funcional corrige o VHDL; caso ambíguo não altera arquivos.
7. `--regressoes-componentes` preserva casos que revelaram falhas já
   corrigidas.
8. `rvverify` executa a validação integrada e produz o veredito final.

## Artefatos

Cada sessão registra em `.rvgen/sessao-*/` o contrato, arquitetura, respostas
da LLM, testbenches, resultados, logs e relatórios JSON. A infraestrutura de
memória é privada do `rvverify` e não aparece em `architecture.json`.
