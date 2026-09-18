# `software/` — artefatos de programa desta CPU

Esta pasta é **anterior** à reconciliação descrita em
[`../specs/spec.md`](../specs/spec.md), seção "Reconciliação com a spec
vigente do repositório". Ela foi produzida pela fase 3b do contrato do branch
`Implementing-.asm-and-.rm-tests`, que montava programas de teste com o
binutils RISC-V real (assembly → ELF → `.rm` → `rom_image_pkg.vhd`).

**Está preservada de propósito** (constituição, princípio 8: nada é removido),
e os comentários `REQ:` dentro dos arquivos continuam citando os IDs
`pipeline:FR-18` a `FR-22` daquele contrato. Esses IDs **não foram
reescritos**: eles registram sob qual requisito cada arquivo foi de fato
gerado. Reescrevê-los para os IDs de hoje falsificaria a procedência.

## O que ainda está no caminho ativo

| arquivo | papel hoje |
|---|---|
| `riscv_base_test/rom_image_pkg.vhd` | imagem **default** da ROM (`ROM_INIT_FILE = ""`, FR-13). É o que a fase 5 sintetiza e o que a suíte de bloco `test/instruction_rom/` verifica. |
| `riscv_base_test/program.rm`, `program.dasm` | oráculos da suíte `test/instruction_rom/`: ela confere a ROM elaborada contra o `.rm` e contra o disassembly do binutils. |
| `ext_m_test/*` | programa de cobertura da extensão M e seu `expected_ram.json` derivado à mão. |

## O que saiu do caminho ativo

A verificação em nível de programa passou a ser feita pela suíte de
conformidade de `rvverify`, cujos programas são montados por
`rvverify/asm.py` (ADR-004) e cujos valores esperados vêm de
`rvverify/reference.py`. Portanto:

- `tools/build_program.sh`, `tools/bin_to_rm.py`, `tools/rm_to_rom_pkg.py` e
  `tools/check_dasm_coverage.py` **não são executados** pela verificação
  atual. Continuam versionados porque são o que produziu os `.rm` acima, e
  porque regenerar `rom_image_pkg.vhd` a partir de um novo `.S` ainda passa
  por eles. Exigem Docker (binutils RISC-V), ver `../../docker/Dockerfile`.
- `riscv_base_test/` aqui não tem `src/program.S` nem `expected_ram.json`: a
  fixture golden completa vivia em `examples/riscv_base_test/` na raiz, pasta
  que a ADR-013 eliminou. O que sobrou é o suficiente para os oráculos da
  suíte de bloco, e nada no caminho ativo depende do resto.
