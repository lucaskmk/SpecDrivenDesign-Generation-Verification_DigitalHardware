# rv32im_gabarito

CPU RV32IM monociclo escrita à mão no contrato atual de
[`specs/cpu.md`](../../specs/cpu.md). É o
[`rv32i_gabarito`](../rv32i_gabarito/) mais a extensão M de
[`specs/riscv-rv32m.md`](../../specs/riscv-rv32m.md): MUL, MULH, MULHSU,
MULHU, DIV, DIVU, REM e REMU, combinacionais, então também terminam em um
ciclo. Um arquivo só ([`src/cpu.vhd`](src/cpu.vhd)), sem ROM, RAM nem generic.

Serve para provar que o caminho do M no juiz funciona antes de pedir uma CPU
IM para a IA: se esta CPU reprovar, o defeito está no juiz ou na spec.

## Resultado (06/11/2026, imagem `docker/veredito`)

| Execução | Programas | Resultado |
|---|---|---|
| `--isa rv32im` (IM completo) | 40 `rv32ui` + 8 `rv32um` | **48/48** |
| `--isa rv32im --tests div,divu,mul,mulh,mulhsu,mulhu,rem,remu` (só o M) | 8 `rv32um` | **8/8** |
| `--isa rv32i` (só o I) | 40 `rv32ui` | **40/40** |
| controle: `rv32i_gabarito` (sem M) com os 8 do M | 8 `rv32um` | **0/8**, como esperado |

O controle mostra que os programas `rv32um` exercitam mesmo o M: uma CPU
sem M reprova todos.

Não existe CPU "só M": pelo manual da ISA, o M é uma *extensão* de uma base
inteira, e os programas `rv32um` do `riscv-tests` usam instruções do I para
montar os valores e conferir o resultado. "Testar só o M" é rodar só os 8
programas `rv32um` numa CPU IM, como na segunda linha.

Da raiz do repositório (no Git Bash do Windows, veja as variantes de `-v` em
[`docker/veredito/README.md`](../../docker/veredito/README.md)):

```bash
docker run --rm -v "$PWD:/repo" -w /repo rvgen-veredito \
    spec-riscv-test --cpu cpus/rv32im_gabarito --riscv-tests /opt/riscv-tests \
    --isa rv32im --out out/im_gabarito
```

## `rvverify`

`python -m rvverify cpus/rv32im_gabarito --etapa rv32i` passa os 24 casos
RV32I (veredito `parcial`). A etapa RV32M do `rvverify` é **pulada**: ela só
roda quando o `cpu.toml` declara `rv32m_generic`, e o contrato atual proíbe
generic. Para o `rvgen` isso não importa (o juiz é o `spec-riscv-test`); para
as entregas de alunos é uma decisão pendente com o professor.
