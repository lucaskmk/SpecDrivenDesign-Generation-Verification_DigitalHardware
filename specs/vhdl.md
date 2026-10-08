# Especificação essencial de VHDL gerado

Estas regras valem para todo VHDL escrito pelo `rvgen` e são verificadas por
GHDL com VHDL-2008.

1. Use somente `ieee.std_logic_1164` e `ieee.numeric_std`; não use pacotes
   aritméticos não padronizados.
2. Para extensão de sinal, use `resize(signed(...), largura)`. Nunca repita
   manualmente um bit de sinal em concatenações.

   ```vhdl
   imm_i <= std_logic_vector(resize(signed(instr(31 downto 20)), 32));
   ```

3. Faça conversões explicitamente com `signed(...)`, `unsigned(...)` e
   `std_logic_vector(...)`; mantenha as larguras compatíveis antes de operar.
4. Todo sinal deve ter um único driver. Em processos combinacionais, atribua
   valores padrão a todas as saídas para não inferir latches.
5. Uma função que lê sinal ou estado declarado na arquitetura deve ser
   `impure`; prefira processo combinacional quando isso não for necessário.
6. Entregue um arquivo completo: uma entidade por arquivo, sem placeholders,
   elipses ou trechos omitidos.
7. Arrays observados pelo testbench devem ser arrays 1-D de palavras de 32
   bits. Mantenha a guarda de faixa e o índice de um array na mesma expressão
   condicional.
8. Todo arquivo deve iniciar com comentário `-- REQ:` e os IDs de requisitos
   atendidos; use identificadores e comentários em inglês.
