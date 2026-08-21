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
