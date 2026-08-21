# Especificação funcional — SpecHDL

Notação EARS (Easy Approach to Requirements Syntax). Cada requisito tem um ID
único, referenciado pelo código gerado (ver `constitution.md`, princípio 2).

> Atenção: esta é a spec do PRÓPRIO PIPELINE SpecHDL — a ferramenta que você
> está construindo. Não confundir com a spec de um exercício específico (ex:
> "some 4 bits"), que é gerada dinamicamente pela ferramenta a partir de cada
> documento de entrada, na fase 1.

## Fase 1 — Ingestão e extração de spec

- **FR-01**: WHEN o usuário fornece um documento (PDF, docx ou texto)
  contendo um enunciado de hardware, THE SYSTEM SHALL extrair um conjunto de
  requisitos estruturados em formato EARS.
- **FR-02**: WHEN a extração identifica ambiguidade ou informação faltante no
  documento original, THE SYSTEM SHALL sinalizar explicitamente o requisito
  como incompleto, em vez de assumir um valor padrão silenciosamente.
- **FR-03**: THE SYSTEM SHALL salvar a spec extraída em um arquivo
  versionável (`spec.json`) antes de prosseguir para a próxima fase.

## Fase 2 — Decomposição arquitetural

- **FR-04**: WHEN uma spec está aprovada, THE SYSTEM SHALL propor uma
  decomposição em blocos de hardware (ex: ULA, banco de registradores,
  unidade de controle, muxes, memória), cada um com entradas, saídas e
  responsabilidade descritas.
- **FR-05**: THE SYSTEM SHALL justificar cada decisão arquitetural (ex: FSM
  hardwired vs. microprogramada) em termos de pelo menos um requisito
  não-funcional da spec (potência, velocidade ou área).
- **FR-06**: WHERE mais de uma arquitetura viável atende à spec, THE SYSTEM
  SHALL apresentar as alternativas com seus trade-offs, em vez de escolher
  silenciosamente uma única opção.

## Fase 3 — Geração de VHDL e testbench

> Testbench = cocotb (Python), não VHDL. O cocotb dirige o DUT VHDL através
> do GHDL como simulador (fluxo `make SIM=ghdl`, ver `plan.md`).

- **FR-07**: FOR EACH bloco definido na fase 2, THE SYSTEM SHALL gerar um
  arquivo VHDL correspondente e um testbench cocotb (Python) derivado dos
  mesmos requisitos, incluindo o Makefile necessário para rodá-lo via GHDL.
- **FR-08**: THE SYSTEM SHALL inserir, em cada arquivo VHDL gerado,
  comentários referenciando o(s) ID(s) de requisito atendido(s); o mesmo
  vale para cada testbench cocotb gerado, em comentário Python.

## Fase 4 — Verificação

- **FR-09**: WHEN um bloco VHDL e seu testbench cocotb estão prontos, THE
  SYSTEM SHALL compilar e simular via GHDL (orquestrado pelo cocotb),
  registrando o resultado (pass/fail, log, waveform em `.vcd` —
  inspecionável no GTKWave).
- **FR-10**: IF a simulação falhar, THEN THE SYSTEM SHALL reportar qual
  requisito da spec não foi satisfeito, o erro técnico bruto, e uma
  classificação da falha — bug de implementação (código/testbench, volta
  pra fase 3) ou lacuna de spec/arquitetura (volta pra fase 1 ou 2) — ver
  `constitution.md`, princípio 5.
- **FR-11**: THE SYSTEM SHALL integrar os blocos verificados individualmente
  em uma simulação de nível superior (top-level) antes de considerar o design
  como um todo verificado.

## Fase 5 — Análise PPA

- **FR-12**: WHEN todos os blocos estão verificados, THE SYSTEM SHALL
  estimar métricas de área (contagem de células/flip-flops) e criticidade de
  caminho, preferencialmente via síntese real (Yosys + ghdl-yosys-plugin).
- **FR-13**: IF a síntese real não for viável no ambiente de execução, THEN
  THE SYSTEM SHALL usar uma heurística alternativa e marcá-la explicitamente
  como estimativa, nunca como medição.

## Fase 6 — Relatório

- **FR-14**: THE SYSTEM SHALL gerar um relatório final rastreando requisito →
  bloco → arquivo VHDL → resultado de teste → métrica PPA.

## Requisitos não-funcionais (do próprio pipeline)

- **NFR-01**: THE SYSTEM SHALL executar de ponta a ponta a partir de um único
  comando (`spechdl run <documento>`), dado um documento de entrada válido.
- **NFR-02**: THE SYSTEM SHALL permitir re-executar uma única fase
  isoladamente (ex: só a fase 5), reaproveitando artefatos das fases
  anteriores.
- **NFR-03**: THE SYSTEM SHALL produzir saídas legíveis por humano
  (Markdown) e por máquina (JSON) em cada fase.
- **NFR-04**: THE SYSTEM SHALL funcionar em ambiente Linux/WSL2 sem depender
  de FPGA física ou licença de ferramenta EDA proprietária.
