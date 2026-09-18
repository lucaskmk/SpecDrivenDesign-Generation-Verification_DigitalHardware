# Especificação funcional — CPU `rv32im_sc` (opus_5_RISCVIM)

Saída da fase 1 do pipeline SpecHDL, derivada de `rubrica.md`. Notação EARS.

> **Namespace**: os IDs `FR-xx`/`NFR-xx` deste arquivo são requisitos **do
> design gerado** (esta CPU), não do pipeline SpecHDL. Os IDs citados como
> `repo:FR-RV-xx` referem-se à spec do repositório
> (`../../specs/spec.md`), seção "Validador de entregas", que é o contrato
> vigente para julgar uma CPU. Ver também a seção "Reconciliação com a spec
> vigente do repositório" no fim deste arquivo.

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

- **FR-10**: THE CPU SHALL expor a interface de verificação exigida pelo
  validador do repositório (`repo:FR-RV-26`), declarada em `cpu.toml`
  (FR-16): `clk`, `rst`, o PC de busca (`pc`) e a palavra buscada (`instr`)
  como sinais observáveis do top-level, o banco de registradores como array
  1-D em `regfile_inst.regs`, e a RAM de dados como `signal memory` dentro da
  instância `data_ram_inst`, filha direta do top-level. WHERE um array é
  observado, ele SHALL ser unidimensional (`array (0 to N) of
  std_logic_vector(31 downto 0)`), porque o VPI do GHDL não expõe arrays 2-D
  ao cocotb (`../../specs/decisions.md`, ADR-002).
  THE CPU SHALL ADICIONALMENTE manter `dbg_pc`, `dbg_instr` e `dbg_valid`
  (ativo só quando uma instrução real é aposentada no ciclo): a porta de
  trace de aposentadoria não é usada pelo validador, mas é o que permite
  cobertura dinâmica de instrução e é preservada pelo princípio 8.

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

- **FR-13**: THE CPU SHALL carregar a imagem de ROM sem passo manual de
  edição de fonte, por um de dois caminhos selecionados pelo generic
  `ROM_INIT_FILE` do top-level:
  - `ROM_INIT_FILE = ""` (default): a imagem vem do pacote VHDL gerado
    `rom_image_pkg.vhd`, derivado do `.rm` do programa montado. É o caminho
    usado pela síntese (fase 5) e o comportamento original do design, que o
    princípio 8 preserva intacto;
  - `ROM_INIT_FILE = <caminho>`: a imagem vem de um arquivo `.ram` lido **na
    elaboração** (`repo:FR-RV-08`, `repo:FR-RV-09`; formato em
    `../../specs/decisions.md`, ADR-003 — uma palavra de 32 bits por linha,
    8 dígitos hexadecimais, `#` inicia comentário).

  A carga SHALL acontecer na elaboração, nunca em tempo de execução: o cocotb
  não consegue escrever em ROM no GHDL — a escrita é silenciosamente
  ignorada (ADR-003).

- **FR-14**: THE CPU SHALL NOT implementar `fence`, `fence.i`, `ecall`,
  `ebreak`, instruções de CSR (Zicsr), instruções atômicas, ponto flutuante,
  SIMD, interrupções, MMU ou modos de privilégio. Essas instruções **não
  entram** em `declared_instructions` e, portanto, não são exercitadas pela
  suíte de conformidade do validador, que cobre exatamente RV32I e a extensão
  M (`repo:FR-RV-04`, `repo:FR-RV-13`); WHEN uma palavra de instrução não
  reconhecida é buscada, THE CPU SHALL tratá-la como `nop` (nenhuma escrita
  em registrador nem em memória) e seguir para `PC+4`.
  *(rubrica: syscall_trap=False, tem_interrupcoes=False, mmu=False,
  modos_privilegio=False, ponto_flutuante=False, simd=False,
  instrucoes_atomicas=False)*

- **FR-15**: THE CPU SHALL expor o generic booleano `RV32M_ENABLE` no
  top-level, WHERE `true` habilita as 8 instruções da extensão M (FR-04) e
  `false` as torna ilegais — decodificadas como `nop`, exatamente como
  qualquer outro encoding não implementado (FR-14) —, de modo que a **mesma
  base de código** seja verificável como RV32I puro e como RV32IM
  (`repo:FR-RV-16`). WHEN `RV32M_ENABLE = false`, THE CPU SHALL NOT
  instanciar a unidade de multiplicação/divisão, para que a diferença de área
  medida na fase 5 seja a da extensão de fato, e não de lógica morta que a
  síntese poderia ou não remover.

  A evolução é por **parametrização**, não por duplicação da árvore de fontes
  nem por deleção do que já funcionava (constituição, princípio 8); o
  baseline RV32I medido sob o mesmo testbench é o que dá sentido a qualquer
  afirmação sobre a extensão (princípio 9).

