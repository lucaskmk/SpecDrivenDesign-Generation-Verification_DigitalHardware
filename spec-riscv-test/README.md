# spec-riscv-test

Verificador Cocotb para CPUs RV32I que executa os programas oficiais em
`riscv-tests/isa/rv32ui`. Ele usa somente a interface definida em
[`../specs/cpu.md`](../specs/cpu.md): a ROM e a RAM são modelos externos; a
CPU não precisa (nem deve) instanciar memória.

## Pré-requisitos

```bash
cd spec-riscv-test
python -m venv .venv
.venv/bin/pip install -e .
```

Também é necessário um compilador que aceite `-march=rv32i -mabi=ilp32`, por
exemplo `riscv64-unknown-elf-gcc` ou `riscv32-unknown-elf-gcc`, e o GHDL. O
wrapper usa os arquivos de teste oficiais, porém fornece seu ambiente mínimo
sem CSRs/ECALL: o `env/p` padrão do upstream exige privilégios que
`specs/cpu.md` explicitamente deixa fora de escopo.

## Executar

Na raiz deste repositório:

```bash
spec-riscv-test --cpu entregas/corsi_v3 --riscv-tests riscv-tests \
  --isa rv32i --out spec-riscv-test/out
```

Por padrão, o comando compila e executa todos os testes `rv32ui-p-*`.
Durante depuração, restrinja a seleção:

```bash
spec-riscv-test --cpu entregas/corsi_v3 --riscv-tests riscv-tests \
  --tests add,addi,srl,sra --out spec-riscv-test/out
```

Use `--isa rv32im` para acrescentar `mul`, `mulh`, `mulhsu`, `mulhu`, `div`,
`divu`, `rem` e `remu`. Os demais perfis do upstream não são aceitos porque o
contrato atual não inclui extensões C/F/A, CSRs ou modos privilegiados.

Cada teste gera `out/<nome>/report.json`; o resumo de toda a rodada fica em
`out/report.json`. Ambos são JSON estável e deliberadamente conciso para que
um LLM consiga decidir o que corrigir. Uma falha de compilação do VHDL é
reportada uma vez, com arquivo, linha, coluna e mensagem do GHDL. Uma falha de
programa informa o teste, o PC, o ciclo e o valor escrito em `tohost`.

Os programas são relinkados pelo wrapper no endereço zero, compatível com o
reset exigido pelo contrato da CPU. `tohost` é descoberto na tabela de símbolos
do ELF; escrever `1` aprova e outro valor ímpar sinaliza a falha interna do
programa oficial.
