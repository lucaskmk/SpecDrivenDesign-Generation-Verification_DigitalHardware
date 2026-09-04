# Especificação funcional — CPU `rv32im_sc` (opus_5_RISCVIM)

Saída da fase 1 do pipeline SpecHDL, derivada de `rubrica.md`. Notação EARS.

> **Namespace**: os IDs `FR-xx`/`NFR-xx` deste arquivo são requisitos **do
> design gerado** (esta CPU), não do pipeline SpecHDL. Ver `specs/plan.md`
> do repositório, seção "Contratos de dados entre fases". Os IDs citados
> como `pipeline:FR-xx` referem-se à spec do pipeline.

## Identificação

| Item | Valor |
|---|---|
| Design | `rv32im_sc` — RISC-V RV32IM monociclo |
| ISA base | RV32I |
| Extensões | M (padrão), nenhuma custom |
| Instruções declaradas | 45 (37 RV32I + 8 M) |
| Top-level | `cpu` |
| Origem | `specs/rubrica.md` (fase 1) |

## Requisitos funcionais

- **FR-01**: THE CPU SHALL operar com palavra e registradores de 32 bits,
  espaço de endereço de 32 bits, memória endereçada por byte em
  little-endian, exigindo acesso alinhado (halfword em múltiplo de 2, word
  em múltiplo de 4).
  *(rubrica: largura_palavra, largura_endereco, enderecamento_por_byte,
  little_endian, exige_acesso_alinhado)*

- **FR-02**: THE CPU SHALL prover um banco de 32 registradores de 32 bits com
  duas portas de leitura assíncronas e uma porta de escrita síncrona, WHERE
  `x0` é fixo em zero: leitura de `x0` retorna 0 e escrita em `x0` é
  descartada.
  *(rubrica: num_registradores, registrador_zero_fixo,
  portas_leitura_regbank, portas_escrita_regbank)*

- **FR-03**: THE CPU SHALL implementar o conjunto base RV32I nas 37
  instruções abaixo, com semântica da especificação RISC-V não privilegiada:

  | Grupo | Instruções |
  |---|---|
  | U-type | `lui`, `auipc` |
  | Jumps | `jal`, `jalr` |
  | Branches | `beq`, `bne`, `blt`, `bge`, `bltu`, `bgeu` |
  | Loads | `lb`, `lh`, `lw`, `lbu`, `lhu` |
  | Stores | `sb`, `sh`, `sw` |
  | ALU-imediato | `addi`, `slti`, `sltiu`, `xori`, `ori`, `andi`, `slli`, `srli`, `srai` |
  | ALU-registrador | `add`, `sub`, `sll`, `slt`, `sltu`, `xor`, `srl`, `sra`, `or`, `and` |

  *(rubrica: ISA base = RV32I)*

- **FR-04**: THE CPU SHALL implementar a extensão padrão M nas 8 instruções
  `mul`, `mulh`, `mulhsu`, `mulhu`, `div`, `divu`, `rem`, `remu`, em hardware
  dedicado (sem emulação por software e sem sequenciamento multiciclo).
  *(rubrica: extensões = M, mult_hardware, div_hardware)*

- **FR-05**: THE CPU SHALL usar datapath monociclo com CPI igual a 1 e
  unidade de controle hardwired combinacional (sem microprograma, sem
  pipeline, sem stall e sem forwarding), retirando exatamente uma instrução
  por borda de subida do clock após o reset.
  *(rubrica: estagios_pipeline=1, cpi_alvo=1.0, multiciclo_microprogramado=False,
  forwarding=False, deteccao_hazard_stall=False)*

- **FR-06**: THE CPU SHALL usar organização Harvard sem cache, com o mapa de
  memória abaixo; acesso fora dessas faixas é tratado pelo FR-07.

  | Região | Faixa | Tamanho | Acesso |
  |---|---|---|---|
  | ROM de instruções (`.text` + `.rodata`) | `0x00000000`–`0x00000FFF` | 4 KB / 1024 palavras | leitura por instrução (fetch) e por load |
  | RAM de dados (scratchpad) | `0x00FC8000`–`0x00FC8FFF` | 4 KB / 1024 palavras | leitura e escrita por load/store |

  *(rubrica: harvard=True, niveis_cache=0, scratchpad=True, boot_rom=True,
  tamanho_boot_rom_kb=4)*

- **FR-07**: THE CPU SHALL suportar acessos de 8, 16 e 32 bits com extensão
  de sinal (`lb`, `lh`) e com extensão de zero (`lbu`, `lhu`); IF o endereço
  de dados estiver fora das faixas do FR-06 OR desalinhado para a largura
  pedida, THEN a leitura SHALL retornar `0xFFFFFFFF` e a escrita SHALL ser
  descartada, sem gerar exceção (não há mecanismo de exceção — ver FR-14).
  *(rubrica: exige_acesso_alinhado=True, excecoes_precisas=False)*

- **FR-08**: THE CPU SHALL calcular desvios condicionais e `jal` de forma
  PC-relativa e `jalr` como `(rs1 + imm) & ~1`, gravando `PC+4` em `rd` nas
  duas instruções de jump, sem delay slot.
  *(rubrica: modo_pc_relativo=True, tem_call_link=True, tem_delay_slot=False)*

- **FR-09**: WHEN `rst` está em '1' na borda de subida do clock, THE CPU
  SHALL zerar o PC para `0x00000000` e suprimir a retirada de instrução
  (reset síncrono, ativo em nível alto); WHILE `rst` está em '0', a execução
  SHALL prosseguir a partir do PC corrente.
  *(rubrica: reset_sincrono=True, reset_ativo_baixo=False)*

