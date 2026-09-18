# Especificação funcional — SpecHDL

Notação EARS (Easy Approach to Requirements Syntax). Cada requisito tem um ID
único, referenciado pelo código gerado (ver `constitution.md`, princípio 2).

> Atenção: esta é a spec do PRÓPRIO PIPELINE SpecHDL — a ferramenta que você
> está construindo. Não confundir com a spec de um exercício específico (ex:
> "some 4 bits"), que é gerada dinamicamente pela ferramenta a partir de cada
> documento de entrada, na fase 1.

## Fase 1 — Ingestão da rubrica

> A entrada do pipeline é um formulário web local (Streamlit) — não um
> enunciado em texto livre, nem edição manual de Markdown. O aluno responde
> perguntas de true/false e campos técnicos (presença de cache, número de
> estágios de pipeline, largura de palavra, banco de registradores etc.) na
> interface; ao submeter, as respostas viram `rubrica.md` (versionável) e o
> pipeline roda sozinho até o relatório final. A IA não interpreta texto
> livre nessa fase, só valida e estrutura o que foi respondido. Preencher e
> submeter o formulário é a única decisão do aluno no processo inteiro — ver
> NFR-01.

- **FR-01**: THE SYSTEM SHALL disponibilizar um formulário web local
  (Streamlit), com perguntas true/false e campos de especificação técnica,
  como única forma de entrada do pipeline.
- **FR-02**: WHEN o aluno submete o formulário preenchido, THE SYSTEM SHALL
  registrar as respostas em `rubrica.md` e parseá-las em um conjunto de
  requisitos estruturados em formato EARS.
- **FR-03**: IF o formulário é submetido com uma combinação de respostas
  estruturalmente inválida (ex.: campo numérico preenchido pra uma opção
  marcada como "não") ou um campo obrigatório vazio, THEN THE SYSTEM SHALL
  bloquear a submissão e indicar exatamente qual pergunta ou campo precisa
  ser corrigido, em vez de assumir um valor padrão silenciosamente.
- **FR-04**: THE SYSTEM SHALL salvar a spec extraída em um arquivo
  versionável (`spec.json`) antes de prosseguir para a próxima fase.

## Fase 2 — Decomposição arquitetural

- **FR-05**: WHEN uma spec está aprovada, THE SYSTEM SHALL propor uma
  decomposição em blocos de hardware (ex: ULA, banco de registradores,
  unidade de controle, muxes, memória), cada um com entradas, saídas e
  responsabilidade descritas.
- **FR-06**: THE SYSTEM SHALL justificar cada decisão arquitetural (ex: FSM
  hardwired vs. microprogramada) em termos de pelo menos um requisito
  não-funcional da spec (potência, velocidade ou área).
- **FR-07**: WHERE a rubrica não fixa uma decisão de implementação (ex.: FSM
  hardwired vs. microprogramada) e mais de uma arquitetura viável atende à
  spec, THE SYSTEM SHALL registrar as alternativas com seus trade-offs no
  relatório, em vez de escolher silenciosamente uma única opção — sem
  pausar a execução pra perguntar ao aluno (ver NFR-01).

## Fase 3 — Geração de VHDL e testbench

> Testbench = cocotb (Python), não VHDL. O cocotb dirige o DUT VHDL através
> do GHDL como simulador (fluxo `make SIM=ghdl`, ver `plan.md`).

- **FR-08**: FOR EACH bloco definido na fase 2, THE SYSTEM SHALL gerar um
  arquivo VHDL correspondente e um testbench cocotb (Python) derivado dos
  mesmos requisitos, incluindo o Makefile necessário para rodá-lo via GHDL.
- **FR-09**: THE SYSTEM SHALL inserir, em cada arquivo VHDL gerado,
  comentários referenciando o(s) ID(s) de requisito atendido(s); o mesmo
  vale para cada testbench cocotb gerado, em comentário Python.

## Fase 4 — Verificação

- **FR-10**: WHEN um bloco VHDL e seu testbench cocotb estão prontos, THE
  SYSTEM SHALL compilar e simular via GHDL (orquestrado pelo cocotb),
  registrando o resultado (pass/fail, log, waveform em `.vcd` —
  inspecionável no GTKWave).