- **FR-16**: THE CPU SHALL ser acompanhada de um manifesto `cpu.toml` na raiz
  do seu diretório, declarando ao validador do repositório como exercitá-la —
  ordem de análise das fontes, clock, reset, generic de carga de programa,
  caminhos observáveis e modo de parada — sem que o validador conheça o RTL
  (`repo:FR-RV-26`). WHERE o manifesto não declara um caminho, o item
  correspondente SHALL sair como não observado no relatório, nunca como
  estimativa (`repo:NFR-RV-02`).

  O modo de parada SHALL ser `fetch_pc`: sendo monociclo (FR-05), esta CPU
  não tem busca especulativa, e no auto-laço `halt: j halt` o PC de busca
  fica literalmente estacionário (`../../specs/decisions.md`, ADR-008).

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

- **NFR-04** (verificabilidade): THE CPU SHALL ser verificada por execução
  real de cocotb sobre GHDL em dois níveis, sem hardware adicional dedicado a
  teste além do trio `dbg_*`:
  - **por bloco** — as 10 suítes de `test/<bloco>/`, derivadas destes
    requisitos (fase 4);
  - **em nível de programa** — a suíte de conformidade do validador do
    repositório (`python -m rvverify`), nas duas etapas RV32I e RV32IM
    (`repo:FR-RV-26`, `repo:FR-RV-27`), cujos valores esperados vêm do modelo
    de referência em `rvverify/reference.py` e **não** de constante escrita à
    mão.

  Nenhum resultado SHALL ser declarado sem a execução correspondente ter
  rodado e o exit code ter sido conferido (constituição, princípios 4 e 10).
  **Reprovar é um resultado legítimo** (`repo:FR-RV-26`).

## Lacunas de spec identificadas na fase 1

Registradas aqui em vez de contornadas em silêncio (constituição do
pipeline, princípio 5).

- **SPEC-GAP-01** — `validate_cross_fields()`
  (`legado/src/spechdl/ingestion/schema.py:258`) modela o orçamento de bits da
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

## Reconciliação com a spec vigente do repositório

Registrada aqui em vez de contornada em silêncio (constituição, princípio 5),
porque esta CPU foi gerada contra um contrato que o repositório não tem mais.

**O que aconteceu.** As fases 1 a 4 desta CPU rodaram no branch
`Implementing-.asm-and-.rm-tests`, que havia acrescentado à spec do pipeline
as fases 3b e 4b (FR-16 a FR-29: fixture golden em `software/riscv_base_test/`,
comparação de RAM endereço por endereço contra `expected_ram.json`, cobertura
dinâmica por porta de trace). Esse branch divergiu de `main` em `f884a4e` e
nunca foi integrado. `main` seguiu outro caminho para o mesmo problema: o
validador de terminal `rvverify` (`repo:FR-RV-26` a `FR-RV-35`), com montador
próprio (`rvverify/asm.py`, ADR-004), modelo de referência
(`rvverify/reference.py`) e suíte de conformidade de 35 casos. Na
reorganização da ADR-013 a pasta `examples/` deixou de existir.

**Como foi resolvido.** Vale a spec de `main`, que é a mais recente:

| contrato do branch (3b/4b) | contrato vigente (`main`) |
|---|---|
| `repo:FR-RV-26` — interface de verificação padrão | `repo:FR-RV-26` — manifesto `cpu.toml` (FR-10, FR-16) |
| `pipeline:FR-21` — `.rm` na ROM via pacote gerado | `repo:FR-RV-08/09` — `.ram` por `ROM_INIT_FILE` na elaboração (FR-13) |
| `pipeline:FR-22` — `expected_ram.json` escrito antes da simulação | `rvverify/reference.py` — modelo de referência executável |
| `pipeline:FR-23/24` — comparação de RAM endereço por endereço | `repo:FR-RV-27/28` — veredito e diagnóstico estruturado por caso |
| `repo:FR-RV-26/26` — cobertura dinâmica pela porta de trace | `repo:FR-RV-04/13` — 35 casos cobrindo RV32I e a extensão M |
| `pipeline:FR-29` — baseline antes da extensão | `repo:FR-RV-16` — duas etapas na mesma base, via `RV32M_ENABLE` (FR-15) |

**O que isso custou e o que ganhou.** Custou duas mudanças de RTL, ambas por
parametrização e nenhuma por deleção (princípio 8): o generic `ROM_INIT_FILE`
(FR-13) e o generic `RV32M_ENABLE` (FR-15). Ganhou um juiz independente: os
valores esperados passam a vir de um modelo de referência executável em vez
de uma tabela derivada à mão, e a mesma suíte que julga as CPUs de referência
de `cpus/` julga esta — o que torna o resultado comparável.

**O que foi preservado.** As 10 suítes de bloco de `test/` continuam válidas e
continuam sendo executadas: elas verificam os blocos contra **estes**
requisitos (FR-01 a FR-12), que a reconciliação não mudou. Os programas de
`software/` e o pacote `rom_image_pkg.vhd` seguem versionados e seguem sendo
o default de `ROM_INIT_FILE`, portanto o caminho de síntese da fase 5 é o
mesmo que sempre foi.
