# Concluir a ADR-013, trazer o oráculo Docker do montador, e documentar a estrutura do repositório

## Contexto

O repositório já tem uma decisão registrada — `specs/decisions.md`, **ADR-013**
("Estrutura do repositório: validador no centro, trilha A no legado") — que
especifica a estrutura de 5 pastas que o usuário está pedindo (o pedido inicial
de "mover cpus/ para dentro de examples/" foi checado contra essa ADR e
**revertido**: a ADR já decidiu, com justificativa registrada, tirar as CPUs de
`examples/` porque aquela pasta misturava exercícios da trilha A com as CPUs de
referência RISC-V, e o nome `RISCV32I` não sinalizava que era o alvo editável
do aluno). A investigação confirmou que o commit `2091e0d` ("tenatndo
restruturar", HEAD atual) executou **só metade** dessa ADR — falta criar
`legado/` e promover o montador/modelo de referência para `rvverify/`.

Separadamente, existe um plano de merge antigo e abandonado
(`hey-claude-please-plan-jolly-bird.md`) que nunca foi executado. A maior parte
dele foi de fato superada pela reorganização da ADR-013 (a CPU DUT
`opus_5_RISCVIM`, a promoção para um `tools/riscv/` de topo, os IDs
FR-16..FR-29/NFR-05 daquele branch). **Mas uma parte dele continua válida e o
usuário pediu para trazê-la**: a imagem Docker com o toolchain RISC-V real
(`binutils` cruzado + Yosys), usada como **oráculo independente** para
conferir, palavra a palavra, a saída do montador Python
(`cpus/rv32i_pipeline/tools/rv_assembler.py`, que este mesmo plano promove para
`rvverify/asm.py`) contra um assemblador de verdade. Essa peça já existe pronta
no branch `Implementing-.asm-and-.rm-tests` (commit `a199070`, arquivo
`docker/Dockerfile`, 45 linhas, lido por completo) e só precisa ser adaptada
aos caminhos atuais.

Importante: **CLAUDE.md exige spec aprovada antes de código.** O
`docker/Dockerfile` original cita `NFR-05`/`T0.6` — IDs de requisito que
existem só no branch abandonado, não em `specs/spec.md` desta `main` (que vai
de NFR-RV-01 a NFR-RV-04). Por isso este plano começa essa parte por uma
tarefa de spec (`NFR-RV-05`), antes de qualquer código do oráculo — não é
possível simplesmente copiar o Dockerfile do branch e citar um requisito que
não existe aqui.

**Decisões já confirmadas com o usuário** (não re-abrir):
1. Concluir a ADR-013 como decidida — CPUs continuam em `cpus/`, não voltam
   para `examples/`.
2. Criar `legado/` e mover a trilha A original para lá, como parte deste plano.
3. Não mexer em `implemetation_tests/` (é só cache git-ignorado de simulações
   antigas, sem fonte versionada — fora de escopo; o DUT completo
   `opus_5_RISCVIM` com `src/`/`specs/` existe de verdade no branch
   `Implementing-.asm-and-.rm-tests`, commit `fdc589e`, mas trazê-lo não foi
   pedido — só o oráculo Docker do montador).
4. Criar `REPO_MAP.md` novo na raiz (em português); `docs/mapa-do-projeto.html`
   fica como está.
5. Trazer a infraestrutura Docker do montador (do plano antigo) como
   cross-check do montador Python, formalizada como requisito de spec antes de
   implementada.

## Regras a seguir (CLAUDE.md)

Uma tarefa = um commit, Conventional Commits, checkbox de `specs/tasks.md`
marcado no mesmo commit. Nenhuma simulação conta como "passou" sem GHDL/Docker
rodado de fato e exit code conferido. A sequência abaixo tem 15 commits
pequenos, cada um com uma preocupação só, na ordem em que devem ser aplicados
(cada um depende do anterior).

## Sequência de execução

**Commit 0 — `docs(tasks): quebrar a conclusão da ADR-013 em subtarefas`**
Adicionar em `specs/tasks.md`, na Fase RV-7 (após `TRV-7.1`), as tarefas
`TRV-7.7.1` a `TRV-7.7.12` (uma por commit abaixo), cada uma com `REQ:` (a
ADR ou o novo NFR-RV-05, conforme o caso) e um `ACEITE:` = o critério de
verificação listado no commit correspondente.

**Commit 1 (TRV-7.7.1) — `fix(specs): atualizar plan.md e spec.md para cpus/rv32i_pipeline`**
Editar `specs/plan.md:204` e `specs/spec.md:115,120,121,129,137`:
`examples/RISCV32I/...` → `cpus/rv32i_pipeline/...`. Não tocar ainda
`specs/spec.md:256,286` (viram `rvverify/asm.py`/`rvverify/reference.py` no
Commit 4c) nem `specs/plan.md:13,128-129,137` (viram `legado/...` no
Commit 3).
Verificação: `grep -rn "examples/RISCV32I" specs/plan.md specs/spec.md`.

**Commit 2 (TRV-7.7.2) — `refactor(legado): mover a trilha A da raiz para legado/`**
`git mv`: `src/spechdl/` → `legado/src/spechdl/`; `templates/` →
`legado/templates/`; `tests/` → `legado/tests/`; `scripts/` →
`legado/scripts/`; `.streamlit/` → `legado/.streamlit/`;
`abrir_formulario.bat` → `legado/abrir_formulario.bat`. Editar
`CLAUDE.md:85` (`templates/rubrica.md` → `legado/templates/rubrica.md`).
Registrar no corpo do commit que `abrir_formulario.bat` passa a assumir um
`.venv` local a `legado/` (antes assumia um na raiz ao lado do `.bat`) —
mudança real de uso, não silenciar isso.
Verificação: `git status --short` só mostra renames + os dois arquivos
editados. Não afirmar que a trilha A "continua funcionando" — ela não tem
testes (`docs/ESTADO-TRILHA-A.md`); só o `git mv` preserva o conteúdo.

**Commit 3 (TRV-7.7.3) — `refactor(legado): mover exemplos remanescentes da trilha A e remover lixo de examples/riscv_base_test`**
`git mv`: `examples/ula32_sol/` → `legado/ula32_sol/`;
`examples/ula32_terra/` → `legado/ula32_terra/`;
`examples/toolchain_smoketest/` → `legado/toolchain_smoketest/`.
Apagar (limpeza de working tree, não é `git mv` — mencionar no corpo do
commit): `examples/riscv_base_test/` (só tem `build/program.o`,
git-ignorado). Depois disso `examples/` fica vazio e some da árvore.
Editar: `.github/workflows/toolchain-smoketest.yml` (os dois `paths:` e o
`run:` de `examples/toolchain_smoketest/...` → `legado/toolchain_smoketest/...`);
`CLAUDE.md:63`; `specs/plan.md:13,128-129,137`; `README.md` (a linha
`src/ e examples/    trilha genérica antiga e smoke tests` →
`legado/  trilha genérica antiga (SpecHDL Streamlit) e smoke tests`).
Verificação: `git ls-files examples/` vazio; `grep -rn
"examples/toolchain_smoketest\|examples/ula32"` só aparece em docs tratados
no Commit 8 e em blocos `ACEITE` históricos já fechados em `specs/tasks.md`
(não tocar). Revisar manualmente o YAML editado — não há como confirmar que
o CI passa sem disparar um workflow de verdade; sinalizar isso ao revisar o
diff.

**Commit 4a (TRV-7.7.4a) — `refactor(rvverify): promover rv_assembler.py e reference_model.py para rvverify/asm.py e rvverify/reference.py`**
Maior risco da sequência de reorg — muda a direção de dependência que toda a
suíte usa. `git mv`: `cpus/rv32i_pipeline/tools/rv_assembler.py` →
`rvverify/asm.py`; `cpus/rv32i_pipeline/test/reference_model.py` →
`rvverify/reference.py`. Reescrever `rvverify/_ferramentas.py` (32 linhas,
lido por completo): remover `sys.path.insert` e `import reference_model as
ref` / `import rv_assembler` (linhas 17–28), trocar por `from . import asm
as rv_assembler` e `from . import reference as ref`; manter `EXAMPLE_ROOT` e
`PROGRAMS_DIR` (continuam em `cpus/rv32i_pipeline`, onde ficam os programas
de exemplo); remover `TOOLS_DIR`/`REFERENCE_DIR` do `__all__` (nada mais os
usa, confirmado por grep). Editar `rvverify/conformance.py:51`: import
relativo `from .asm import (...)`. Editar
`rvverify/tests/test_generic_smoke.py:55`,
`test_nao_aprova_em_vazio.py:65`, `test_feedback.py:201`: mesmo ajuste.
Verificação (rodar de verdade): `python -c "import rvverify, rvverify.asm,
rvverify.reference, rvverify.conformance"` sem `ModuleNotFoundError`, depois
`pytest rvverify/tests -q` com exit code conferido. **Não avançar para o
Commit 4b sem essa suíte verde.**

**Commit 4b (TRV-7.7.4b) — `fix(cpus): atualizar imports de rv_assembler/reference_model para rvverify.asm/rvverify.reference`**
Editar (troca mecânica de import + remoção do `sys.path.insert` que só
existia para achar `rv_assembler`/`reference_model`, mantendo qualquer outro
que sirva a outro propósito, ex. `rvverify.builder`):
`cpus/rv32i_pipeline/test/rv_build.py` (+ docstring linha 231),
`rv_m_cases.py`, `test_programs.py`, `test_rv32i_baseline.py`,
`test_rv32m_div.py`, `test_rv32m_mul.py`, `test_rv32m_integration.py`,
`test_toolchain.py` (+ docstring linha 14),
`cpus/rv32i_pipeline/tools/build_programs.py` (+ docstrings linhas 2,16-17).
Verificação: `pytest cpus/rv32i_pipeline/test -q` rodado de verdade contra
GHDL/cocotb, exit code conferido; `grep -rn "import rv_assembler\|import
reference_model" cpus/` vazio.

**Commit 4c (TRV-7.7.4c) — `docs(cpus): atualizar rv32i_monociclo, RELATORIO.md e entregas/README.md para a nova localização do montador/modelo`**
Editar: `cpus/rv32i_monociclo/test/test_monociclo.py` (imports + docstrings
linhas 9,15 + log linha 163); `cpus/rv32i_monociclo/README.md:116`;
`cpus/rv32i_pipeline/RELATORIO.md:89,96,459,479`; `entregas/README.md` (as
duas linhas de tabela que citam `rvverify/_ferramentas.py +
cpus/rv32i_pipeline/tools/rv_assembler.py` e
`cpus/rv32i_pipeline/test/reference_model.py`);
`cpus/rv32i_pipeline/src/instruction_memory.vhd:30` (comentário);
`cpus/rv32i_pipeline/src/mul_div_unit.vhd:33` (comentário);
`specs/spec.md:256,286`.
Verificação: `grep -rn "rv_assembler\.py\|reference_model\.py"
--include=*.md --include=*.vhd --include=*.py .` sem sobras; `pytest
cpus/rv32i_monociclo/test -q` rodado de verdade, exit code conferido.

**Commit 5 (TRV-7.7.5) — `docs(spec): registrar NFR-RV-05, oráculo de montagem via toolchain real`**
Antes de trazer qualquer código Docker (regra do CLAUDE.md: spec antes de
código). Editar `specs/spec.md`: acrescentar `NFR-RV-05` logo após
`NFR-RV-03` (linha 322), no mesmo formato EARS dos vizinhos, ex.:
> **NFR-RV-05**: THE SYSTEM SHALL disponibilizar uma imagem de container
> (`docker/Dockerfile`) com um assemblador RISC-V cruzado real
> (`riscv64-unknown-elf-as`/`ld`/`objcopy`/`objdump`) e o Yosys, e SHALL
> usá-la como oráculo independente para conferir, palavra a palavra, a saída
> do montador Python (ADR-004) contra pelo menos um programa de cada
> categoria de instrução suportada; a ausência da imagem SHALL apenas pular
> essa conferência (marcada como não executada), nunca bloquear a suíte
> principal — o montador Python continua sendo o caminho autocontido e
> testável por pytest.

Ajustar o título da seção (linha 308) para deixar claro que `NFR-RV-04` fica
na seção do validador (não renumerar nada existente, só anotar que a
numeração não é contígua por seção). Flipar `- [ ] TRV-7.7.5` → `- [x]`.
Verificação: releitura do trecho para confirmar formato EARS consistente
com `NFR-RV-01..04`.

**Commit 6 (TRV-7.7.6) — `build: trazer a imagem docker do toolchain RISC-V (NFR-RV-05)`**
Trazer `docker/Dockerfile` do branch `Implementing-.asm-and-.rm-tests`
(`git show Implementing-.asm-and-.rm-tests:docker/Dockerfile`, 45 linhas, já
lido por completo — base `rafaelcorsi/pl-descomp-cocotb` pinada por digest,
`binutils-riscv64-unknown-elf 2.40` + `yosys 0.23`, `RUN` que falha o build
se `as`/`ld`/`objcopy`/`objdump`/`ghdl`/`yosys` não responderem). Adaptar ao
estado atual do repositório:
- Trocar a referência de requisito no comentário de cabeçalho de `NFR-05,
  T0.6` (IDs do branch abandonado, não existem aqui) para `NFR-RV-05`
  (Commit 5).
- Trocar o exemplo de aceite `make -C examples/toolchain_smoketest/test/`
  para `make -C legado/toolchain_smoketest/test/` (caminho pós-Commit 3).
- Conferir se o comentário sobre `examples/RISCV32I/compilation/Makefile`
  (caminho xPack não versionado) ainda se aplica em
  `cpus/rv32i_pipeline/compilation/Makefile` e ajustar o caminho citado.
Flipar `- [ ] TRV-7.7.6` → `- [x]`.
Verificação (rodar de verdade, não inferir): `docker build -t
spechdl-toolchain -f docker/Dockerfile docker` e depois `docker run --rm
spechdl-toolchain bash -lc "riscv64-unknown-elf-as --version; ghdl
--version; yosys -V"` — os três precisam responder. Se Docker não estiver
disponível no ambiente de quem aplica este commit, registrar isso
explicitamente em vez de presumir que o build passaria.

**Commit 7 (TRV-7.7.7) — `test(rvverify): oráculo do montador contra o binutils real (NFR-RV-05)`**
Adicionar `rvverify/tests/test_assembler_oracle.py`: monta o mesmo `.asm`
(usar um dos programas versionados em `cpus/rv32i_pipeline/programs/`, um
por categoria de instrução coberta) com `rvverify.asm.assemble(...)`
(assinatura já conferida: `assemble(text: str, base_address: int = 0,
allow_m: bool = True, ...) -> list[int]`) e separadamente com
`riscv64-unknown-elf-as`/`objcopy`/`objdump` dentro do container
`spechdl-toolchain` (via `docker run`), extrai as palavras de `.text` e
compara palavra a palavra contra a saída do montador Python. Pular o teste
(`pytest.mark.skip`/`pytest.skip` condicional) quando `docker` não estiver
no PATH ou a imagem `spechdl-toolchain` não existir — nunca falhar a suíte
principal por isso, conforme `NFR-RV-05`. Marcar `# REQ: NFR-RV-05` no
topo do arquivo (convenção do CLAUDE.md para testbenches/testes gerados).
Atualizar `specs/decisions.md` ADR-004: acrescentar um bloco **Revisão**
(formato livre, ao final da ADR, sem editar o texto histórico acima) dizendo
que a premissa "não existe toolchain RISC-V" deixou de valer com a imagem
Docker (Commit 6), mas o montador Python permanece o caminho principal —
autocontido, sem instalação na máquina do usuário, testável por pytest sem
Docker — e o binutils real vira oráculo de cross-check opcional, não
substituto.
Flipar `- [ ] TRV-7.7.7` → `- [x]`.
Verificação (rodar de verdade): com Docker disponível, `pytest
rvverify/tests/test_assembler_oracle.py -v` executado e exit code
conferido — reportar concretamente se cada palavra bateu, não apenas "o
teste não quebrou". Sem Docker, confirmar que o teste é pulado (não
falha) e reportar isso como tal, não como "passou".

