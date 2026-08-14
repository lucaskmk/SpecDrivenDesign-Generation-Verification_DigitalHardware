# Constituição do projeto SpecHDL

Princípios que não são negociáveis ao longo do desenvolvimento. Qualquer
decisão de design que os contradiga deve ser discutida e esta constituição
atualizada primeiro — não o contrário.

## 1. Spec-first, sempre
Nenhuma linha de VHDL ou de código Python de geração é escrita antes de
existir uma seção correspondente em `specs/spec.md`, aprovada. Prompt solto
pro Claude gerar "o que achar melhor" é exatamente o antipadrão (vibe coding)
que este projeto existe para evitar.

## 2. Rastreabilidade requisito → bloco → código → teste
Todo artefato gerado (bloco arquitetural, arquivo VHDL, testbench, linha de
relatório) deve ser rastreável até o(s) requisito(s) da spec que o
originaram. Um relatório final sem essa cadeia de rastreamento é um
relatório incompleto, mesmo que o código funcione.

## 3. Requisitos não-funcionais são cidadãos de primeira classe
Potência, velocidade e área não são um apêndice opcional — entram na spec
como requisitos EARS desde o início e influenciam decisões de arquitetura
(ex: FSM hardwired vs. microprogramada, largura de pipeline, clock gating).
Uma arquitetura proposta sem justificativa em termos de NFR é uma arquitetura
incompleta.

## 4. Verificação real, não simulada por inferência
Um bloco só é considerado "concluído" quando existe uma execução real do
GHDL com resultado registrado (pass/fail + log/waveform). A IA nunca declara
"o teste passaria" sem efetivamente rodar o teste.

## 5. Falha aponta pra spec, não só pro código
Quando um teste falha, o relatório de erro deve indicar qual requisito da
spec não foi atendido — não apenas "linha 42 não bateu com o esperado".

## 6. Reprodutibilidade
O pipeline inteiro deve rodar de ponta a ponta a partir de um único comando,
dado um novo documento de entrada. Nada de passos manuais escondidos entre
fases.

## 7. Ferramenta genérica, não hardcoded pro exercício específico
O pipeline não assume que o hardware alvo é uma ULA de 4 bits ou qualquer
exercício específico — o design vem do documento de entrada. Exemplos fixos
vivem em `examples/`, nunca dentro do core do pipeline.
