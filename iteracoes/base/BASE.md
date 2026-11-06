# Base das specs (ponto de partida das iterações)

Cópia de `specs/` feita em 29/10/2026, a partir do commit `a3d29d6` mais as
correções daquele dia (juiz do `rvgen` = `spec-riscv-test`, prompt sem generic,
`vhdl.md` sem a regra `-- REQ:`).

Esta pasta não se edita. Cada iteração nasce de uma cópia dela (ou de outra
iteração) em `iteracoes/it-NNN/`, e o app `python -m iteracoes` compara tudo
com ela. Para voltar ao ponto de partida, basta criar uma iteração nova a
partir da base.

Acréscimo em 06/11/2026: `specs/riscv-rv32m.md` (referência da extensão M).
Só vai para a IA quando o `cpu.md` da iteração declara RV32IM. Nenhum outro
arquivo da base mudou.
