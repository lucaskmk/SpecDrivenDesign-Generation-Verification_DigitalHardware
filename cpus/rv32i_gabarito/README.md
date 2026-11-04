# rv32i_gabarito

CPU RV32I monociclo no contrato atual de [`specs/cpu.md`](../../specs/cpu.md):
a entidade `cpu`, com as 9 portas do barramento virtual, em um único arquivo
([`src/cpu.vhd`](src/cpu.vhd)). Não tem ROM, RAM nem generic. Uma instrução
termina a cada borda de subida.

Ela serve para três coisas:

1. **Gabarito do juiz.** Se o validador reprovar esta CPU, o defeito está no
   validador. Foi assim que apareceram os dois defeitos corrigidos no
   `rvverify/tb_virtual.py` (endereço de dados lido antes de a instrução
   assentar, e relatório de falha num formato que o `feedback` não lia).
2. **Ponto de partida** para quem escreve uma CPU do zero (`entregas/`).
3. **Referência de tamanho e de estilo** para o que o `rvgen` deveria gerar.

## Resultado

| Juiz | Resultado |
|---|---|
| `spec-riscv-test` (juiz do `rvgen`) | 40/40 programas `rv32ui`, `"status": "passed"` |
| `rvverify --etapa rv32i` | 24/24 casos RV32I (veredito `parcial`, ver abaixo) |

O `spec-riscv-test` roda na imagem [`docker/veredito`](../../docker/veredito/README.md)
(GHDL 2.0.0, cocotb 2.0.0, `gcc-riscv64-unknown-elf` 12.2.0, `riscv-tests` no
commit `3df703c`), da raiz do repositório:

```bash
docker build -t rvgen-veredito docker/veredito
docker run --rm -v "$PWD:/repo" rvgen-veredito   spec-riscv-test --cpu cpus/rv32i_gabarito --riscv-tests /opt/riscv-tests --isa rv32i --out out/gabarito
```

O relatório fica em `out/gabarito/report.json` (no Git Bash do Windows, ver
as variantes de `-v` no README da imagem). O commit `644cba9` registra o
mesmo 40/40.

O `rvverify`:

```bash
python -m rvverify cpus/rv32i_gabarito --etapa rv32i
```

24/24 casos RV32I aprovados (GHDL 2.0, cocotb 2.0, imagem
`rafaelcorsi/pl-descomp-cocotb`, 29/10/2026). O teste
`rvverify/tests/test_virtual.py` refaz essa prova e também confere que uma
cópia com defeito é reprovada com diagnóstico.

Mesmo com 24/24 o veredito do `rvverify` não sai `aprovado`: com
`--etapa rv32i` ele é `parcial` (só uma etapa foi pedida) e sem a opção é
`incompleto` (a etapa RV32M exige um generic, e o contrato atual não tem
generic). Ver `entregas/README.md`.

## O que ainda não foi verificado

- Síntese no Quartus.

FENCE, ECALL e EBREAK funcionam como NOP; CSRs, interrupções e acessos
desalinhados estão fora do contrato.
