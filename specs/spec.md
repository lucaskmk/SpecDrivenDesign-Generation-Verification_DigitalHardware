# Especificação funcional — SpecHDL

Notação EARS (Easy Approach to Requirements Syntax). Cada requisito tem um ID
único, referenciado pelo código gerado (ver `constitution.md`, princípio 2).

> Atenção: esta é a spec do PRÓPRIO PIPELINE SpecHDL — a ferramenta que você
> está construindo. Não confundir com a spec de um exercício específico (ex:
> "some 4 bits"), que é gerada dinamicamente pela ferramenta a partir de cada
> documento de entrada, na fase 1.

> As fases **3b** e **4b** são condicionais: valem quando o design alvo é um
> processador (ex.: RISC-V RV32I + extensões). Nesse caso elas não são
> opcionais — a CPU não é considerada verificada sem elas (FR-29). Para
> designs combinacionais/sequenciais simples (uma ULA, um demux), o fluxo
> segue direto da fase 3 para a fase 4.

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
- **FR-16**: WHERE a rubrica indica que o design alvo é um processador
  RISC-V, THE SYSTEM SHALL registrar em `spec.json` a ISA base (RV32I), a
  lista de extensões selecionadas (padrão — M, A, F, D, C, Zicsr… — e
  custom) e a **lista nominal de instruções declaradas como implementadas**,
  cada uma com o requisito que a originou. Essa lista é o contrato contra o
  qual a cobertura da fase 4 é medida (FR-26).

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
- **FR-17**: WHEN o design alvo é um processador, THE SYSTEM SHALL incluir na
  decomposição uma ROM de instruções e uma RAM de dados endereçável, e
  garantir que o top-level gerado exponha a **interface de verificação
  padrão** definida em `plan.md` (clock, reset, porta de trace da instrução
  aposentada e array de RAM legível pelo cocotb). Sem essa interface, o teste
  obrigatório da fase 4 não tem como se acoplar ao design gerado.

## Fase 3 — Geração de VHDL e testbench

> Testbench = cocotb (Python), não VHDL. O cocotb dirige o DUT VHDL através
> do GHDL como simulador (fluxo `make SIM=ghdl`, ver `plan.md`).

- **FR-08**: FOR EACH bloco definido na fase 2, THE SYSTEM SHALL gerar um
  arquivo VHDL correspondente e um testbench cocotb (Python) derivado dos
  mesmos requisitos, incluindo o Makefile necessário para rodá-lo via GHDL.
- **FR-09**: THE SYSTEM SHALL inserir, em cada arquivo VHDL gerado,
  comentários referenciando o(s) ID(s) de requisito atendido(s); o mesmo
  vale para cada testbench cocotb gerado, em comentário Python.

## Fase 3b — Geração do software de verificação (CPUs)

> Aplica-se somente quando o design alvo é um processador. Um testbench de
> bloco isolado (ULA, banco de registradores) não prova que a CPU executa
> programas — ver `constitution.md`, princípio 8. O caminho é sempre
> assembly → `.rm` → ROM → simulação → comparação de RAM. O programa de teste
> é escrito **diretamente em assembly** pela IA: escrever em C e deixar o
> compilador escolher o que emitir não permite garantir a cobertura instrução
> por instrução exigida pelo FR-26.

- **FR-18**: WHEN o design alvo é um processador RISC-V, THE SYSTEM SHALL
  usar o **teste-programa obrigatório do RV32I base** — uma fixture golden
  versionada em `examples/riscv_base_test/`, com o assembly, o `.rm` e os
  estados de RAM esperados — sem gerá-lo, editá-lo ou substituí-lo.
- **FR-19**: FOR EACH extensão declarada em `spec.json` (padrão ou custom),
  THE SYSTEM SHALL gerar um programa de teste em assembly dedicado que
  exercite **todas as instruções que aquela extensão adiciona**, escrevendo o
  resultado de cada uma em um endereço distinto e conhecido da RAM.
- **FR-20**: FOR EACH programa de teste, THE SYSTEM SHALL montar e linkar o
  assembly para ELF, gerar o disassembly de conferência e o código de máquina
  da ROM (`.rm`), registrando `-march`, `-mabi` e a versão do montador
  usados — o `.rm` é derivado por ferramenta, nunca escrito à mão pela IA.
