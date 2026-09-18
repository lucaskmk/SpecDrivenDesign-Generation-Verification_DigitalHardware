# `rv32i_monociclo` — a segunda CPU da trilha

CPU RISC-V **RV32I monociclo**, escrita do zero, com generic para ligar a
extensão **RV32M**. Uma instrução por ciclo: sem pipeline, sem estágios, sem
unidade de hazard, sem forwarding e sem stall.

## Por que ela existe

São duas razões, e as duas importam:

**(a) É o exemplo de "o aluno faz do zero".** A trilha vai virar um validador
de CPUs: o aluno entrega uma CPU e o sistema verifica automaticamente se ela
implementa RV32I e, depois, RV32IM. Esta é a CPU de partida para quem escolhe
escrever a sua própria em vez de modificar uma existente — pequena o bastante
para caber na cabeça (quatro arquivos VHDL próprios), completa o bastante para
passar na suíte de conformidade.

**(b) É a prova de que o validador não está preso a um design.** Até aqui a
trilha tinha **uma** CPU verificada — `cpus/rv32i_pipeline`, pipeline de 5
estágios — e o testbench lia 11 sinais internos pelo nome exato, com o mapa de
memória escrito no código. Um mecanismo assim não é um validador: é um
testbench de um design só. Se a **mesma** suíte de conformidade passa nesta CPU
**e** na pipeline, o mecanismo está provado. Esta CPU foi escrita justamente
para ser o mais diferente possível da outra onde isso importa (microarquitetura,
resolução de salto, nome do top-level) e idêntica onde não importa (mapa de
memória, convenção de parada, polaridade de reset).

## O que é próprio e o que é reaproveitado

As memórias e a unidade RV32M já estavam verificadas na trilha, e reescrevê-las
só criaria uma segunda chance de errar. Elas são **referenciadas por caminho
relativo** na lista `sources` do `cpu.toml` — não há cópia:

| Arquivo | Origem |
|---|---|
| `cpu_package.vhd`, `memory_package.vhd` | `../rv32i_pipeline/src/` — tipos e mapa de memória |
| `instruction_memory.vhd` | `../rv32i_pipeline/src/` — ROM com generic `ROM_INIT_FILE` |
| `data_ram.vhd`, `data_rom.vhd`, `data_memory.vhd` | `../rv32i_pipeline/src/` — RAM/ROM de dados e o roteamento por endereço |
| `mul_div_unit.vhd` | `../rv32i_pipeline/src/` — as 8 instruções RV32M, já verificadas |
| **`src/mono_alu.vhd`** | **próprio** — ALU combinacional |
| **`src/mono_control.vhd`** | **próprio** — decodificador + controle, num bloco só |
| **`src/mono_regfile.vhd`** | **próprio** — banco de registradores 1-D |
| **`src/cpu_monocycle.vhd`** | **próprio** — top-level e datapath |

Reaproveitar as memórias tem um efeito colateral valioso: o **mapa de memória
fica idêntico** ao da CPU pipeline (DATA_ROM em `0x00FC8000`, DATA_RAM em
`0x00FC8100`, 512 bytes), então os mesmos programas `.asm` e as mesmas imagens
`.ram` rodam nas duas sem nenhuma adaptação. É isso que torna a comparação
honesta.

## O ciclo, em uma figura

```
    pc (único registrador do núcleo)
      │
      ├─► instruction_memory   (leitura assíncrona)
      │        │
      │        ├─► mono_control (decodifica tudo de uma vez: selects,
      │        │                 imediato, largura de acesso, classe do salto)
      │        │        │
      │        │        ├─► mono_regfile  (leitura assíncrona de rs1/rs2)
      │        │        ├─► mono_alu      ─┐
      │        │        └─► mul_div_unit  ─┴─► exec_result
      │        │                                 │
      │        │                                 ├─► data_memory (leitura assíncrona)
      │        │                                 └─► mux de writeback
      │        └─► comparador de branch ──► pc_next
      │
      └─◄ na BORDA DE SUBIDA, tudo de uma vez:
           pc <= pc_next, o banco comita rd, a RAM comita o store.
```

