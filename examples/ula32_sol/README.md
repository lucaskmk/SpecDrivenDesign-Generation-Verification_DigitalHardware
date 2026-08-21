# ULA de 32 bits

ULA combinacional MIPS-style gerada pelo fluxo Spec Driven Development.

## Estrutura

- `specs/spec.md` e `specs/spec.json`: requisitos aprovados.
- `specs/architecture.json`: decomposicao e trade-off arquitetural.
- `src/ula32.vhd`: hardware VHDL sintetizavel.
- `test/test_ula32.py`: verificacao cocotb dirigida e aleatoria.
- `test/Makefile`: execucao cocotb sobre GHDL.
- `verification/`: resultados registrados da verificacao.

## Interface e controles

| Controle | Operacao |
|---|---|
| `0000` | AND |
| `0001` | OR |
| `0010` | ADD |
| `0110` | SUB |
| `0111` | SLT com sinal |
| `1100` | NOR |

Entradas: `a[31:0]`, `b[31:0]`, `alu_control[3:0]`.
Saidas: `result[31:0]`, `zero`.

## Simulacao

Requer GHDL, Python 3.11+, cocotb e Make. A partir desta pasta:

```sh
make -C test
```

Ou, sem instalar o toolchain localmente, usando a imagem de referencia a
partir desta pasta:

```sh
docker run --rm -v "${PWD}:/work" -w /work/test \
  rafaelcorsi/pl-descomp-cocotb make SIM=ghdl
```

O teste cobre casos de fronteira, todos os controles invalidos e 200 vetores
pseudoaleatorios deterministas para cada operacao. O GHDL tambem grava a forma
de onda em `test/ula32.ghw`.
