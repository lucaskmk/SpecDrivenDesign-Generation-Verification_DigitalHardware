# SpecHDL

Pipeline spec-driven que parte de um formulário web local (Streamlit,
`spechdl web`) — o aluno responde perguntas true/false e campos técnicos
(cache, estágios de pipeline, largura de palavra etc.), não escreve nada
livre — extrai requisitos estruturados, decompõe em blocos de hardware
(ULA, banco de registradores, unidade de controle, muxes etc.), gera VHDL +
testbenches, verifica no GHDL e produz um relatório de trade-offs de
potência, velocidade e área (PPA). Ao submeter, o app grava `rubrica.md`
(versionável) e o pipeline roda sozinho até o relatório final — preencher e
submeter o formulário é a única responsabilidade do aluno.

O projeto em si é construído seguindo a metodologia que ele implementa:
**nenhuma linha de código antes de uma spec aprovada** — ver
[`specs/constitution.md`](specs/constitution.md), princípio 1.

## CPU RISC-V — o caso especial

Quando a rubrica pede um **processador RISC-V**, o pipeline gera uma CPU nova
e customizada (RV32I base + as extensões escolhidas), usando
[`examples/RISCV32I/`](examples/RISCV32I/) como referência de arquitetura —
não como código a copiar. Nesse caso entram duas fases a mais, e o critério
de pronto é bem mais duro: **CPU só está verificada se rodar software de
verdade.**

```
program.S ──as/ld──> ELF ──objcopy──> .rm ──> ROM da CPU gerada
                       │                            │
                  objdump                     cocotb + GHDL
                       │                            │
                  program.dasm            RAM final == esperado?
```

Três regras que valem sempre (ver `specs/constitution.md`, princípios 8 a 10):

1. **Testbench de bloco não fecha uma CPU.** ULA e banco de registradores
   passando isolados é o piso, não o teto. O design só fecha depois de
   executar um programa montado de verdade e a RAM final bater, endereço por
   endereço, com o estado esperado.
2. **O oráculo vem antes da observação.** O estado esperado é derivado da
   semântica do assembly e gravado *antes* da simulação. O teste obrigatório
   do RV32I base é um **golden file imutável**: se ele falha, o bug é da CPU
   gerada, e a correção é no VHDL — nunca no arquivo esperado.
3. **Toda instrução implementada é testada.** Cobertura é medida
   dinamicamente, pelo que a CPU *aposentou* durante a simulação (via as
   portas de trace `dbg_instr`/`dbg_valid`), não pela presença do mnemônico
   no fonte — senão código morto passaria. Instrução declarada e nunca
   executada = falha, com a lista nominal do que ficou de fora.

Cada extensão (padrão — M, A, F, D, C, Zicsr… — ou custom) entra com o seu
próprio programa de teste, cobrindo todas as instruções que ela adiciona. Os
programas são escritos **direto em assembly**, não em C: com C quem escolhe
as instruções emitidas é o compilador, e aí não há como garantir cobertura
instrução por instrução. Detalhes em [`specs/plan.md`](specs/plan.md), seção
"Fase 3b/4b em detalhe".

## O pipeline

![Pipeline (conceito original): documento → spec EARS → decomposição arquitetural → geração de VHDL+testbench → verificação GHDL → análise PPA → relatório final, com falha voltando para a spec](pipeline_sdd_hardware.png)

> O diagrama acima é do conceito original (entrada em texto livre); a
> entrada real hoje é o formulário Streamlit — ver `specs/spec.md`, Fase 1.

1. **Ingestão** — o formulário web (Streamlit) preenchido pelo aluno vira um
   conjunto de requisitos estruturados em notação EARS (`spec.json`); uma
   submissão com respostas inconsistentes é bloqueada, apontando o campo.
2. **Decomposição arquitetural** — a spec aprovada vira uma proposta de
   blocos de hardware, cada decisão justificada por pelo menos um requisito
   não-funcional (potência, velocidade ou área).
