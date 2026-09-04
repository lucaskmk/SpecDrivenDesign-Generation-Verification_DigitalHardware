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

## 8. CPU só é verificada rodando software de verdade
Testbench de bloco (ULA isolada, banco de registradores isolado) é condição
necessária, não suficiente. Quando o design alvo é um processador, ele só é
considerado verificado depois de **executar um programa montado de verdade**
e ter o estado final da RAM comparado com o estado esperado. O caminho é
sempre o completo: assembly → código de máquina (`.rm`) → ROM da CPU
gerada → simulação cocotb/GHDL → comparação de RAM. Nenhuma etapa desse
caminho pode ser pulada, simulada de mentira ou substituída por inspeção do
código gerado.

## 9. O oráculo é independente e vem antes da observação
O estado de RAM esperado é derivado da semântica do programa de teste,
**nunca** do que a CPU gerada produziu. Rodar a simulação, ver a RAM que saiu
e chamar aquilo de "esperado" não é verificação, é tautologia — e é a forma
mais fácil de a IA se enganar sozinha.

Em consequência:
- O arquivo de estados esperados é gravado e commitado **antes** de a
  simulação daquele programa rodar.
- O golden file do teste obrigatório é **imutável**. Se ele falha, a falha é
  da CPU gerada, e a correção é no hardware — nunca no golden. A IA não tem
  permissão de editar, relaxar, regravar ou "atualizar" esse arquivo.
- Se um estado esperado estiver realmente errado, isso é um bug de spec:
  pare, corrija a spec do programa de teste e justifique a mudança — não
  ajuste números silenciosamente até o teste ficar verde.


## 10. Toda instrução implementada é uma instrução testada
Uma instrução que a spec declara como implementada e que nenhum teste
executou não conta como pronta. A cobertura é medida **dinamicamente**, pelo
que a CPU efetivamente aposentou (retirou) durante a simulação — não pela
presença do mnemônico no disassembly, que passaria mesmo com código morto ou
instrução em caminho de pipeline descartado.

Duas direções, ambas obrigatórias:
- Instrução declarada e nunca executada → falha, com a lista nominal do que
  ficou de fora.
- Instrução executada e não declarada na spec → lacuna de spec (princípio 5),
  não um detalhe a ignorar.

Cada extensão de ISA (padrão ou custom) entra com seu próprio programa de
teste, cobrindo todas as instruções que ela adiciona.
