> **ARQUIVADO — plano parcialmente executado, 2026-09-18.**
>
> Este plano de merge nunca foi executado como está. Uma parte dele foi
> aproveitada e o resto foi superado por outra decisão.
>
> **Aproveitado.** A imagem Docker com o toolchain RISC-V e o seu uso como
> oráculo do montador (passos 1 e 3 deste plano) foram trazidos nos commits que
> acrescentam `NFR-RV-05` a `specs/spec.md`, `docker/Dockerfile` e
> `rvverify/tests/test_assembler_oracle.py` (tarefas `TRV-7.7.5` a `TRV-7.7.7`),
> com a `ADR-004` revisada para registrar que o binutils real é cross-check e
> não substituto do montador Python.
>
> **Não executado.** O restante — o merge do branch
> `Implementing-.asm-and-.rm-tests`, a CPU DUT `opus_5_RISCVIM`, a promoção para
> um `tools/riscv/` de topo e os IDs `FR-16`..`FR-29`/`NFR-05` — foi superado
> pela reorganização da `ADR-013`, que resolveu o mesmo problema de estrutura de
> outra forma: cinco pastas de topo, com o montador e o modelo de referência
> promovidos para `rvverify/`. Ver `REPO_MAP.md` e a `ADR-014`.
>
> O texto abaixo é o plano original, preservado sem alteração (princípio 8).

---

# Merge das duas trilhas: `main` ← `Implementing-.asm-and-.rm-tests`

## Contexto

As duas branches divergiram em `f884a4e` ("RISCV32I example") e seguiram em
direções diferentes sem nunca se reencontrar:

| | `main` (12 commits) | `Implementing-.asm-and-.rm-tests` (3 commits) |
|---|---|---|
| Foco | executar a trilha RISC-V até o fim | ampliar a **spec do pipeline** para cobrir CPUs |
| Entregou | `rvverify/` (validador dirigido por manifesto), `entregas/`, RV32IM medido com PPA real, 10 benchmarks, `docs/` | `docker/Dockerfile` (binutils real + Yosys), fases 3b/4b na spec, uma CPU RV32IM gerada do zero |
| tasks.md | 40 de 68 fechadas | 3 de 47 fechadas |
| Requisitos | FR-01..15, NFR-01..04 + namespace `FR-RV-*` | FR-01..**29**, NFR-01..**05** |

O problema concreto: `git merge` cru marcaria como deletados os ~17 mil de
linhas concluídas da `main` (rvverify, entregas, docs, benchmarks, PPA), porque
o branch nunca as viu. E há duplicações reais para resolver — dois geradores de
imagem de programa, dois estilos de harness cocotb, um diretório de teste
copiado em dois lugares.

**Resultado pretendido:** uma `main` que soma o ferramental e a ambição de spec
do branch ao trabalho já verificado, sem duas formas de fazer a mesma coisa, e
com o branch antigo arquivado e removido.

### Decisões já tomadas (confirmadas com o usuário)

1. **A CPU `opus_5_RISCVIM` fica.** Ela não compete com `examples/RISCV32I` nem
   com `examples/rv32i_monociclo`: aquelas são exemplos baixados, verificados e
   funcionais; esta é o *device under test* produzido para exercitar as
   mudanças. Propósitos diferentes, ambos permanecem — em
   `implemetation_tests/`, não em `examples/` nem em `entregas/`.
2. **Os dois montadores ficam**, com papéis distintos: `rv_assembler.py`
   continua o caminho padrão; o binutils real do Docker entra como **oráculo de
   cross-check**.
3. **Branch de integração a partir da `main`**, trazendo arquivo a arquivo. Sem
   merge commit.

---

## O que entra, o que fica de fora

### Entra do branch

| Origem (branch) | Destino (`main`) | Por quê |
|---|---|---|
| `docker/Dockerfile` | `docker/Dockerfile` | A `main` não tem nada equivalente. Base pinada por digest, binutils RISC-V 2.40 + Yosys 0.23, e um `RUN` que falha o build se `as`/`ld`/`objcopy`/`objdump`/`ghdl`/`yosys` não responderem. Fecha NFR-05 e a pendência registrada no ADR-004. |
| `software/tools/build_program.sh`, `bin_to_rm.py`, `rm_to_rom_pkg.py`, `check_dasm_coverage.py` | `tools/riscv/` (promovidos à raiz) | São toolchain, não código de uma CPU específica — o oráculo e o DUT usam os mesmos. `check_dasm_coverage.py` não tem equivalente na `main`. |
| `implemetation_tests/opus_5_RISCVIM/{src,test,specs,software}/` | mesmo caminho | O DUT e seus 10 testbenches de nível de bloco. A `main` só testa em nível de CPU/programa. |
| `specs/spec.md`: FR-16..FR-29, NFR-05, fases 3b e 4b | `specs/spec.md` | **Sem colisão de ID**: a `main` para em FR-15 e usa `FR-RV-*` para a trilha RISC-V, então FR-16+ está livre. Entra quase literal. |
| `specs/plan.md`: seções "Interface de verificação padrão da CPU", "Fase 3b/4b em detalhe", "Toolchain — imagem única (NFR-05)" | `specs/plan.md` | Seções novas; a `main` não as tem. |
| `specs/tasks.md`: tarefas de fase 3b/4b | `specs/tasks.md` | Renumeradas para não colidir com as 68 da `main`. |

