# Entregas — onde a CPU do aluno entra

Cada entrega é **uma pasta** dentro deste diretório, com um `cpu.toml` na raiz.
O `rvverify` descobre sozinho toda pasta que tenha um `cpu.toml` e roda a suíte
de conformidade em cada uma.

```
entregas/
├── _modelo/              ← copie esta pasta para começar
├── joao_silva/
│   ├── cpu.toml
│   └── src/cpu.vhd (+ os blocos que você quiser)
└── maria_souza/
    ├── cpu.toml
    └── src/*.vhd
```

## O contrato

A CPU é a entidade `cpu` de [`specs/cpu.md`](../specs/cpu.md): 9 portas
(`clk`, `rst`, `instr_addr`, `instr_data`, `data_addr`, `data_write`,
`data_width`, `data_write_data`, `data_read_data`), **sem generic e sem
memória dentro**. O validador faz o papel da ROM e da RAM:

- lê `instr_addr` e responde com a instrução em `instr_data`;
- lê `data_addr` e responde com a palavra da RAM em `data_read_data`;
- quando `data_write = '1'`, grava na borda de subida o byte, a meia palavra
  ou a palavra indicada por `data_width`.

A RAM virtual fica em `0x00FC8100` e tem 512 bytes
([`rvverify/memmap.py`](../rvverify/memmap.py)); stores fora dela são
ignorados e aparecem como aviso no relatório.

## Como entregar

```bash
cp -r entregas/_modelo entregas/seu_nome
# escreva entregas/seu_nome/src/cpu.vhd e troque o TODO do cpu.toml
```

Comece de [`cpus/rv32i_gabarito`](../cpus/rv32i_gabarito/): uma CPU RV32I
monociclo em um arquivo, que já passa nos 24 casos RV32I.

## Como rodar

```bash
python -m rvverify entregas/seu_nome                       # uma entrega
python -m rvverify entregas/                               # todas
python -m rvverify entregas/seu_nome --keep --workdir rel  # guarda os logs
```

Precisa de Linux/WSL2 com GHDL e cocotb 2 (`pip install -e ".[sim]"`), ou da
imagem Docker das aulas, `rafaelcorsi/pl-descomp-cocotb`.

## O que o veredito quer dizer hoje

- **RV32I**: 24 casos, com valores esperados vindos do modelo de referência
  em Python (`rvverify/reference.py`).
- **RV32M**: a etapa só roda quando o manifesto declara `rv32m_generic`. No
  contrato atual a entidade não tem generic, então uma CPU RV32I sai como
  `incompleto` mesmo com 24/24 na base. É um limite conhecido, a resolver
  quando o RV32IM entrar.
- O veredito oficial de uma CPU gerada pelo `rvgen` é do `spec-riscv-test`
  (programas oficiais do `riscv-tests`), não deste validador.

## Uma restrição do GHDL que vale lembrar

Mantenha a guarda de faixa e o índice de um array na mesma expressão
condicional. Com

```vhdl
signal in_range : boolean;
in_range <= word_index < N;                              -- ERRADO
data_out <= memory(word_index) when in_range else ...;
```

o sinal `in_range` atrasa um delta em relação a `word_index`, e um endereço
fora de faixa indexa o array antes de a guarda alcançar:
`ghdl:error: index (...) out of bounds`.

## Versionamento

As pastas de entrega ficam versionadas junto com o resto. Se você preferir
manter as suas fora do git, acrescente ao `.gitignore` da raiz:

```
entregas/*
!entregas/_modelo/
!entregas/README.md
```