3. **Geração de VHDL + testbench** — cada bloco vira um arquivo VHDL e um
   testbench [cocotb](https://www.cocotb.org/) (Python), ambos rastreando o
   ID do requisito que implementam.
3b. **Software de verificação** (só CPU) — o teste obrigatório do RV32I base
   mais um programa por extensão declarada, em assembly, montados para `.rm`
   e carregados na ROM da CPU gerada.
4. **Verificação** — cada bloco (e depois o design integrado) é compilado e
   simulado de fato no GHDL, orquestrado pelo cocotb; falha de simulação é
   reportada junto do requisito não atendido.
4b. **Verificação em nível de programa** (só CPU) — cada `.rm` roda na CPU
   gerada e o estado final da RAM é comparado com o esperado, endereço por
   endereço, com cobertura de instrução medida dinamicamente. Se o teste
   obrigatório falha, a fase 5 não roda e a CPU é declarada não verificada.
5. **Análise PPA** — síntese real via Yosys + `ghdl-yosys-plugin` para
   contagem de células/área, em vez de a IA estimar métricas "no chute".
6. **Relatório final** — rastreia cada requisito até o bloco, o arquivo
   VHDL, o resultado do teste e a métrica de PPA correspondente; para CPU,
   inclui também a tabela de cobertura instrução por instrução.

## Estado atual

O projeto está na **Fase 0/1** — a especificação está concluída e alinhada,
e as duas primeiras tarefas do pipeline já são código real e testado.

**Pronto:**
- Constituição (10 princípios), spec funcional (EARS, FR-01–FR-29,
  NFR-01–NFR-05), plano técnico e backlog de tarefas em [`specs/`](specs/),
  revisados e consistentes entre si — incluindo as fases 3b/4b de verificação
  de CPU RISC-V rodando software.
- **T0.1** — estrutura de pastas do pipeline (`src/spechdl/`, `tests/`,
  `outputs/`) e ambiente virtual Python.
- **T1.1** — schema completo da rubrica em
  [`src/spechdl/ingestion/schema.py`](src/spechdl/ingestion/schema.py) (137
  campos em 8 seções: modelo da máquina, ISA, microarquitetura, hierarquia
  de memória, E/S, proteção, PPA, ABI), com skip logic e validação cruzada
  (FR-03). O formulário
  ([`web_form.py`](src/spechdl/ingestion/web_form.py)) renderiza esse
  schema e roda de verdade — abre com
  [`abrir_formulario.bat`](abrir_formulario.bat) (duplo clique) sem prompt
  de telemetria pra atrapalhar, grava `outputs/rubrica.md` ao submeter, e
  já foi testado ponta a ponta (`streamlit.testing`, mais um teste manual
  seu). O parser pra `spec.json` em EARS (T1.2) ainda não existe.
- Smoke test de toolchain (GHDL + cocotb) em
  [`examples/toolchain_smoketest/`](examples/toolchain_smoketest/), com CI
  em [`.github/workflows/toolchain-smoketest.yml`](.github/workflows/toolchain-smoketest.yml).
- Duas execuções de referência do método SDD completo (ponta a ponta, com
  verificação real via GHDL+cocotb em Docker, re-testada localmente) em
  [`examples/ula32_sol/`](examples/ula32_sol/) e
  [`examples/ula32_terra/`](examples/ula32_terra/) — geradas por um agente
  externo contra o modelo antigo (texto livre), não são fixtures de rubrica,
  mas provam que a metodologia funciona ponta a ponta.
- CPU RV32I de terceiro (Morgan Demange) em
  [`examples/RISCV32I/`](examples/RISCV32I/), vendorizada como **referência
  de arquitetura** para as fases 3b/4b — 5 estágios de pipeline, Harvard.
  Não foi gerada por este pipeline: não tem `-- REQ:`, não tem testbench
  cocotb (só um `CPU_tb.vhd`), e o `Makefile` dela aponta pra um toolchain
  xPack que não está no repo. É material de consulta, não saída do pipeline.

**Pendente (backlog completo em [`specs/tasks.md`](specs/tasks.md)):**
- T0.2–T0.5 — validar GHDL/cocotb/GTKWave e Yosys de fato (só testamos via
  Docker contra o exemplo de referência, não contra o smoke test oficial
  ainda), configurar `OPENROUTER_API_KEY` e criar o exemplo fixo com rubrica
  preenchida (fixture real das fases seguintes).
- T0.6–T0.7 — imagem Docker do projeto com o binutils cruzado RISC-V
  (NFR-05) e validação da cadeia de montagem assembly → ELF → `.rm`. Hoje
  nada disso existe: a máquina de desenvolvimento não tem GHDL nem toolchain
  RISC-V no PATH, só Docker e WSL2.
- T1.2–T1.5 — parser EARS, validação de submissão e a seleção de ISA/extensões
  RISC-V na rubrica.
- Fases 3b e 4b inteiras — fixture golden do RV32I base, conversor de `.rm`,
  testbench de programa, cobertura dinâmica de instrução e os gates.
- Todo o restante do pipeline (Fases 2 a 7): decomposição, geração,
  verificação, PPA, relatório e CLI instalável (`spechdl web`).

## Especificações — leia nesta ordem

| Ordem | Arquivo | Conteúdo |
|---|---|---|
| 1 | [`specs/constitution.md`](specs/constitution.md) | Princípios inegociáveis do projeto |
| 2 | [`specs/spec.md`](specs/spec.md) | Requisitos funcionais/não-funcionais (EARS) do pipeline |
| 3 | [`specs/plan.md`](specs/plan.md) | Arquitetura técnica, estrutura de pastas, contratos JSON entre fases |
| 4 | [`specs/tasks.md`](specs/tasks.md) | Backlog atômico, fase por fase |

O [`CLAUDE.md`](CLAUDE.md) na raiz resume as regras de comportamento pra
quem (ou qual agente) for implementar o pipeline em cima dessa spec.

Uma versão visual — diagrama do pipeline (formulário → EARS → decomposição
→ VHDL → verificação, com a triagem de falha e a checagem manual no
GTKWave), árvore do repositório e status por fase — está em
[`docs/mapa-do-projeto.html`](docs/mapa-do-projeto.html) (abra localmente no
navegador). É uma foto do estado do repo num momento; a fonte de verdade
continua sendo `specs/tasks.md`.

## Estrutura do repositório

```
.
├── CLAUDE.md                       # instruções de comportamento pro Claude Code
├── README.md
├── pipeline_sdd_hardware.png       # diagrama do pipeline (conceito original)
├── abrir_formulario.bat            # atalho dev: duplo clique sobe o formulário
├── .gitignore · .env.example       # OPENROUTER_API_KEY, SPECHDL_LLM_MODEL
├── .streamlit/config.toml          # desliga o prompt de telemetria/e-mail
├── docs/
│   └── mapa-do-projeto.html        # versão visual: diagrama + árvore + status
├── specs/
│   ├── constitution.md
│   ├── spec.md
│   ├── plan.md
│   └── tasks.md
├── templates/
│   └── rubrica.md                  # visão geral estrutural — schema.py é a
│                                    # fonte de verdade real do schema
├── src/spechdl/
│   ├── ingestion/schema.py         # 137 campos, skip logic, validação cruzada (T1.1)
│   ├── ingestion/web_form.py       # formulário Streamlit — código real, T1.1
│   └── architecture/ codegen/ software/ verification/ ppa/ report/  # pacotes vazios ainda
├── docker/
│   └── Dockerfile                  # imagem do projeto: GHDL+cocotb+binutils RISC-V (T0.6)
├── tests/                          # testes pytest do pipeline (ainda vazio)
├── outputs/                        # artefatos gerados por execução (gitignored)
├── examples/
│   ├── toolchain_smoketest/        # smoke test do toolchain GHDL+cocotb (T0.2)
│   │   ├── src/demux.vhd
│   │   └── test/{test_demux.py, Makefile}
│   ├── riscv_base_test/            # fixture GOLDEN do RV32I base (T3b.1/T3b.2)
│   ├── RISCV32I/                   # CPU RV32I de terceiro — referência de arquitetura
│   ├── ula32_sol/                  # referência: SDD ponta a ponta, modelo antigo (texto livre)
│   └── ula32_terra/                # idem, rodado por um segundo agente isolado do primeiro
├── scripts/
│   └── llm_playground.py           # manda um prompt solto pro modelo via OpenRouter (T0.4)
└── .github/workflows/
    └── toolchain-smoketest.yml
```

O exemplo real da disciplina com rubrica preenchida (`examples/alu_4bit/`
ou equivalente, T0.5) ainda não foi criado — ver estrutura completa
proposta em [`specs/plan.md`](specs/plan.md).

## Stack

- Python 3.11+ (venv — 3.12 já validado)
- [Streamlit](https://streamlit.io/) — formulário web local da fase 1, único
  ponto de entrada do pipeline; já rodando
  ([`src/spechdl/ingestion/web_form.py`](src/spechdl/ingestion/web_form.py)).
  O comando final será `spechdl web` (Fase 7, ainda não implementado); por
  ora é `streamlit run` direto ou `abrir_formulario.bat`
- [OpenRouter](https://openrouter.ai/docs) (SDK nativo) — extração de spec,
  decomposição arquitetural e geração de VHDL (`OPENROUTER_API_KEY` via
  variável de ambiente, modelo via `SPECHDL_LLM_MODEL`, nunca hardcoded)
- [GHDL](https://github.com/ghdl/ghdl) — compilação/simulação VHDL
- [cocotb](https://www.cocotb.org/) — testbenches em Python sobre o GHDL
- [GTKWave](https://gtkwave.sourceforge.net/) — inspeção visual do waveform
  (`.vcd`) na triagem manual de falha
- [Yosys](https://github.com/YosysHQ/yosys) + `ghdl-yosys-plugin` — síntese
  real para as métricas de PPA
- Binutils cruzado RISC-V (`riscv64-unknown-elf-as/ld/objcopy/objdump`) —
  monta os programas de teste de CPU da fase 3b (assembly → ELF → `.rm`);
  entregue dentro da imagem `docker/Dockerfile`, sem instalação manual
  (NFR-05)
- pytest — testes do próprio pipeline (não confundir com os testbenches
  cocotb gerados, que testam o hardware)
- python-dotenv — carrega `.env` em desenvolvimento local

Ambiente de referência: Linux/WSL2, imagem Docker
`rafaelcorsi/pl-descomp-cocotb` (mesma usada no smoke test de CI); a imagem
do projeto (`docker/Dockerfile`, T0.6) estende essa com o toolchain RISC-V e
o Yosys.

## Próximo passo

Testar o formulário (`abrir_formulario.bat`) e, se estiver bom, seguir pra
`T1.2` em [`specs/tasks.md`](specs/tasks.md): o parser que transforma
`rubrica.md` em requisitos EARS estruturados (`spec.json`).