**Commit 8 (TRV-7.7.8) — `docs: corrigir links quebrados em MUDANCAS.md, mudancas-riscv.html e ESTADO-TRILHA-A.md`**
Tratamento diferenciado (convenção já usada em `docs/MUDANCAS.md` §7: docs
antigos ganham nota, não são reescritos):
- `docs/MUDANCAS.md`: corrigir os links markdown relativos hoje quebrados
  (`../examples/RISCV32I/RELATORIO.md` e os 3 links de `src/*.vhd`,
  `programs/README.md` → `../cpus/rv32i_pipeline/...`). Manter a prosa
  histórica intacta; acrescentar uma frase no fim da tabela do §6 dizendo
  que `tools/rv_assembler.py`/`test/reference_model.py` foram promovidos
  para `rvverify/asm.py`/`rvverify/reference.py` (ADR-013) e que agora há um
  oráculo Docker opcional (NFR-RV-05, ADR-004 Revisão).
- `docs/mudancas-riscv.html`: corrigir os comandos literais para
  copiar-colar (`pytest examples/RISCV32I/test/...`, `.../tools/build_programs.py`)
  para `cpus/rv32i_pipeline/...`.
- `docs/ESTADO-TRILHA-A.md`: as 5 ocorrências de `examples/RISCV32I/...` →
  `cpus/rv32i_pipeline/...`, e a árvore do §2 atualizada para
  `legado/src/spechdl/`, `legado/tests/` etc.