Todos os três comits usam valores calculados a partir do estado que existia no
**início** do ciclo, então não há corrida leitura-depois-de-escrita dentro do
ciclo — e é exatamente por isso que não existe hazard nenhum para tratar.

## Como rodar

O smoke test é **autossuficiente**: não depende do pacote `rvverify` nem dos
testes de `cpus/rv32i_pipeline/test/`. Uma CPU cujo papel é provar independência
não pode ter o próprio teste amarrado ao outro design.

```bash
# dentro da WSL, na raiz do repositório
RV_BUILD_ROOT=$HOME/rvb_mono ~/venv-cocotb/bin/python -m pytest \
    cpus/rv32i_monociclo/test/test_monociclo.py -o addopts= -q
```

O `RV_BUILD_ROOT` próprio é obrigatório: dois GHDL escrevendo na mesma
biblioteca a corrompem. O `-o addopts=` também, porque o `pyproject.toml`
aponta o pytest para outra trilha.

Só para compilar e elaborar, sem simular:

```bash
ghdl -a --std=08 <as 11 fontes de cpu.toml, na ordem> && ghdl -e --std=08 cpu_monocycle
```

### O que a suíte cobre

| Teste | O que exercita |
|---|---|
| `test_r_type` | as 10 operações R-type, 18 casos com valores de borda |
| `test_i_type` | as 9 operações I-type, 18 casos, incluindo os extremos do imediato de 12 bits |
| `test_lui_auipc` | LUI e AUIPC, com o endereço vindo da tabela de símbolos do montador |
| `test_load_store_larguras` | LB/LBU/LH/LHU/LW e SB/SH/SW, com modelo little-endian conferido em Python |
| `test_branches` | os 6 branches, cada um tomado **e** não tomado (14 casos) |
| `test_jal_jalr` | JAL grava PC+4; JALR desvia por registrador e zera o bit 0 do alvo |
| `test_x0_sempre_zero` | x0 resiste a I-type, R-type, U-type, load e link de JAL |
| `test_laco_com_dependencia` | somatório em laço, soma de vetor com load-use imediato |
| `test_rv32m` | as 8 instruções M, 64 casos, com divisão por zero e overflow `(-2^31)/(-1)` |
| `test_rv32m_desligado_nao_conta_dispatch` | controle: `m_dispatch` é zero constante com `RV32M_ENABLE=false` |
| `test_travamento_e_detectado` | um programa que nunca para **tem** de reprovar por teto de ciclos |

Todo valor esperado vem do modelo de referência
(`cpus/rv32i_pipeline/test/reference_model.py`) ou de um modelo Python da
semântica de memória — nenhum foi copiado de uma execução.

Duas invariantes da microarquitetura são verificadas em **toda** execução, e
não assumidas: `instructions == cycles` (CPI exatamente 1) e o armazenamento de
x0 nunca escrito. Além disso, o testbench confirma que o PC ficou mesmo
**estacionário** no auto-laço antes de declarar parada — se não ficar, o modo
`fetch_pc` do manifesto não valeria para esta CPU e o teste diz isso.

## O contraste com a CPU pipeline

Este é o ponto do exercício. As duas CPUs usam o mesmo contrato de manifesto; o
que muda, e por quê:

| Campo | `RISCV32I` (pipeline) | `rv32i_monociclo` | Motivo |
|---|---|---|---|
| `[design].top` | `CPU` | `cpu_monocycle` | Nome diferente **de propósito**: se o validador funcionasse só com `CPU`, o campo `top` do manifesto seria decorativo. |
| `[design].sources` | 20 arquivos locais | 11, sete deles por caminho relativo à outra CPU | O manifesto tem de aceitar fontes fora do diretório da CPU. |
| `[halt].mode` | `commit_pc` | **`fetch_pc`** | A diferença mais importante. Ver abaixo. |
| `[halt].taken` | `jump_e` | **ausente** | `fetch_pc` não precisa distinguir busca especulativa de execução real: não há busca especulativa. |
| `[halt].drain` | 5 | 2 | Não há pipeline para drenar. O `sw` anterior ao auto-laço já comitou na mesma borda em que o PC virou o endereço de parada; 2 é margem. |
| `[metrics].stall` | `stall_pc` | **ausente** | Não existe stall num monociclo. |
| `[metrics].flush_d`, `flush_f` | `flush_d`, `flush_f` | **ausentes** | Não existe flush: o salto é resolvido no ciclo da busca, então nada especulativo entra no pipeline (não há pipeline). |
| `[metrics].m_dispatch` | `m_dispatch_e` | `m_dispatch` | Este **existe** nas duas, e vale 0 constante quando `RV32M_ENABLE=false`. |