- **FR-11**: IF a simulação falhar, THEN THE SYSTEM SHALL reportar qual
  requisito da spec não foi satisfeito, o erro técnico bruto, e uma
  classificação da falha — bug de implementação (código/testbench, volta
  pra fase 3) ou lacuna de spec/arquitetura (volta pra fase 1 ou 2) — ver
  `constitution.md`, princípio 5.
- **FR-12**: THE SYSTEM SHALL integrar os blocos verificados individualmente
  em uma simulação de nível superior (top-level) antes de considerar o design
  como um todo verificado.

## Fase 5 — Análise PPA

- **FR-13**: WHEN todos os blocos estão verificados, THE SYSTEM SHALL
  estimar métricas de área (contagem de células/flip-flops) e criticidade de
  caminho, preferencialmente via síntese real (Yosys + ghdl-yosys-plugin).
- **FR-14**: IF a síntese real não for viável no ambiente de execução, THEN
  THE SYSTEM SHALL usar uma heurística alternativa e marcá-la explicitamente
  como estimativa, nunca como medição.

## Fase 6 — Relatório

- **FR-15**: THE SYSTEM SHALL gerar um relatório final rastreando requisito →
  bloco → arquivo VHDL → resultado de teste → métrica PPA.

## Requisitos não-funcionais (do próprio pipeline)

- **NFR-01**: THE SYSTEM SHALL disponibilizar um ponto de entrada único
  (`spechdl web`, que abre o formulário Streamlit local) e, a partir da
  submissão do formulário preenchido, executar as fases 1 a 6 de ponta a
  ponta sem interação humana adicional até o relatório final. A única
  responsabilidade do aluno é preencher e submeter o formulário; o VHDL e
  tudo mais são gerados sem checkpoint de aprovação no meio do caminho.
- **NFR-02**: THE SYSTEM SHALL permitir re-executar uma única fase
  isoladamente (ex: só a fase 5), reaproveitando artefatos das fases
  anteriores.
- **NFR-03**: THE SYSTEM SHALL produzir saídas legíveis por humano
  (Markdown) e por máquina (JSON) em cada fase.
- **NFR-04**: THE SYSTEM SHALL funcionar em ambiente Linux/WSL2 sem depender
  de FPGA física ou licença de ferramenta EDA proprietária.

---

# Trilha RISC-V — RV32I para RV32IM

> Trilha paralela (trilha B), concreta e mais simples, criada a pedido do
> professor: em vez de gerar uma arquitetura qualquer, parte-se da CPU RISC-V
> RV32I já existente em `cpus/rv32i_pipeline/`, valida-se essa CPU como
> **baseline** por simulação real, estende-se para **RV32IM** (as oito
> instruções de multiplicação e divisão) e mede-se a eficiência antes e
> depois. A trilha SpecHDL genérica (FR-01 a FR-15) **não é removida** — passa
> a segundo plano e continua valendo. Os requisitos abaixo são referenciados
> diretamente pelo código em `cpus/rv32i_pipeline/src/`,
> `cpus/rv32i_pipeline/test/` e `cpus/rv32i_pipeline/tools/`; as decisões de
> arquitetura que os concretizam estão em `specs/decisions.md` (ADR-000 a
> ADR-007; o registro da ADR-007 — unidade M combinacional no estágio EX — é a
> tarefa TRV-0.4 de `specs/tasks.md`, ainda em aberto).

## Escopo e premissas (FR-RV-01 a FR-RV-03)

- **FR-RV-01**: WHEN a trilha RISC-V é iniciada e antes de qualquer alteração
  em arquivo de `cpus/rv32i_pipeline/src/`, THE SYSTEM SHALL registrar em
  `specs/decisions.md` (ADR-000) uma auditoria do design existente cujos
  achados — interface do top-level, polaridade e tipo do reset, latência e
  organização das memórias, subconjunto de instruções suportado e ferramentas
  efetivamente disponíveis no ambiente — venham de execução real de
  ferramenta, com o comando e o resultado anotados, em vez de presunção sobre
  o código.
- **FR-RV-02**: THE SYSTEM SHALL reutilizar como base da trilha os blocos já
  existentes em `cpus/rv32i_pipeline/src/` — `CPU.vhd`,
  `instruction_memory.vhd`, `data_ram.vhd`, `data_rom.vhd`,
  `register_file.vhd`, `ALU.vhd` e os demais arquivos RTL do design —, sem
  reescrever o núcleo do zero e sem apagar o caminho RV32I original.