Flipar `- [ ] TRV-7.7.8` → `- [x]`.
Verificação: `grep -o '\](\.\./[^)]*)' docs/MUDANCAS.md` e conferir cada
alvo com `test -e`; revisão manual dos trechos HTML corrigidos. Sinalizar
para revisão humana: a linha entre "corrigir link quebrado" e "reescrever
histórico" é decisão editorial.

**Commit 9 (TRV-7.7.9) — `docs(claude): registrar a trilha RISC-V ativa, o legado/ e o oráculo Docker no CLAUDE.md`**
Adicionar um parágrafo curto (3-5 frases, português) em `CLAUDE.md` logo
após "O que é este projeto": o pipeline Streamlit descrito é a trilha A,
hoje congelada em `legado/`; o trabalho ativo é a trilha RISC-V
(`rvverify/` validando `entregas/` contra `cpus/`), com um montador Python
próprio conferido opcionalmente por um oráculo Docker com binutils real
(`docker/Dockerfile`, NFR-RV-05). Não tocar no resto do arquivo além disso.
Flipar `- [ ] TRV-7.7.9` → `- [x]`.
Verificação: `git diff CLAUDE.md` só mostra a inserção; reler o arquivo
inteiro para não haver contradição com o texto vizinho.

**Commit 10 (TRV-7.7.10) — `docs: arquivar hey-claude-please-plan-jolly-bird.md (parcialmente executado via ADR-013/ADR-004)`**
Arquivar, não apagar. `git mv hey-claude-please-plan-jolly-bird.md
docs/archive/hey-claude-please-plan-jolly-bird.md`, com uma nota no topo do
arquivo movido explicando precisamente o que foi aproveitado e o que não:
"A imagem Docker do toolchain RISC-V e seu uso como oráculo do montador
(passos 1 e 3 deste plano) foram trazidos nos commits que adicionam
NFR-RV-05, `docker/Dockerfile` e `rvverify/tests/test_assembler_oracle.py`.
O restante deste plano — merge do branch `Implementing-.asm-and-.rm-tests`,
a CPU DUT `opus_5_RISCVIM`, a promoção para `tools/riscv/` de topo, os IDs
FR-16..FR-29/NFR-05 — foi superado pela reorganização da ADR-013 e não foi
executado."
Verificação: `git log --follow` no novo caminho mostra histórico contínuo;
`grep -rn "hey-claude-please-plan-jolly-bird"` só encontra o arquivo movido.