- **FR-10**: THE CPU SHALL expor a interface de verificação padrão exigida
  pelo pipeline (`pipeline:FR-17`): `clk`, `rst`, `dbg_pc`, `dbg_instr`,
  `dbg_valid` (ativo só quando uma instrução real é aposentada no ciclo) e a
  RAM de dados como `signal memory` dentro da instância `data_ram_inst`,
  filha direta do top-level.

- **FR-11**: THE CPU SHALL seguir a semântica de borda da extensão M da
  especificação RISC-V:

  | Caso | `div` | `divu` | `rem` | `remu` |
  |---|---|---|---|---|
  | divisor = 0 | `-1` | `0xFFFFFFFF` | dividendo | dividendo |
  | overflow (`-2^31 / -1`) | `-2^31` | n/a | `0` | n/a |

  *(rubrica: div_hardware=True)*

- **FR-12**: THE CPU SHALL usar apenas os 5 bits menos significativos do
  operando de deslocamento (`shamt` do imediato ou `rs2(4 downto 0)`) em
  `sll`, `srl`, `sra`, `slli`, `srli`, `srai`, em um barrel shifter de um
  ciclo.
  *(rubrica: barrel_shifter=True)*

- **FR-13**: THE CPU SHALL carregar a imagem de ROM a partir do `.rm` do
  programa montado, via pacote VHDL gerado (`rom_image_pkg.vhd`), sem passo
  manual de edição de fonte (`pipeline:FR-21`).

- **FR-14**: THE CPU SHALL NOT implementar `fence`, `fence.i`, `ecall`,
  `ebreak`, instruções de CSR (Zicsr), instruções atômicas, ponto flutuante,
  SIMD, interrupções, MMU ou modos de privilégio. Essas instruções **não
  entram** em `declared_instructions` e, portanto, não são exigidas pela
  cobertura da fase 4b (`pipeline:FR-26`); WHEN uma palavra de instrução não
  reconhecida é buscada, THE CPU SHALL tratá-la como `nop` (nenhuma escrita
  em registrador nem em memória) e seguir para `PC+4`.
  *(rubrica: syscall_trap=False, tem_interrupcoes=False, mmu=False,
  modos_privilegio=False, ponto_flutuante=False, simd=False,
  instrucoes_atomicas=False)*

## Requisitos não-funcionais

- **NFR-01** (área): THE CPU SHALL caber no orçamento de 10000 células/LUTs
  declarado na rubrica, WHERE a escolha de controle hardwired combinacional e
  de datapath monociclo evita registradores de pipeline, ROM de microcódigo,
  lógica de hazard e de forwarding.
  *(rubrica: orcamento_area=10000, alvo_fpga=True)*

- **NFR-02** (velocidade): THE CPU SHALL atingir CPI = 1 com alvo de clock de
  50 MHz, aceitando que o caminho crítico contenha o divisor combinacional —
  trade-off registrado explicitamente na fase 2 (ver `architecture.json`,
  `alternatives`).
  *(rubrica: cpi_alvo=1.0, freq_clock_mhz=50)*

- **NFR-03** (potência): THE CPU SHALL usar um único domínio de clock, sem
  clock gating e sem memória externa, dentro do orçamento de 500 mW.
  *(rubrica: dominios_clock=1, orcamento_potencia_mw=500)*

- **NFR-04** (verificabilidade): THE CPU SHALL ser verificada por testbenches
  cocotb rodando sobre GHDL, por bloco (fase 4) e em nível de programa
  (fase 4b), sem hardware adicional dedicado a teste além do trio `dbg_*`.

## Lacunas de spec identificadas na fase 1

Registradas aqui em vez de contornadas em silêncio (constituição do
pipeline, princípio 5).

- **SPEC-GAP-01** — `validate_cross_fields()`
  (`src/spechdl/ingestion/schema.py:258`) modela o orçamento de bits da
  instrução como `opcode + n_operandos × bits_registrador + imediato ≤
  largura_instrucao`. Para RISC-V isso é falso por construção: os formatos
  são disjuntos — R-type tem três campos de registrador e nenhum imediato,
  I-type tem dois campos e imediato de 12 bits, U-type tem um campo e
  imediato de 20 bits. Com as respostas honestas desta rubrica
  (`bits_opcode=7`, `tres_operandos=True`, `bits_imediato=12`) a soma dá 34 >
  32 e a validação bloquearia a submissão de uma ISA que existe e é válida.
  A alternativa seria responder `tres_operandos=False` só para agradar o
  validador, o que falsearia a rubrica. **Consequência**: a validação cruzada
  precisa passar a raciocinar por formato de instrução (o campo
  `num_formatos_instrucao` já existe) em vez de somar todos os campos de uma
  vez. Não afeta o hardware gerado.

- **SPEC-GAP-02** — `capacidade_ram_mb` tem granularidade de MB e mínimo de
  1 MB, mas este design usa 4 KB de RAM de dados (suficiente para os
  programas de teste e coerente com o orçamento de área). A resposta na
  rubrica é o mínimo expressável (1 MB); o valor implementado e verificado é
  o do FR-06 (4 KB). **Consequência**: o schema precisa de unidade
  configurável (KB/MB) ou de um campo em bytes. Não afeta o hardware gerado,
  mas afeta a rastreabilidade rubrica → FR-06.