- **FR-21**: THE SYSTEM SHALL carregar o `.rm` na ROM de instruções da CPU
  gerada de forma automática, sem passo manual de copiar/colar conteúdo em
  arquivo VHDL (contraste com o fluxo de `examples/RISCV32I/`, que exige isso
  do humano — ver `constitution.md`, princípio 6).
- **FR-22**: FOR EACH programa de teste gerado pela IA, THE SYSTEM SHALL
  derivar os estados de RAM esperados da semântica do assembly escrito e
  gravá-los em arquivo **antes** de executar a simulação daquele programa,
  nunca a partir da RAM observada na simulação (ver `constitution.md`,
  princípio 9).


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

## Fase 4b — Verificação em nível de programa (CPUs)

- **FR-23**: FOR EACH programa de teste (o obrigatório do FR-18 e os de
  extensão do FR-19), THE SYSTEM SHALL executar o `.rm` na CPU gerada via
  cocotb + GHDL e comparar o estado final da RAM com os estados esperados,
  **endereço por endereço**, registrando pass/fail, log e waveform.
- **FR-24**: IF algum endereço divergir do esperado, THEN THE SYSTEM SHALL
  reportar o endereço, o valor esperado, o valor obtido, a instrução e a
  extensão envolvidas, o requisito não atendido e a classificação da falha
  (ver FR-11).
- **FR-25**: WHILE um programa de teste executa, THE SYSTEM SHALL registrar
  **dinamicamente** o conjunto de instruções efetivamente aposentadas pela
  CPU, a partir da porta de trace do FR-17 — não da presença do mnemônico no
  código-fonte assembly, que passaria mesmo com código morto, trecho nunca
  alcançado ou instrução descartada em flush de pipeline.
- **FR-26**: IF alguma instrução declarada em `spec.json` (FR-16) não foi
  aposentada por nenhum programa de teste, THEN THE SYSTEM SHALL falhar a
  verificação da CPU e listar nominalmente as instruções sem cobertura.
- **FR-27**: IF a CPU aposentar uma instrução que não consta na lista
  declarada em `spec.json`, THEN THE SYSTEM SHALL reportar isso como lacuna
  de spec (ver `constitution.md`, princípio 5), não como detalhe ignorável.
- **FR-28**: IF um programa de teste não sinalizar término dentro do limite
  de ciclos configurado, THEN THE SYSTEM SHALL falhar como não-terminação,
  reportando o último PC e a última instrução aposentada, em vez de comparar
  uma RAM de estado indefinido.
- **FR-29**: THE SYSTEM SHALL considerar uma CPU verificada somente se o
  teste obrigatório passar, todos os testes de extensão passarem e a
  cobertura de instruções estiver completa (FR-26). IF o teste obrigatório
  falhar, THEN THE SYSTEM SHALL NOT prosseguir para a fase 5, e o relatório
  final SHALL declarar a CPU como não verificada.

## Fase 5 — Análise PPA

- **FR-13**: WHEN todos os blocos estão verificados, THE SYSTEM SHALL
  estimar métricas de área (contagem de células/flip-flops) e criticidade de
  caminho, preferencialmente via síntese real (Yosys + ghdl-yosys-plugin).
- **FR-14**: IF a síntese real não for viável no ambiente de execução, THEN
  THE SYSTEM SHALL usar uma heurística alternativa e marcá-la explicitamente
  como estimativa, nunca como medição.

## Fase 6 — Relatório

- **FR-15**: THE SYSTEM SHALL gerar um relatório final rastreando requisito →
  bloco → arquivo VHDL → resultado de teste → métrica PPA. WHERE o design é
  um processador, o relatório SHALL incluir também a cadeia extensão →
  programa de teste → `.rm` → resultado da comparação de RAM, e uma tabela de
  cobertura instrução por instrução (declarada vs. aposentada, FR-25/FR-26).

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
- **NFR-05**: THE SYSTEM SHALL fornecer o toolchain completo de verificação
  de CPU (montador/linker cruzado RISC-V + GHDL + cocotb) como um ambiente
  reprodutível e versionado no próprio repositório, de forma que a cadeia
  assembly → `.rm` → simulação rode com um único comando, sem instalação
  manual de toolchain nem caminho hardcoded na máquina do aluno (contraste
  com `examples/RISCV32I/compilation/Makefile`, que aponta pra um diretório
  xPack local).