**Commit 11 (TRV-7.7.11) — `docs: adicionar REPO_MAP.md com a estrutura final do repositório`**
Só depois dos Commits 1–10. Novo `REPO_MAP.md` na raiz, em português,
cobrindo: as cinco pastas de topo da ADR-013 (`rvverify/`,
`cpus/rv32i_pipeline/`, `cpus/rv32i_monociclo/`, `entregas/`, `legado/`) com
propósito e link para README próprio onde existir; `docker/Dockerfile` como
o oráculo opcional do montador (NFR-RV-05); a nota de que `examples/` deixou
de existir; a nota de que `legado/` está congelado (link para
`docs/ESTADO-TRILHA-A.md`); a nota de que `docs/mapa-do-projeto.html` é um
mapa visual mais antigo e mais restrito (trilha A), deixado como está por
decisão do usuário; referência cruzada a `specs/decisions.md` ADR-004,
ADR-013 e ADR-014. Lembrete no próprio arquivo para mantê-lo atualizado em
qualquer reorganização futura.
Verificação: conferir manualmente com `git ls-files` que todo caminho
citado existe.

**Commit 12 (TRV-7.7.12) — `docs(decisions): registrar ADR-014, conclusão da ADR-013 e adoção do oráculo Docker`**
Adicionar em `specs/decisions.md`, após ADR-013 (sem editar ADR-013, que é
registro histórico), uma ADR-014 no mesmo formato
(Contexto/Decisão/Alternativas rejeitadas/Consequência): o que foi de fato
movido (referenciando os commits acima), a decisão de manter `testpaths` do
`pyproject.toml` sem `legado/` (não há teste algum na trilha A —
`docs/ESTADO-TRILHA-A.md`), a decisão de trazer o oráculo Docker do plano
antigo formalizado como NFR-RV-05 em vez de simplesmente copiar o código
sem spec, e a decisão de arquivar (não apagar) o plano de merge antigo.
Alternativas rejeitadas: mover `cpus/` de volta para `examples/` (pedido
inicial do usuário, revertido nesta conversa); adotar o binutils real como
montador principal em vez de oráculo (rejeitada — quebraria a
autocontenção que a ADR-004 buscava).
Verificação: reler `specs/decisions.md` inteiro para confirmar que ADR-014
não contradiz ADR-013/ADR-004 (só as complementa).