### Fica de fora

| O quê | Por quê |
|---|---|
| `RISCV32IM_OPUS_5_InProgress.md` (347 KB) | Dump bruto de transcript de sessão — JSON escapado dentro de markdown. Não é documentação; é ruído de 347 KB no diff de todo mundo. |
| `examples/riscv_base_test/` | **Byte a byte idêntico** a `implemetation_tests/opus_5_RISCVIM/software/riscv_base_test/`. Sobra de uma movimentação de diretório. |
| `**/build/program.elf`, `program.bin` | Binários regeneráveis por `build_program.sh`. Mantêm-se `.dasm`, `.sym`, `.rm` e `toolchain.txt` — texto, revisáveis, e são a procedência. Acrescentar `*.elf`/`*.bin` ao `.gitignore`. |
| `specs/constitution.md`, `plan.md`, `tasks.md` do branch, inteiros | A versão da `main` está estritamente à frente (tem `decisions.md` com 10 ADRs, e a trilha RISC-V inteira). Só as seções nomeadas acima são aproveitadas. |
| `test/lib/riscv_isa.py` | Ver "Duplicações" abaixo. |

---

## Duplicações e como cada uma se resolve

**1. Dois geradores de imagem — os dois ficam, com papéis separados.**

`examples/RISCV32I/tools/rv_assembler.py` (696 linhas, validado por pytest
contra os encodings da spec RISC-V não privilegiada) continua o caminho padrão:
roda no Windows, sem dependência externa, e é código do projeto — logo, entra na
cadeia de rastreabilidade.