- **FR-RV-03**: THE SYSTEM SHALL manter a arquitetura estritamente RISC-V:
  toda instrução montada, carregada ou executada pertence ao conjunto RV32I
  base ou à extensão M padrão, sem instruções de outra ISA (MIPS ou
  equivalente) e sem opcode inventado — em particular, o fim de programa é
  sinalizado pelo auto-laço `JAL x0, 0` (`0x0000006f`), instrução legítima da
  ISA, e nunca por uma "instrução mágica" de halt.

## Arquitetura alvo — RV32I (FR-RV-04 a FR-RV-07)

- **FR-RV-04**: THE SYSTEM SHALL operar com palavras e instruções de 32 bits,
  banco de 32 registradores `x0` a `x31` em que `x0` lê sempre zero e toda
  escrita em `x0` é descartada, aritmética modular de 32 bits em complemento
  de dois, e acesso à memória de dados exclusivamente por instruções de load e
  store (`LB`, `LBU`, `LH`, `LHU`, `LW`, `SB`, `SH`, `SW`).
- **FR-RV-05**: THE SYSTEM SHALL instanciar, em um único top-level
  (`entity CPU`, portas `clk` e `rst`), a CPU conectada à ROM de instruções
  (base `0x00000000`) e à memória de dados — DATA_ROM de 8 bytes em
  `0x00FC8000` e DATA_RAM de 512 bytes em `0x00FC8100` —, de modo que um
  programa carregado execute do reset até a parada sem nenhum estímulo externo
  além do clock e do reset.
- **FR-RV-06**: THE SYSTEM SHALL manter o estado arquitetural observável pelo
  cocotb através da hierarquia do GHDL — os 32 registradores de
  `register_file.vhd`, o PC de `program_counter.vhd` e o conteúdo da RAM de
  dados de `data_ram.vhd` —, de modo que o testbench possa afirmar valores em
  registradores e em posições de RAM sem acrescentar portas de depuração ao
  top-level (ver ADR-002).
- **FR-RV-07**: FOR EACH alteração feita em um bloco VHDL de terceiro (autoria
  original de Morgan Demange, vendorizada no commit `f884a4e`), THE SYSTEM
  SHALL comprovar por execução de teste que o comportamento observável foi
  preservado, comparando o RTL original e o RTL alterado sobre o mesmo
  programa e exigindo PC final e conteúdo dos 32 registradores idênticos,
  antes de considerar a alteração concluída.

## Carga de programa e memórias (FR-RV-08 a FR-RV-10)

- **FR-RV-08**: THE SYSTEM SHALL documentar o formato da imagem `.ram` em
  `specs/decisions.md` (ADR-003) — uma palavra de 32 bits por linha, 8 dígitos
  hexadecimais sem prefixo `0x` e case-insensitive, linha de índice 0
  correspondendo ao endereço de byte `0x00000000` e linha `n` ao endereço
  `4*n`, linhas vazias e iniciadas por `#` tratadas como comentário, palavras
  não informadas preenchidas com `0x00000000` — incluindo a convenção de
  parada por auto-laço `JAL x0, 0` (`0x0000006f`), que é como o testbench
  reconhece o término do programa.
- **FR-RV-09**: WHEN o generic `ROM_INIT_FILE` de `instruction_memory.vhd` é
  preenchido com o caminho de uma imagem `.ram`, THE SYSTEM SHALL carregar
  essa imagem na ROM de instruções durante a elaboração e executá-la, de modo
  que trocar de programa de teste não exija editar nenhum arquivo VHDL; a
  verificação consiste em montar um programa, gerar sua imagem e comprovar que
  a CPU produziu o resultado desse programa, e não o da constante embutida.
- **FR-RV-10**: WHERE `ROM_INIT_FILE` está vazio (valor padrão `""`), THE
  SYSTEM SHALL usar a constante `INSTRUCTION_MEMORY_CONTENT` de
  `memory_package.vhd` como conteúdo da ROM, preservando o comportamento
  original do design e mantendo-o elaborável e sintetizável por `ghdl synth`.