## Arquivos críticos já lidos e confirmados

- `specs/decisions.md:161-193` (ADR-004, texto completo) e `:523-565`
  (ADR-013, texto completo — nomes-alvo `asm.py`/`reference.py`
  confirmados)
- `rvverify/_ferramentas.py` (32 linhas, lido por completo)
- `cpus/rv32i_pipeline/tools/rv_assembler.py` (assinaturas de
  `assemble`/`assemble_with_symbols`/`disassemble_word` confirmadas por
  grep)
- `specs/spec.md:305-326` (formato EARS de `NFR-RV-01..04`, ponto de
  inserção de `NFR-RV-05` confirmado)
- `docker/Dockerfile` no branch `Implementing-.asm-and-.rm-tests` (commit
  `a199070`, 45 linhas, lido por completo — confirma base pinada por
  digest, pacotes `binutils-riscv64-unknown-elf`/`yosys` e o `RUN` de
  verificação)
- `.github/workflows/toolchain-smoketest.yml` (existe e referencia
  `examples/toolchain_smoketest` — precisa do fix do Commit 3)
- `specs/tasks.md:501-529` (formato `TRV-7.x` com `REQ:`/`ACEITE:`
  confirmado)
- Confirmado que `implemetation_tests/opus_5_RISCVIM` na `main` não tem
  `src/`/`specs/` (só `software/`/`test/`, tudo git-ignorado), mas esse
  conteúdo existe de verdade no branch `Implementing-.asm-and-.rm-tests`
  (commit `fdc589e`) — não faz parte deste plano por decisão explícita do
  usuário (só o oráculo Docker foi pedido).

