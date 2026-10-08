# Constituição do projeto

## Fonte de verdade

- `specs/cpu.md` define o contrato funcional da CPU RISC-V.
- `specs/vhdl.md` define regras essenciais do VHDL gerado.
- O código em `rvgen/contrato.py` contém os metadados executáveis necessários
  para validar opções e montar o manifesto.

## Verificação

- A IA gera ou corrige apenas VHDL e testbenches dentro da entrega.
- GHDL e cocotb verificam componentes; erros do testbench não autorizam alterar
  o VHDL sem triagem.
- `rvverify` é a única autoridade do veredito da CPU integrada.
- Nenhuma geração pode modificar o validador nem fontes fornecidas.

## Reprodutibilidade

- Toda geração grava prompts, respostas, logs e relatórios em `.rvgen/`.
- Um resultado deve poder ser reproduzido pelo comando registrado na sessão.