## Baseline e extensão RV32IM (FR-RV-11 a FR-RV-17)

- **FR-RV-11**: THE SYSTEM SHALL obter e registrar um resultado aprovado de
  verificação da baseline RV32I — execução real de GHDL dirigida por cocotb,
  com exit code zero — antes de iniciar a implementação da extensão M; IF essa
  verificação de baseline não estiver aprovada, THEN THE SYSTEM SHALL bloquear
  o início da extensão, para que nenhuma diferença medida depois seja
  atribuída à extensão sem um ponto de comparação válido.
- **FR-RV-12**: THE SYSTEM SHALL estender a CPU para RV32IM instanciando a
  unidade de multiplicação e divisão (`mul_div_unit.vhd`) no estágio de
  execução, em paralelo com a ALU e selecionada por multiplexador, de modo que
  RV32IM seja exatamente RV32I acrescido das oito instruções de FR-RV-13, sem
  alterar a semântica de nenhuma instrução RV32I já suportada (ver ADR-007).
- **FR-RV-13**: THE SYSTEM SHALL implementar as oito instruções da extensão M
  no formato R-type, com opcode `0110011` e `funct7 = 0000001`, a saber:
  `MUL` (funct3 `000`), `MULH` (`001`), `MULHSU` (`010`), `MULHU` (`011`),
  `DIV` (`100`), `DIVU` (`101`), `REM` (`110`) e `REMU` (`111`) — `MUL`
  entregando os 32 bits baixos do produto e `MULH`/`MULHSU`/`MULHU` os 32 bits
  altos do produto de 64 bits nas combinações com sinal × com sinal, com
  sinal × sem sinal e sem sinal × sem sinal, respectivamente.
- **FR-RV-14**: FOR EACH caso especial definido pela especificação RISC-V não
  privilegiada, THE SYSTEM SHALL produzir exatamente o valor exigido, sem
  exceção de hardware e sem travar o pipeline:
  - IF o divisor é zero, THEN `DIV` resulta `-1` (`0xFFFFFFFF`), `DIVU`
    resulta `0xFFFFFFFF`, e `REM` e `REMU` resultam o próprio dividendo;
  - IF ocorre overflow de divisão com sinal (dividendo `-2^31` =
    `0x80000000` e divisor `-1`), THEN `DIV` resulta `-2^31` (`0x80000000`) e
    `REM` resulta `0`;
  - FOR EACH demais casos, o quociente é truncado em direção a zero e o resto
    tem o sinal do dividendo.
- **FR-RV-15**: WHEN `rst` é levado a nível alto (reset assíncrono, ativo em
  ALTO), THE SYSTEM SHALL zerar o PC e o banco de registradores e, ao liberar
  o reset, retomar a execução a partir da instrução do endereço `0x00000000`,
  com `x0` lendo zero — comportamento idêntico nas duas configurações de
  `RV32M_ENABLE`.
- **FR-RV-16**: WHERE o generic `RV32M_ENABLE : boolean` de `CPU.vhd` vale
  `false`, THE SYSTEM SHALL comportar-se como o design RV32I original,
  tratando as oito instruções da extensão M como instruções inválidas e não
  instanciando a lógica da unidade M — logo, sem pagar o seu custo de área;
  WHERE vale `true`, THE SYSTEM SHALL habilitar RV32IM. As duas configurações
  são elaboradas a partir da mesma árvore de fontes.
- **FR-RV-17**: THE SYSTEM SHALL executar as instruções da extensão M no mesmo
  caminho de dados de latência de um ciclo usado pela ALU, com a seleção da
  unidade M viajando até o estágio EX pelo campo `alu_op_type` que já existe,
  de modo que o forwarding MEM→EX e WB→EX, o stall de load-use e o flush de
  branch/jump continuem válidos sem alteração e sem nova condição de stall; THE
  SYSTEM SHALL ainda declarar explicitamente no relatório que este design não
  possui latência multiciclo para MUL/DIV e que o custo da extensão aparece em
  área e em caminho crítico, medidos conforme FR-RV-25. A verificação consiste
  em programas com dependência RAW imediata entre uma instrução da extensão M e
  a instrução seguinte, produzindo o resultado correto sem NOPs intercalados.

## Artefatos de software (FR-RV-18 a FR-RV-20)

