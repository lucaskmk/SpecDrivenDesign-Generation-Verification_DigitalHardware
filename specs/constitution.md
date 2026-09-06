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

## Emenda 1 — Trilha RISC-V (setembro de 2026)

A partir desta emenda o projeto tem **duas trilhas** de desenvolvimento, e
ambas respondem a esta mesma constituição.

- **Trilha A — SpecHDL genérico** (formulário Streamlit → spec EARS →
  decomposição arquitetural → VHDL + cocotb → GHDL → PPA → relatório).
  Segue existindo **intacta**: nada dela é removido, congelado ou
  desfigurado. Continua sendo a razão de ser do core em `src/spechdl/` e
  dos princípios 1 a 7 na forma em que estão escritos.
- **Trilha B — RISC-V RV32I → RV32IM**. Passa a ser o **foco** do trabalho:
  partir da CPU RV32I concreta já existente, validá-la como *baseline*,
  estendê-la para a extensão M (`MUL`, `MULH`, `MULHSU`, `MULHU`, `DIV`,
  `DIVU`, `REM`, `REMU`), provar por cocotb + GHDL que funciona e medir a
  eficiência antes e depois.

Prioridade de foco não é prioridade de princípio: a trilha B ser o foco
significa que ela recebe o esforço, não que ela pode contradizer o que já
está escrito acima.

### Por que o princípio 7 continua valendo

O princípio 7 proíbe que o pipeline assuma um exercício específico como
alvo. A trilha B **não viola** esse princípio porque vive inteiramente em
`examples/RISCV32I/` — fontes VHDL, montador, programas, testbenches,
scripts de síntese e relatórios. Nenhuma linha de `src/spechdl/` passa a
conhecer RISC-V, RV32IM, o montador próprio ou o formato `.ram`: o core
segue genérico e dirigido pelo documento de entrada. A trilha B é, na letra
do princípio 7, um exemplo fixo em `examples/` — o maior deles, mas ainda
um exemplo. Se algum dia um trecho da trilha B parecer útil ao core, ele só
sobe para `src/spechdl/` depois de generalizado e especificado; jamais por
cópia direta.

Os princípios 8 a 11 abaixo são **específicos da trilha B** e têm o mesmo
peso dos princípios 1 a 7: são inegociáveis da mesma forma.

## 8. Nada é removido
Código de terceiros (a CPU RV32I vendorizada) e contribuições de colegas são
**preservados**. A evolução acontece por **parametrização** — um `generic`
que liga ou desliga um comportamento no mesmo design — nunca por deleção do
que já funcionava e nunca por duplicação da árvore de fontes em uma "versão
2". Deletar apaga a prova de que o original funcionava; duplicar cria duas
verdades que divergem no primeiro *bugfix* aplicado em só uma delas. Um
único design parametrizado é também a única forma de a comparação A/B ser
honesta: as duas configurações compartilham, por construção, exatamente a
mesma base de código.

## 9. Baseline antes de melhoria
Nenhuma extensão é aceita sem que a versão **original** tenha sido
verificada antes, **sob o mesmo testbench** que julgará a versão estendida.
Sem baseline medido não existe "melhorou": existe apenas uma afirmação sobre
um número que ninguém viu antes. O baseline também é o que separa uma
regressão introduzida pela extensão de um defeito que já estava lá — sem
ele, toda falha vira discussão de opinião.

## 10. Nenhuma métrica sem ferramenta
Todo número apresentado como **medido** exige a execução real da ferramenta
correspondente, com o comando e a saída registrados no repositório: ciclos e
CPI vêm da simulação cocotb + GHDL; área e caminho crítico vêm de
`ghdl synth` + Yosys. O que não foi obtido assim é **estimativa**, e deve
aparecer no relatório rotulado como estimativa, com o método explícito. Um
número inventado com aparência de medição é pior do que a ausência do
número, porque contamina toda conclusão construída sobre ele. Este princípio
é a aplicação direta do princípio 4 ao domínio das métricas.

## 11. ISA estritamente RISC-V
A arquitetura implementada é RISC-V e apenas RISC-V: codificação, semântica
e casos especiais seguem a especificação oficial (RV32I e a extensão M).
Nada de MIPS, nada de ISA "inspirada em", nada de instrução inventada para
facilitar um teste. Divergir da ISA para contornar uma dificuldade de
implementação transforma o resultado em um simulador de um processador que
não existe — e destrói o valor de comparação contra qualquer modelo de
referência externo.