O critério foi: **deixar ausente o que não existe, em vez de inventar um sinal
para preencher o campo**. Um `stall` cravado em `'0'` só para satisfazer o
manifesto seria uma mentira educada — o validador degrada graciosamente e
reporta o que não conseguiu observar, que é o comportamento correto (NFR-RV-02).

### Por que `fetch_pc` aqui e `commit_pc` lá

A convenção de parada da trilha é o auto-laço (`halt: j halt`). A pergunta é
como o testbench percebe que o programa chegou lá.

**Na CPU pipeline não dá para olhar o PC de busca.** Ela é always-not-taken e
resolve saltos só no estágio EX. Num laço como

```asm
loop:  bge  x6, x7, fim
       ...
       j    loop
fim:   sw   x5, 0(x11)
halt:  j    halt
```

o `j loop` só é resolvido depois que a busca **já visitou especulativamente**
os dois endereços seguintes — inclusive o do auto-laço. O PC de busca passa
pelo endereço de parada **uma vez por iteração**, muito antes do fim. Observar a
busca declara término no meio do laço e produz resultado errado; isso já causou
um bug real na trilha (`specs/decisions.md`, ADR-008). Por isso lá a parada é
reconhecida no **commit**: `pc_e == endereço_de_parada and jump_e == '1'`.

**Aqui o PC realmente para.** Branch e salto são resolvidos combinacionalmente
no mesmo ciclo da busca, então nunca existe um PC especulativo. No auto-laço
`pc_next = pc`, e o PC fica literalmente estacionário. `fetch_pc` é o modo
certo, é mais simples, e não exige que o design exponha um sinal `taken`.

A lição para o validador é essa: **os três modos de parada não são preferências
de estilo, são fatos da microarquitetura**, e o manifesto é onde a CPU declara
qual fato vale para ela.

### RV32I → RV32IM: a mesma tarefa nas duas CPUs

As duas expõem o generic `RV32M_ENABLE : boolean := false`, e nas duas ligá-lo
instancia a mesma `mul_div_unit.vhd` num bloco `generate` e muxa o resultado
sobre o da ALU. Como a unidade é puramente combinacional, uma instrução M custa
**um ciclo**, igual a qualquer outra: a extensão muda área e caminho crítico,
nunca a contagem de ciclos (o mesmo trade-off do ADR-007). Então o exercício
"estenda sua CPU de RV32I para RV32IM" vale, palavra por palavra, para as duas.

## Limitações conhecidas

- **Sem FENCE, ECALL e EBREAK.** A CPU alvo da trilha também não os implementa
  (ADR-000); mantê-los fora deixa as duas comparáveis. Essas codificações caem
  no braço `others` do decodificador e são inertes: não escrevem registrador
  nem memória.
- **Sem detecção de instrução ilegal e sem exceções.** Uma codificação
  desconhecida é ignorada, não gera trap. É a mesma escolha da CPU pipeline.
- **Sem CSR, sem modos de privilégio, sem interrupções.** Fora do escopo de
  RV32I base para esta trilha.
- **Caminho crítico longo.** É o preço estrutural do monociclo: busca, decode,
  leitura de registrador, ALU (ou divisor de 32 estágios, com RV32M ligado),
  acesso à memória e writeback cabem todos num único período de clock. A
  comparação de área e frequência com a pipeline é trabalho de síntese real
  (Yosys), não de estimativa.