- **FR-RV-18**: FOR EACH benchmark usado na comparação de eficiência, THE
  SYSTEM SHALL versionar um arquivo `.c` legível que documente o algoritmo
  medido; WHERE não houver compilador RISC-V verificado no ambiente (ver
  ADR-004), THE SYSTEM SHALL marcar esses arquivos explicitamente como **não
  compilados neste ambiente**, deixando claro que servem como especificação do
  algoritmo e não como fonte da imagem efetivamente executada.
- **FR-RV-19**: FOR EACH programa `.asm` versionado, THE SYSTEM SHALL montá-lo
  com o montador do projeto (`rvverify/asm.py`) para
  gerar a imagem `.ram` correspondente, usando somente instruções RV32I nos
  programas destinados à baseline e admitindo instruções da extensão M apenas
  nos programas destinados à configuração RV32IM; IF um programa marcado como
  baseline contiver qualquer instrução da extensão M, THEN THE SYSTEM SHALL
  falhar a montagem em vez de gerar a imagem.
- **FR-RV-20**: FOR EACH ferramenta externa de que a trilha depende (GHDL,
  Yosys, cocotb, compilador RISC-V, `ghdl-yosys-plugin`), THE SYSTEM SHALL
  verificar a sua presença por execução antes de depender dela; IF a ferramenta
  estiver ausente, THEN THE SYSTEM SHALL registrar em `specs/decisions.md` a
  alternativa adotada e prosseguir por ela, sem instalar nada na máquina do
  usuário de forma silenciosa ou sem autorização explícita.

## Verificação (FR-RV-21 a FR-RV-23)

- **FR-RV-21**: FOR EACH execução de programa no testbench cocotb, THE SYSTEM
  SHALL aplicar o reset conforme FR-RV-15, gerar o clock, impor um teto de
  ciclos, detectar o término normal pela convenção de parada de FR-RV-08,
  detectar travamento quando o teto de ciclos é atingido sem término, reportar
  o primeiro ciclo em que uma verificação falhou junto do requisito afetado,
  gravar o waveform da simulação para inspeção no GTKWave e terminar o processo
  com exit code diferente de zero sempre que houver falha.
- **FR-RV-22**: FOR EACH instrução verificada, THE SYSTEM SHALL exercitar
  casos de valor zero, operandos negativos, valores extremos (`0x00000000`,
  `0x00000001`, `0x7FFFFFFF`, `0x80000000`, `0xFFFFFFFF`), divisão por zero e
  overflow de divisão onde aplicáveis, além de dependências de dados entre
  instruções consecutivas e das situações de hazard do pipeline (load-use,
  branch tomado e não tomado, encadeamento por forwarding MEM→EX e WB→EX).
- **FR-RV-23**: FOR EACH valor esperado usado em uma asserção, THE SYSTEM SHALL
  derivá-lo de um modelo de referência em Python
  (`rvverify/reference.py`) que implementa a aritmética
  modular de 32 bits em complemento de dois, em vez de valores escritos à mão
  no teste — de modo que o hardware seja conferido contra uma fonte
  independente, e não contra a expectativa de quem escreveu o teste.

## Eficiência (FR-RV-24, FR-RV-25)

- **FR-RV-24**: FOR EACH execução de benchmark, THE SYSTEM SHALL registrar
  ciclos totais, instruções executadas, CPI, tempo estimado, número de stalls,
  número de flushes e número de instruções da extensão M despachadas, todos
  obtidos por contagem de sinais reais do pipeline durante a simulação; WHERE
  uma métrica depender de um parâmetro não medido — o tempo estimado, obtido
  por ciclos × período nominal de clock —, THE SYSTEM SHALL rotulá-la
  explicitamente como estimativa.
- **FR-RV-25**: THE SYSTEM SHALL obter a área das configurações RV32I e RV32IM
  por execução real de ferramenta — `ghdl synth --std=08 --out=verilog CPU`
  alimentando `yosys` com `read_verilog`, `hierarchy -top CPU` e `stat`
  (ADR-005) —, reportando a contagem de células, wires e bits de memória
  devolvida pelo `stat` junto do comando que a produziu; IF essa execução
  falhar no ambiente, THEN THE SYSTEM SHALL marcar qualquer número alternativo
  como heurística, nunca como medição.