## Verificação de ponta a ponta

Depois dos 15 commits, na ordem:
```bash
grep -rn "examples/RISCV32I\|examples/rv32i_monociclo\|examples/toolchain_smoketest\|examples/ula32" \
  --include=*.md --include=*.py --include=*.yml --include=*.html --include=*.vhd . \
  | grep -v "specs/tasks.md"   # blocos ACEITE históricos ficam de fora de propósito
git ls-files examples/          # deve retornar vazio
python -c "import rvverify, rvverify.asm, rvverify.reference, rvverify.conformance"
pytest rvverify/tests -q
pytest cpus/rv32i_pipeline/test -q
pytest cpus/rv32i_monociclo/test -q

# oráculo Docker (NFR-RV-05) — só roda se houver Docker disponível
docker build -t spechdl-toolchain -f docker/Dockerfile docker
docker run --rm spechdl-toolchain bash -lc \
  "riscv64-unknown-elf-as --version; ghdl --version; yosys -V"
pytest rvverify/tests/test_assembler_oracle.py -v
```
Todos os `pytest`/`docker run` precisam ser executados de verdade
(ambiente GHDL/cocotb, ex. WSL2 ou a imagem Docker de referência) e o exit
code de cada um conferido — nenhuma simulação conta como "passou" por
inferência (regra do CLAUDE.md). O workflow de CI
(`toolchain-smoketest.yml`) só pode ser validado de fato com um
`workflow_dispatch` ou push real; sinalizar isso ao usuário como pendência
pós-merge.
