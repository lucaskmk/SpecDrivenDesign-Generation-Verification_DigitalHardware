# Regras para testbenches Cocotb

Estas regras se aplicam a todo testbench Cocotb gerado para componentes. Testes
de componentes verificam apenas as portas declaradas da entidade; não acessam
sinais ou memória por hierarquia.

## Compatibilidade e assertions

- Use `import cocotb`, `cocotb.clock.Clock` e `cocotb.triggers`.
- Use `assert` Python com uma mensagem que diga valor esperado e observado.
- Não importe `cocotb.result.TestFailure`: essa API não existe no cocotb 2.
- Para ler um vetor já conhecido como `0` ou `1`, use `int(sinal.value)`.
  Não use `int(sinal.value, 2)`: em cocotb 2 `sinal.value` é um `LogicArray`,
  não uma string. Não use métodos inventados como `to_string()`.
- Não remova assertions nem reduza casos de teste ao corrigir um testbench.
- Para toda porta ou sinal `std_logic_vector`, escreva valores dirigidos,
  valores esperados e exemplos em hexadecimal: `0x00000000`, `0x0000001F`,
  `0xFFFFFFFF`. Não escreva literais binários longos nem construa strings de
  bits repetidos (`"000..."`). Para vetores estreitos, continue usando um
  inteiro hexadecimal que caiba na largura, como `0x0`, `0x1` ou `0x7`.
  Essa regra também vale para comentários e mensagens de assertion. Sinais
  escalares `std_logic` continuam usando `0` ou `1`.

## Verificação obrigatória da interface

Antes de escrever o testbench, leia a declaração `entity` fornecida e faça
uma lista mental de todas as portas, suas direções e larguras.

- Use somente portas declaradas nessa entidade.
- Nunca presuma a existência de `clk`, `rst`, `enable` ou qualquer outro
  sinal por causa do tipo de componente.
- Só importe `Clock` ou `RisingEdge` e só inicie um clock se a entidade
  declarar uma porta de entrada chamada `clk`.
- Só dirija `rst` se a entidade declarar uma porta de entrada chamada `rst`.
- Para uma entidade sem `clk`, escreva um teste combinacional: dirija as
  entradas, aguarde `Timer(1, unit="ns")` e verifique as saídas.
- Antes de devolver o código, revise cada ocorrência de `dut.<nome>`:
  `<nome>` precisa constar exatamente na lista de portas da entidade.

## Direção e observação de sinais

- Antes da primeira leitura, dirija valores conhecidos em **todas** as portas
  de entrada.
- Todo valor dirigido deve caber na largura declarada da porta; masque valores
  quando testar wraparound de 32 bits.
- Após `RisingEdge`, aguarde `Timer(1, unit="ns")` antes de conferir saídas
  produzidas por lógica sequencial.
- Para leituras assíncronas, altere o endereço, aguarde um `Timer` curto e
  então faça a assertion; não espere uma borda de clock.
- Não use atributos internos do DUT (`dut._...`) para observar ou alterar seu
  estado; interaja exclusivamente pelas portas.

## Clock, reset e isolamento

- Inicie **um único** `Clock` para o DUT. Nunca crie outro clock dentro de
  cada `@cocotb.test()` ou função de reset.
- Testes Cocotb podem compartilhar a mesma instância do DUT. Cada teste deve
  dirigir todas as entradas e deixar o DUT em estado conhecido antes de fazer
  qualquer assertion.
- Para reset síncrono, mantenha `rst = 1` durante uma borda de subida:

  ```python
  dut.rst.value = 1
  await RisingEdge(dut.clk)
  await Timer(1, unit="ns")
  dut.rst.value = 0
  ```

- Para reset assíncrono, aguarde tempo de simulação após afirmar o reset:

  ```python
  dut.rst.value = 1
  await Timer(1, unit="ns")
  dut.rst.value = 0
  ```

- Não presuma que um `Timer` de um período de clock, sem observar a borda,
  aplicou um reset síncrono.

## Ambiente externo para uma interface de CPU

Quando a entidade declarada expõe simultaneamente uma interface de busca de
instruções (endereço como saída e palavra de instrução como entrada) e uma
interface de transações de dados (endereço, leitura/escrita, largura e dados),
o Cocotb é um teste de integração arquitetural. Ele deve agir como ambiente
externo exclusivamente através dessas portas:

- mantenha em Python um mapa de palavras de programa, respondendo a cada
  endereço de busca com a instrução correspondente;
- mantenha em Python o estado de dados, respondendo a leituras e atualizando o
  estado após escritas segundo a largura e os bits baixos do endereço;
- aplique clock e reset somente se essas portas existirem na interface;
- execute programas RV32I curtos que terminem de forma observável e confira
  efeitos arquiteturais externos, como conteúdo de dados, endereços e
  transações de escrita;
- na ampliação, cubra classes de programa declaradas na spec semântica (por
  exemplo, cálculo, desvio, salto e acesso a dados), com um caso representativo
  por classe, não enumeração de operandos ou endereços.

Não instancie ROM, RAM ou qualquer memória VHDL. Não use sinais internos para
inspecionar registradores, ALU ou controle. O ambiente Python apenas responde
ao protocolo público da entidade; `rvverify` continua sendo a autoridade final.

## Escopo e cobertura de componentes

- Testes de componentes são diagnósticos rápidos e representativos; `rvverify`
  é a autoridade para a cobertura integrada completa da CPU.
- Crie casos somente para comportamentos, operações e casos de borda declarados
  no contrato semântico do componente. Não invente cenários adicionais.
- Cubra classes semânticas, não todo o domínio de valores: para cada regra,
  use um caso nominal e apenas as bordas que alterem essa regra.
- Não enumere registradores, endereços, valores de dados ou combinações de
  operandos homogêneos. Para um domínio indexado, use x0/zero quando tiver
  semântica própria, um índice não-zero representativo e um limite somente se
  ele tiver comportamento distinto.
- Não gere produto cartesiano de operações e operandos. Cada operação distinta
  pode ter um caso representativo; adicione outro somente para uma borda
  declarada, como wraparound, sinal, shift 0/31 ou condição tomada/não tomada.
- Se a spec não declara uma semântica, não a teste nem a presuma.