## Requisitos não-funcionais da trilha (NFR-RV-01 a NFR-RV-03, NFR-RV-05)

> A numeração não é contígua por seção: `NFR-RV-04` fica na seção do
> validador de entregas, abaixo, porque é sobre a operação por linha de
> comando. `NFR-RV-05` foi acrescentado depois dele e pertence a esta
> seção, por ser sobre a verificação da trilha.

- **NFR-RV-01**: THE SYSTEM SHALL usar o GHDL como simulador e o cocotb
  (Python) como testbench em toda a verificação da trilha, dirigindo o DUT VHDL
  através do GHDL; testbench escrito em VHDL não é a fonte de verdade desta
  trilha.
- **NFR-RV-02**: THE SYSTEM SHALL declarar como *medido* apenas o que provém de
  uma execução real da ferramenta correspondente, com comando e saída
  registrados, e SHALL rotular como *estimativa* qualquer valor derivado de
  cálculo, de modelo ou de parâmetro nominal — nenhum resultado de simulação ou
  métrica de área pode ser inferido a partir da leitura do código.
- **NFR-RV-03**: THE SYSTEM SHALL comparar RV32I e RV32IM sobre a mesma base de
  código, alternando somente o generic `RV32M_ENABLE` (ADR-001), sem duplicar a
  árvore de fontes — de modo que a diferença medida entre as duas configurações
  seja atribuível à extensão M, e não a divergência entre cópias.
- **NFR-RV-05**: THE SYSTEM SHALL disponibilizar uma imagem de container
  (`docker/Dockerfile`) com um assemblador RISC-V cruzado real
  (`riscv64-unknown-elf-as`/`ld`/`objcopy`/`objdump`) e o Yosys, e SHALL usá-la
  como oráculo independente para conferir, palavra a palavra, a saída do
  montador Python (ADR-004) contra pelo menos um programa de cada categoria de
  instrução suportada; IF a imagem não estiver disponível no ambiente, THEN THE
  SYSTEM SHALL apenas pular essa conferência, marcando-a como não executada, e
  SHALL NOT bloquear a suíte principal — o montador Python continua sendo o
  caminho autocontido e testável por pytest, e o binutils real é cross-check,
  não substituto.

---

## Validador de entregas (FR-RV-26 a FR-RV-35, NFR-RV-04)

> Acrescentado em 2026-09-17 e revisado em 2026-09-18 com a orientação do
> professor: **o trabalho é de terminal, sem interface gráfica** (ADR-012).
> A trilha deixa de validar só a CPU de referência: qualquer CPU descrita por
> um `cpu.toml` — a CPU existente modificada por um aluno ou por um modelo de
> IA, ou uma escrita do zero — passa pela mesma suíte, e **reprovar é um
> resultado legítimo**: o objetivo do projeto é medir se quem executou a tarefa
> conseguiu construir a CPU, não fazer a suíte ser gentil. Daí FR-RV-34 e
> FR-RV-35, que fixam o rigor exigido da suíte.
>
> O validador de linha de comando (`python -m rvverify`) já existia quando esta
> seção foi escrita; FR-RV-26 e FR-RV-27 registram o comportamento dele, e os
> demais requisitos especificam o que faltava (ver `plan.md`, seção 7, e
> ADR-011 a ADR-013).

- **FR-RV-26**: FOR EACH diretório que contenha um `cpu.toml` — as CPUs de
  referência em `cpus/` e as entregas em `entregas/<nome>/` —, THE SYSTEM SHALL validar a
  CPU descrita usando somente o que o manifesto declara (fontes na ordem de
  análise, clock, reset, generic de carga de programa, caminhos observáveis e
  modo de parada), sem conhecer o RTL, rodando a suíte de conformidade em duas
  etapas — RV32I com a extensão desligada e RV32IM com o generic de
  `[design].rv32m_generic` ligado —; WHERE o manifesto não declara
  `rv32m_generic`, THE SYSTEM SHALL pular a segunda etapa e reportá-la como
  pulada, nunca como aprovada; IF a etapa RV32I reprovar, THEN THE SYSTEM SHALL
  pular a etapa RV32IM pelo motivo de FR-RV-11.
