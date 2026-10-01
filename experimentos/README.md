# Experimentos — CPUs geradas por IA

Cada pasta aqui é **uma CPU RISC-V gerada por um modelo de linguagem** com o
`rvgen` (`python -m rvgen gerar`) e julgada pelo `rvverify`. A pasta guarda a
CPU e a prova de como ela foi feita: qual modelo, com qual contrato, em
quantas iterações, a que custo e com que veredito. É o registro que sustenta
uma comparação entre modelos (ADR-019).

CPUs de **alunos** não entram aqui: elas vão para [`entregas/`](../entregas/).
`python -m rvverify` sem argumento valida só `entregas/`; um experimento se
valida apontando a pasta dele.

## Estrutura de um experimento

```text
experimentos/<nome>/
├── architecture.json          decomposição em blocos proposta pelo modelo (com justificativa)
├── descricao.md               só com --descricao: o texto pedido (NÃO verificado pelo rvverify)
├── cpu.toml                   manifesto do validador, gerado SEM modelo, pelo contrato do tipo
├── src/*.vhd                  o VHDL que o modelo escreveu (um bloco por arquivo)
└── .rvgen/
    └── sessao-AAAAMMDD-HHMMSS/    uma por execução de `gerar` (a mais recente é a que vale)
        ├── contrato.txt           o prompt de sistema exato desta execução
        ├── sessao.jsonl           cada chamada ao modelo (mensagens, resposta, tokens, tempo)
        │                          e cada execução do rvverify, em ordem
        ├── rvverify/*.json        o relatório completo de cada execução do validador
        ├── resultado.json         veredito, placar, iterações, tokens, tempo, modelo
        ├── sim/                   logs do GHDL por caso      (fora do Git)
        └── build/                 biblioteca compilada do GHDL (fora do Git)
```

Uma sessão que parou com erro (modelo fora do ar, validador sem relatório)
não tem `resultado.json`; ela fica como histórico e o `comparar` a ignora.

## Criar, validar e comparar

O passo a passo completo está em [`rvgen/README.md`](../rvgen/README.md). Em
resumo:

```bash
python -m rvgen gerar ia_mono_qwen14b --tipo monociclo --isa rv32im
```
```bash
docker run --rm -v "${PWD}:/job" spechdl-toolchain python3 -m rvverify experimentos/ia_mono_qwen14b --sem-cor
```
```bash
python -m rvgen comparar
```

Um nome sem diretório (`ia_mono_qwen14b`) já grava em
`experimentos/ia_mono_qwen14b/`.

## O que vai para o Git

Tudo, menos `sim/` e `build/` de cada sessão (`.gitignore`). O VHDL, o
manifesto, o contrato e as sessões versionados são o que permite a qualquer
pessoa conferir uma comparação, e repetir a geração com a mesma versão do
prompt. Uma tabela de modelos sem esses arquivos é afirmação sem prova
(princípio 10 da constituição).
