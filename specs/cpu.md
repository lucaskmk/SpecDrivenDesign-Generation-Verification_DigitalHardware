# Especificação da CPU RISC-V

- RV32I single cycle

Nota: Não são exigidos: FENCE, ECALL, EBREAK, CSRs, interrupções ou acessos
desalinhados.

O arquivo obrigatório é `src/cpu.vhd`, com esta entidade exata:

```vhdl
entity cpu is
    port(
        clk : in std_logic;
        rst : in std_logic;
        instr_addr : out std_logic_vector(31 downto 0);
        instr_data : in std_logic_vector(31 downto 0);
        data_addr : out std_logic_vector(31 downto 0);
        data_write : out std_logic;
        data_width : out std_logic_vector(1 downto 0);
        data_write_data : out std_logic_vector(31 downto 0);
        data_read_data : in std_logic_vector(31 downto 0)
    );
end cpu;
```

## Contrato do top-level

Esta é a única interface externa da CPU. Não crie `cpu_top`, generics de ROM,
nem instancie ROM ou RAM dentro da CPU. Blocos internos, seus nomes e suas
portas são livres, desde que `src/cpu.vhd` implemente exatamente esta entidade.

O `rvverify` fornece ROM e RAM virtuais pelas portas acima.

### Busca e PC

- `instr_addr` deve expor sempre o PC da instrução corrente.
- `instr_data` é uma leitura assíncrona da ROM virtual nesse endereço. A CPU
  usa essa instrução para calcular os resultados que são confirmados na borda
  de subida de `clk`.
- Fora de reset, uma instrução RV32I completa por borda de subida. O próximo
  PC é `pc + 4`, exceto para `JAL`, `JALR` ou uma branch tomada.
- A prioridade do próximo PC é: `JAL`/`JALR`, branch tomada, `pc + 4`.
- `JAL x0, 0` deve manter o mesmo PC em bordas sucessivas; esse é o laço de
  parada que o validador detecta.

### Dados

- `data_width` é `"00"` para byte, `"01"` para meia palavra e `"10"` para
  palavra.
- `data_addr` é sempre o endereço efetivo em **bytes**, sem mascarar seus bits
  baixos. Para loads ele é `rs1 + I`; para stores é `rs1 + S`.
- Leituras são assíncronas. `data_read_data` contém a palavra de 32 bits cujo
  endereço-base é `data_addr & 0xFFFFFFFC`.
- A palavra é little-endian: offsets `00`, `01`, `10`, `11` selecionam,
  respectivamente, os bits `7:0`, `15:8`, `23:16`, `31:24` de
  `data_read_data`. Para meia palavra, offset `00` usa bits `15:0` e offset
  `10` usa bits `31:16`.
- A CPU seleciona a parte lida e faz extensão de sinal para `LB` e `LH`; `LBU`
  e `LHU` fazem extensão com zero.
- Para `SB`, `SH` e `SW`, `data_write` deve ser `'1'` no ciclo da instrução e
  `data_write_data` deve conter `rs2` (o validador usa os 8, 16 ou 32 bits
  baixos conforme `data_width`). A RAM virtual confirma a escrita na borda de
  subida.
- Para qualquer instrução que não seja store, `data_write` deve ser `'0'`.


## Reset e execução

`rst` é assíncrono e ativo em nível alto. Enquanto `rst = '1'`, o PC deve ser
`0x00000000` e todos os registradores devem ler como zero, sem esperar uma
borda de clock.

Programas terminam em `halt: j halt` (`JAL x0, 0`).