O binutils do Docker vira **oráculo**: monta o mesmo `.asm` com o `as` real e
compara palavra a palavra contra a saída do montador Python. Isso é exatamente a
mitigação que o próprio ADR-004 exige ("o montador é código novo e portanto
suspeito") e que hoje só existe como teste do montador contra si mesmo. Novo
teste: `examples/RISCV32I/test/test_assembler_oracle.py`, marcado para pular
quando a imagem Docker não estiver disponível.

Atualizar o ADR-004 com um bloco **Revisão** dizendo que a premissa ("não existe
toolchain RISC-V") deixou de valer, e registrar por que o montador Python
permaneceu mesmo assim.

**2. Dois formatos de imagem — `.rm` e `.ram` são o mesmo formato.**

Ambos são texto, uma palavra de 32 bits por linha em hex, endereço crescente,
comentários com `#`. O `.ram` é o canônico: está no ADR-003, tem 10 imagens
versionadas, é lido por `rv_assembler.read_ram_image` e pelo
`instruction_memory.vhd`. Renomear `bin_to_rm.py` → `bin_to_ram.py`, fazer
emitir `.ram`, e renomear os dois `program.rm` do branch. Um formato, dois
produtores.

**3. Dois harnesses cocotb — divisão por nível, não por design.**

- **Nível de bloco** (ALU, gerador de imediato, unidade de branch…): Makefiles
  próprios, `make SIM=ghdl`. O `rvverify` não faz isso — ele dirige uma CPU
  inteira. Fica como está.
- **Nível de CPU/programa**: `rvverify` é o único caminho. Nenhum testbench de
  CPU novo fora dele.

Escrever essa divisão em `implemetation_tests/opus_5_RISCVIM/README.md`, senão
ela se perde.

**4. Dois `mul_div_unit.vhd` — não é duplicação.**

São de CPUs diferentes (o da `main` é do exemplo verificado de 5 estágios; o do
branch é do DUT). Mas devem ser julgados pelo **mesmo modelo golden**: apontar o
teste de bloco `test_mul_div_unit.py` do DUT para
`examples/RISCV32I/test/reference_model.py`, em vez do modelo inline que ele tem
hoje. Um modelo de referência, dois DUTs.

**5. `riscv_isa.py` vs `rv_assembler.py` — consolidar no segundo.**

`riscv_isa.py` (187 linhas) faz `encode()` e `decode()`; `rv_assembler.py` já faz
os dois (`assemble`, `disassemble_word`) e é o que tem testes de encoding
instrução a instrução. Apagar `riscv_isa.py` e apontar os testes de bloco para
`rv_assembler`. O argumento de "oráculo independente" que justificava
`riscv_isa.py` passa a ser servido pelo binutils real (item 1) — que é
independente de verdade, não outro arquivo do mesmo autor.

---

## Sequência de execução

Um commit por bloco, Conventional Commits, checkbox de `specs/tasks.md` no mesmo
commit (CLAUDE.md).

```
git switch -c integra-trilhas main
```

1. **`build: trazer a imagem docker do toolchain RISC-V`**
   `git checkout Implementing-.asm-and-.rm-tests -- docker/Dockerfile`.
   Corrigir a referência interna a `examples/RISCV32I/compilation/Makefile` —
   esse Makefile ainda existe na `main` e ainda aponta para um xPack em caminho
   Windows não versionado; o comentário do Dockerfile continua correto.
   Verificar: `docker build` + os três `--version` do critério de aceite T0.6.

2. **`feat(tools): promover a cadeia asm -> ELF -> .ram para tools/riscv/`**
   Os quatro scripts, com `bin_to_rm.py` → `bin_to_ram.py` emitindo `.ram` no
   formato do ADR-003.

3. **`test(riscv): cross-check do montador contra o binutils real`**
   `test_assembler_oracle.py`, com skip quando não há Docker. Atualizar ADR-004.

4. **`feat: trazer a CPU RV32IM gerada (DUT das mudanças)`**
   `implemetation_tests/opus_5_RISCVIM/` sem os binários, sem
   `examples/riscv_base_test/`, sem o transcript. Apagar `test/lib/riscv_isa.py`
   e reapontar os testes de bloco para `rv_assembler` e `reference_model`.
   Acrescentar o README explicando a divisão de harness.
   Verificar: rodar os 10 `make` de bloco e conferir exit code — **não inferir
   resultado do código** (CLAUDE.md).

5. **`feat(rvverify): validar a CPU gerada pelo manifesto`**
   `implemetation_tests/opus_5_RISCVIM/cpu.toml`. O encaixe já existe:
   `regs` é `array (0 to 31) of word_t` (1-D, legível pelo VPI do GHDL), e o
   modo `program.mode = "vhdl_constant"` do manifesto já cobre o
   `rom_image_pkg.vhd` gerado.
   **Limite conhecido:** em `vhdl_constant`, `ProgramSpec.loadable` é `False`
   ([`rvverify/manifest.py:190`](rvverify/manifest.py#L190)) — o validador só
   roda o programa embutido. Para rodar os benchmarks da `main` neste DUT,
   `instruction_rom.vhd` precisa de um generic `ROM_INIT_FILE`, seguindo o
   padrão já pronto em
   [`examples/RISCV32I/src/instruction_memory.vhd`](examples/RISCV32I/src/instruction_memory.vhd).
   Fazer nesta tarefa; é a mesma mudança, pequena.

6. **`docs(specs): incorporar fases 3b/4b e o contrato de cobertura`**
   FR-16..FR-29 e NFR-05 em `specs/spec.md`; as três seções novas em
   `plan.md`, com `.rm` reconciliado para `.ram`; tarefas renumeradas em
   `tasks.md`. Atualizar `README.md` e `docs/MUDANCAS.md`.

7. **`docs: registrar a integração das duas trilhas`**
   Um ADR-010 em `specs/decisions.md` com as cinco resoluções de duplicação
   acima — é a decisão que mais custa reconstruir depois.

8. **Arquivar o branch**
   `git tag arquivo/asm-rm-tests Implementing-.asm-and-.rm-tests` e push da tag
   antes de apagar a branch local e remota. Nada se perde; a tag preserva
   inclusive o transcript excluído.

---

## Achado fora do escopo (não corrigir neste merge)

[`entregas/README.md`](entregas/README.md) documenta `python -m rvverify
entregas/seu_nome`, mas **`rvverify/__main__.py` não existe** na `main` — o
comando falha com `No module named rvverify.__main__`. É um furo anterior a este
merge e independente dele. Vale um commit próprio depois; sinalizo aqui para não
alargar o escopo silenciosamente.

---

## Verificação de ponta a ponta

Rodar nesta ordem, **conferindo exit code de cada passo** — nenhuma simulação
conta como "passou" sem GHDL executado de fato (CLAUDE.md):

```bash
# 1. imagem do toolchain
docker build -t spechdl-toolchain -f docker/Dockerfile docker
docker run --rm spechdl-toolchain bash -lc \
  "riscv64-unknown-elf-as --version; ghdl --version; yosys -V"

# 2. suíte do próprio pipeline (montador, manifesto, programas)
pytest -q

# 3. oráculo: montador Python x binutils real, palavra a palavra
pytest -q examples/RISCV32I/test/test_assembler_oracle.py

# 4. não-regressão da trilha RISC-V já concluída na main
pytest -q examples/RISCV32I/test/
pytest -q examples/rv32i_monociclo/test/

# 5. testes de bloco do DUT (10 diretórios)
for d in implemetation_tests/opus_5_RISCVIM/test/*/; do
  [ -f "$d/Makefile" ] && make -C "$d" || echo "FALHOU: $d"
done

# 6. o DUT julgado pelo validador
python -m rvverify implemetation_tests/opus_5_RISCVIM   # ver achado acima

# 7. imagens versionadas continuam em dia com os .asm
python examples/RISCV32I/tools/build_programs.py --check
```

**Critério de aceite do merge:** passos 2, 4 e 7 passam exatamente como na
`main` antes do merge (nenhuma regressão no que já estava verificado), e 1, 3, 5
e 6 passam pela primeira vez. Qualquer falha em 5 ou 6 é informação legítima
sobre o DUT — registrar em `specs/tasks.md`, não mascarar.