- **FR-RV-27**: THE SYSTEM SHALL reportar o resultado de cada caso, de cada
  etapa e de cada requisito exercitado — um requisito só conta como atendido
  quando todos os casos que o exercitam passam — e um veredito único entre
  quatro estados:
  - **APROVADO** — a suíte completa (as duas etapas, todos os casos) rodou e
    todo caso executado passou;
  - **REPROVADO** — ao menos um caso executado falhou;
  - **INCOMPLETO** — nenhum caso falhou, mas alguma etapa foi pulada;
  - **PARCIAL** — nenhum caso falhou e nada foi pulado, mas o usuário
    selecionou só parte da suíte; o relatório diz quantos casos da suíte
    ficaram de fora e não trata o resultado como aprovação;

  e THE SYSTEM SHALL terminar a linha de comando com exit code diferente de
  zero sempre que algum caso executado falhar ou alguma etapa for pulada.
- **FR-RV-28**: FOR EACH caso reprovado, THE SYSTEM SHALL reportar um
  diagnóstico estruturado com:
  - o tipo da falha — valor divergente, travamento, caminho de observação
    inexistente, erro de compilação, programa maior que a ROM ou erro interno;
  - para valor divergente, cada posição de RAM com endereço, entrada que a
    produziu, valor esperado e valor obtido, em hexadecimal e em decimal com
    sinal;
  - para erro de compilação, as linhas de erro do GHDL com arquivo, linha e
    coluna;
  - o caminho do log da simulação daquele caso;
  - uma orientação sobre o bloco de hardware a revisar, derivada do caso e do
    requisito;
  - WHERE todos os valores obtidos coincidem com o resultado de outra
    instrução da mesma etapa segundo o modelo de referência, a indicação dessa
    instrução, porque é o sintoma típico de decodificação trocada (por exemplo,
    SRA executando como SRL).

  O diagnóstico só aponta o que a execução observou: a orientação é rotulada
  como sugestão e não altera o veredito.
- **FR-RV-29**: WHILE a validação executa, THE SYSTEM SHALL emitir, quando
  pedido (`--eventos`), um evento legível por máquina por linha de saída — o
  plano de itens a executar, o início e o fim da compilação, o início e o fim
  de cada item com o seu resultado e duração, cada etapa pulada com o motivo e
  o relatório final —, de modo que outro processo — integração contínua, ou um
  arnês que avalie vários modelos de IA em lote — acompanhe a execução sem
  interpretar o log do GHDL; e THE SYSTEM SHALL gravar a saída do GHDL de cada
  caso em um arquivo de log próprio, fora da saída principal.
- **FR-RV-30**: THE SYSTEM SHALL apresentar cada execução como **um relatório
  de terminal coeso**, e não como despejo de log:
  - um cabeçalho com a CPU, o manifesto e o que será executado;
  - uma linha por caso, no momento em que ele termina, com veredito, tempo e
    ciclos — a saída do GHDL não aparece aqui (FR-RV-29);
  - um resumo final com o veredito de FR-RV-27, o placar por etapa, os
    requisitos atendidos e os pendentes (pelo título, não só pelo ID), e as
    métricas efetivamente observadas;
  - o diagnóstico de FR-RV-28 de cada caso reprovado, com o caminho do log
    daquele caso;
  - a linha de comando exata que repete apenas o que falhou.

  WHERE a saída não é um terminal interativo, THE SYSTEM SHALL suprimir cor e
  animação, mantendo o mesmo conteúdo.
- **FR-RV-31**: FOR EACH entrega, THE SYSTEM SHALL aceitar uma **pasta** em
  `entregas/<nome>/` contendo um `cpu.toml` na raiz, descobri-la sozinho, e
  validar o manifesto e a existência de cada fonte declarada **antes** de
  qualquer simulação; IF o manifesto estiver ausente, malformado ou apontar
  para fonte inexistente, THEN THE SYSTEM SHALL dizer qual campo, em qual
  tabela, em qual arquivo, e terminar com exit code diferente de zero, sem
  simular; e THE SYSTEM SHALL ignorar a pasta-modelo (`entregas/_modelo/`), que
  existe para ser copiada e não é uma entrega.
- **FR-RV-32**: WHERE o usuário pede a comparação de eficiência, THE SYSTEM
  SHALL executar cada benchmark de `cpus/rv32i_pipeline/programs/` nas duas
  versões — `*_rv32i` com a extensão desligada e `*_rv32im` com a extensão
  ligada —, conferir os resultados na RAM contra valores derivados do modelo de
  referência (FR-RV-23) e só então tabular, lado a lado, ciclos, instruções,
  CPI, stalls, flushes e instruções RV32M, na medida em que o manifesto torne
  cada métrica observável (NFR-RV-02); IF o mapa de memória do manifesto não
  for o mapa fornecido (`0x00FC8100`, 512 bytes) ou o manifesto não declarar
  `rv32m_generic`, THEN THE SYSTEM SHALL pular a comparação, ou a versão
  RV32IM, com o motivo escrito.
- **FR-RV-33**: WHERE o usuário pede a medição de área, THE SYSTEM SHALL
  sintetizar as fontes do manifesto nas duas configurações do generic
  `rv32m_generic` pelo fluxo do ADR-009 (`ghdl synth --out=verilog` + Yosys
  com hierarquia preservada e `techmap`), reportando por bloco e no total as
  células contadas pelo `stat`, o total sem as memórias fornecidas
  (`instruction_memory`, `data_ram`, `data_rom`) e a profundidade lógica
  medida por `ltp` onde ela for obtida; IF a síntese falhar, THEN THE SYSTEM
  SHALL mostrar o erro da ferramenta e marcar a área como não medida, sem
  alterar o veredito funcional.
- **FR-RV-34**: THE SYSTEM SHALL manter uma suíte de conformidade cuja
  cobertura mínima, por etapa, é declarada e verificável, de modo que uma CPU
  com defeito real não seja aprovada:
  - **RV32I**: as 10 operações registrador-registrador e as 9 formas
    imediatas, cada uma sobre valores de borda com sinal e sem sinal; os
    deslocamentos nos limites do `shamt`; `x0` como origem e como destino;
    escrita e leitura dos 31 registradores graváveis; aliasing de operandos
    (`rd` igual a `rs1`, a `rs2`, e `rs1` igual a `rs2`); as três larguras de
    load e store com extensão de sinal e de zeros, endianness byte a byte e
    preservação das faixas vizinhas; offset negativo e ponteiro em registrador;
    os seis branches nos dois desfechos, para frente e para trás; `JAL`,
    `JALR`, `LUI` e `AUIPC`; chamada aninhada com retorno salvo em memória;
    laço aninhado; e cadeias de dependência entre instruções consecutivas,
    inclusive load seguido de uso imediato;
  - **RV32IM**: as oito instruções da extensão sobre valores de borda, as
    metades alta e baixa do mesmo produto de 64 bits, os casos especiais de
    FR-RV-14, aliasing de operandos, dependência imediata entre uma instrução
    da extensão e a seguinte, e resultado da extensão usado como endereço de
    memória e como condição de desvio.

  FOR EACH caso, o valor esperado vem do modelo de referência (FR-RV-23) e o
  resultado é publicado na RAM de dados, de modo que a verificação não dependa
  de nenhum sinal interno nem da microarquitetura escolhida (FR-RV-26).
- **FR-RV-35**: THE SYSTEM SHALL provar o rigor da suíte por **teste de
  mutação**: para cada defeito de uma lista versionada de mutações — entre
  elas `SRA` como deslocamento lógico, `SUB` como soma, `funct7` ignorado na
  decodificação da extensão M, escrita em `x0` não descartada, extensão de
  sinal ausente em `LB`/`LH`, branch com condição invertida, e `JALR` sem
  zerar o bit 0 — THE SYSTEM SHALL aplicar a mutação a uma cópia de uma CPU de
  referência, rodar a suíte e exigir que ela **reprove**, nomeando o caso que
  pegou o defeito; IF alguma mutação passar, THEN o teste de mutação falha e a
  lacuna de cobertura é tratada como defeito da suíte, não da CPU.
- **NFR-RV-04**: THE SYSTEM SHALL ser operado inteiramente por linha de
  comando, sem interface gráfica e sem serviço de rede (ADR-012), e SHALL
  depender apenas da biblioteca padrão do Python somada ao GHDL e ao cocotb
  já exigidos por NFR-RV-01 — o ambiente de referência (ADR-006) não tem
  framework web instalado, e o fluxo do professor é o terminal.
