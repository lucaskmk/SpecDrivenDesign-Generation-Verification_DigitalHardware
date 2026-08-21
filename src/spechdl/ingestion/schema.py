"""Schema da rubrica de especificação — REQ: FR-01

Cada campo é um dict com: key, label, type ("bool" | "int" | "float" |
"choice" | "coded"), help (opcional), min/max/default (numéricos),
options (choice/coded) e children (campos só relevantes se este campo
booleano for True — implementa o skip logic).

"choice" = seleciona um valor entre alguns literais (ex.: largura de
palavra: 8/16/32/64). "coded" = seleciona um rótulo, mas guarda um código
numérico (ex.: política de substituição).

Este módulo é a única fonte de verdade do schema: o formulário Streamlit
(`web_form.py`) e, futuramente, o parser de EARS (T1.2) leem daqui — não
duplicar as perguntas em outro lugar.
"""
from __future__ import annotations

import math
from typing import Any


def _f(key, label, type_, **kw):
    return {"key": key, "label": label, "type": type_, **kw}


SCHEMA: list[dict] = [
    {
        "section": "Modelo geral da máquina",
        "fields": [
            _f("largura_palavra", "Largura da palavra (bits)", "choice", options=[8, 16, 32, 64], default=32),
            _f("largura_endereco", "Largura do endereço (bits)", "int", min=1, max=64, default=32,
               help="define o espaço endereçável"),
            _f("harvard", "Harvard (memórias de instrução e dados separadas)?", "bool",
               help="Se false, von Neumann"),
            _f("load_store_puro", "Load/store puro (RISC)?", "bool",
               help="Se false, ALU pode operar direto na memória"),
            _f("enderecamento_por_byte", "Endereçamento por byte?", "bool", help="Se false, por palavra"),
            _f("little_endian", "Little-endian?", "bool"),
            _f("exige_acesso_alinhado", "Exige acessos alinhados?", "bool"),
            _f("num_registradores", "Número de registradores de propósito geral", "int", min=1, max=256, default=32),
            _f("largura_registrador", "Largura do registrador (bits)", "int", min=1, max=64, default=32),
            _f("registrador_zero_fixo", "Registrador zero fixo (R0 sempre 0)?", "bool"),
            _f("banco_fp_separado", "Banco de registradores separado para FP?", "bool"),
        ],
    },
    {
        "section": "ISA e formato de instrução",
        "fields": [
            _f("largura_instrucao", "Largura da instrução (bits)", "int", min=1, max=256, default=32),
            _f("tamanho_fixo_instrucao", "Tamanho fixo de instrução?", "bool",
               help="Se false, é de tamanho variável"),
            _f("num_formatos_instrucao", "Quantos formatos de instrução (tipo R/I/J)", "int", min=1, max=16, default=3),
            _f("bits_opcode", "Bits de opcode", "int", min=1, max=32, default=6),
            _f("num_instrucoes", "Quantidade de instruções no conjunto", "int", min=1, max=4096, default=32),
            _f("usa_campo_funct", "Usa campo funct (extensão de opcode)?", "bool"),
            _f("bits_imediato", "Bits de imediato", "int", min=0, max=64, default=16),
            _f("imediato_sinal_extendido", "Imediato com extensão de sinal?", "bool", help="Se false, zero-extend"),
            _f("tres_operandos", "Três operandos (rd, rs, rt)?", "bool", help="Se false, dois (destino = fonte)"),
            _f("num_modos_enderecamento", "Número de modos de endereçamento", "int", min=0, max=16, default=1),
            _f("modo_base_deslocamento", "Base + deslocamento?", "bool"),
            _f("modo_indexado", "Indexado (reg + reg)?", "bool"),
            _f("modo_pc_relativo", "PC-relativo nos desvios?", "bool"),
            _f("modo_auto_inc_dec", "Auto-incremento/decremento?", "bool"),
            _f("push_pop_dedicados", "Push/pop dedicados?", "bool"),
            _f("tem_registrador_flags", "Tem registrador de flags (Z, N, C, V)?", "bool",
               help="Se false, comparação vai pra registrador (estilo slt do MIPS)"),
            _f("desvio_usa_flags", "Desvios condicionais usam flags?", "bool"),
            _f("tem_delay_slot", "Tem delay slot de branch?", "bool"),
            _f("tem_call_link", "Tem instrução de chamada com link (jal)?", "bool"),
            _f("mult_hardware", "Multiplicação em hardware?", "bool"),
            _f("div_hardware", "Divisão em hardware?", "bool"),
            _f("barrel_shifter", "Barrel shifter (shift em 1 ciclo)?", "bool"),
            _f("ponto_flutuante", "Ponto flutuante?", "bool", children=[
                _f("largura_fp", "Largura FP (bits)", "choice", options=[32, 64], default=32),
                _f("ieee754_completo", "IEEE-754 completo?", "bool"),
            ]),
            _f("simd", "SIMD/vetorial?", "bool", children=[
                _f("largura_vetor", "Largura do vetor (bits)", "int", min=1, max=1024, default=128),
                _f("num_lanes", "Número de lanes", "int", min=1, max=64, default=4),
            ]),
            _f("instrucoes_atomicas", "Instruções atômicas (LL/SC ou CAS)?", "bool"),
            _f("syscall_trap", "syscall/trap dedicado?", "bool"),
            _f("nop_explicito", "NOP explícito na ISA?", "bool"),
        ],
    },
    {
        "section": "Microarquitetura (datapath + controle)",
        "fields": [
            _f("estagios_pipeline", "Número de estágios de pipeline (1 = monociclo)", "int", min=1, max=32, default=1),
            _f("multiciclo_microprogramado", "Multiciclo microprogramado?", "bool",
               help="Se false, controle por lógica combinacional"),
            _f("cpi_alvo", "CPI alvo", "float", min=0.1, max=20.0, default=1.0, step=0.1),
            _f("freq_clock_mhz", "Frequência de clock alvo (MHz)", "int", min=1, max=10000, default=100),
            _f("forwarding", "Forwarding/bypass?", "bool"),
            _f("deteccao_hazard_stall", "Detecção de hazard com stall em hardware?", "bool",
               help="Se false, resolve com NOP por software"),
            _f("predicao_desvio", "Predição de desvio?", "bool", children=[
                _f("preditor_dinamico", "Dinâmica?", "bool", children=[
                    _f("entradas_bht", "Entradas do BHT", "int", min=1, max=65536, default=256),
                    _f("bits_preditor", "Bits do preditor", "int", min=1, max=4, default=2),
                ]),
            ]),
            _f("penalidade_desvio_errado", "Penalidade de desvio errado (ciclos)", "int", min=0, max=64, default=2),
            _f("superescalar", "Superescalar?", "bool", children=[
                _f("largura_emissao", "Largura de emissão (instr/ciclo)", "int", min=2, max=16, default=2),
            ]),
            _f("execucao_fora_ordem", "Execução fora de ordem?", "bool", children=[
                _f("renomeacao_registradores", "Renomeação de registradores?", "bool", children=[
                    _f("entradas_rob", "Entradas do ROB", "int", min=1, max=1024, default=32),
                ]),
            ]),
            _f("smt", "SMT?", "bool", children=[
                _f("threads_por_core", "Threads por core", "int", min=2, max=16, default=2),
            ]),
            _f("num_cores", "Número de cores", "int", min=1, max=256, default=1),
            _f("cores_homogeneos", "Cores homogêneos?", "bool", default=True),
            _f("portas_leitura_regbank", "Portas de leitura do banco de registradores", "int", min=1, max=16, default=2),
            _f("portas_escrita_regbank", "Portas de escrita do banco de registradores", "int", min=1, max=16, default=1),
            _f("num_alus", "Número de ALUs / unidades funcionais", "int", min=1, max=32, default=1),
        ],
    },
    {
        # Seção 4 tem lógica dinâmica própria (níveis de cache) — ver
        # render_memory_section() em web_form.py. Os campos aqui são só os
        # que não dependem do número de níveis.
        "section": "Hierarquia de memória",
        "fields": [
            _f("niveis_cache", "Níveis de cache", "choice", options=[0, 1, 2, 3], default=1),
            _f("tamanho_bloco_bytes", "Tamanho do bloco/linha (bytes)", "int", min=1, max=1024, default=64),
            _f("write_back", "Write-back?", "bool", help="Se false, write-through", default=True),
            _f("write_allocate", "Write-allocate no miss de escrita?", "bool"),
            _f("politica_substituicao", "Política de substituição", "coded", options=[
                (0, "LRU"), (1, "FIFO"), (2, "aleatória"), (3, "pseudo-LRU"),
            ], default=0),
            _f("penalidade_miss_ciclos", "Penalidade de miss (ciclos)", "int", min=1, max=1000, default=20),
            _f("coerencia_entre_cores", "Coerência entre cores?", "bool", children=[
                _f("protocolo_coerencia", "Protocolo", "coded", options=[
                    (0, "MSI"), (1, "MESI"), (2, "MOESI"),
                ], default=1),
            ]),
            _f("mmu", "Memória virtual/MMU?", "bool", children=[
                _f("tamanho_pagina_kb", "Tamanho da página (KB)", "int", min=1, max=1024, default=4),
                _f("entradas_tlb", "Entradas da TLB", "int", min=1, max=4096, default=64),
                _f("niveis_tabela_paginas", "Níveis da tabela de páginas", "int", min=1, max=8, default=2),
                _f("tlb_separada_id", "TLB separada I/D?", "bool"),
            ]),
            _f("largura_barramento_memoria", "Largura do barramento de memória (bits)", "int", min=8, max=1024, default=32),
            _f("capacidade_ram_mb", "Capacidade de RAM (MB)", "int", min=1, max=1_048_576, default=64),
            _f("canais_memoria", "Canais/bancos de memória", "int", min=1, max=16, default=1),
            _f("boot_rom", "Boot ROM?", "bool", children=[
                _f("tamanho_boot_rom_kb", "Tamanho (KB)", "int", min=1, max=65536, default=16),
            ]),
            _f("scratchpad", "Scratchpad local (sem cache)?", "bool"),
        ],
    },
    {
        "section": "E/S, barramento e interrupções",
        "fields": [
            _f("io_mapeada_memoria", "E/S mapeada em memória?", "bool", help="Se false, portas dedicadas", default=True),
            _f("num_perifericos", "Número de periféricos", "int", min=0, max=64, default=1),
            _f("tem_interrupcoes", "Tem interrupções?", "bool", children=[
                _f("num_linhas_interrupcao", "Número de linhas", "int", min=1, max=256, default=1),
                _f("interrupcoes_vetorizadas", "Vetorizadas?", "bool"),
                _f("interrupcoes_com_prioridade", "Com prioridade?", "bool", children=[
                    _f("niveis_prioridade", "Níveis de prioridade", "int", min=2, max=32, default=4),
                ]),
                _f("interrupcoes_aninhadas", "Aninhadas?", "bool"),
            ]),
            _f("dma", "DMA?", "bool", children=[
                _f("canais_dma", "Canais", "int", min=1, max=32, default=1),
            ]),
            _f("num_barramentos", "Número de barramentos", "int", min=1, max=8, default=1),
            _f("num_masters_barramento", "Número de masters no barramento", "int", min=1, max=16, default=1),
            _f("precisa_arbitro", "Precisa de árbitro?", "bool"),
            _f("tem_timer", "Timer?", "bool"),
            _f("tem_uart", "UART?", "bool"),
            _f("tem_gpio", "GPIO?", "bool", children=[
                _f("num_pinos_gpio", "Pinos", "int", min=1, max=256, default=16),
            ]),
            _f("tem_watchdog", "Watchdog?", "bool"),
        ],
    },
    {
        "section": "Proteção e exceções",
        "fields": [
            _f("modos_privilegio", "Modos de privilégio (kernel/usuário)?", "bool", children=[
                _f("num_niveis_privilegio", "Número de níveis", "int", min=2, max=8, default=2),
            ]),
            _f("protecao_memoria", "Proteção de memória (MPU ou MMU)?", "bool"),
            _f("excecoes_precisas", "Exceções precisas?", "bool"),
            _f("num_causas_excecao", "Número de causas de exceção suportadas", "int", min=0, max=128, default=8),
        ],
    },
    {
        "section": "Implementação física (PPA)",
        "fields": [
            _f("alvo_fpga", "Alvo é FPGA?", "bool", help="Se false, ASIC", default=True),
            _f("orcamento_area", "Orçamento de área (LUTs ou células)", "int", min=1, max=10_000_000, default=10000),
            _f("orcamento_potencia_mw", "Orçamento de potência (mW)", "int", min=1, max=1_000_000, default=500),
            _f("brams_dsps_disponiveis", "BRAMs/DSPs disponíveis", "int", min=0, max=10000, default=10),
            _f("dominios_clock", "Domínios de clock", "int", min=1, max=16, default=1),
            _f("reset_sincrono", "Reset síncrono?", "bool", default=True),
            _f("reset_ativo_baixo", "Reset ativo em nível baixo?", "bool"),
            _f("interface_debug_jtag", "Interface de debug (JTAG)?", "bool"),
        ],
    },
    {
        "section": "Software / ABI",
        "fields": [
            _f("tera_assembler_proprio", "Vai ter assembler próprio?", "bool"),
            _f("tera_compilador_c", "Compilador C?", "bool"),
            _f("tera_so_rtos", "SO/RTOS?", "bool"),
            _f("registradores_argumento", "Registradores de argumento", "int", min=0, max=32, default=4),
            _f("registradores_salvos_callee", "Registradores salvos pelo callee", "int", min=0, max=32, default=8),
            _f("tamanho_pilha_kb", "Tamanho padrão da pilha (KB)", "int", min=1, max=65536, default=4),
            _f("pilha_cresce_para_baixo", "Pilha cresce pra baixo?", "bool", default=True),
        ],
    },
]


def all_keys() -> set[str]:
    keys: set[str] = set()

    def walk(fields):
        for field in fields:
            keys.add(field["key"])
            if field.get("children"):
                walk(field["children"])

    for section in SCHEMA:
        walk(section["fields"])
    # campos da seção 4 (cache) que têm lógica dinâmica própria, fora do
    # schema declarativo — ver render_memory_section() em web_form.py
    keys |= {
        "l1_unificada",
        "l1_tamanho_kb", "l1_associatividade", "l1_latencia_hit",
        "l1i_tamanho_kb", "l1i_associatividade",
        "l1d_tamanho_kb", "l1d_associatividade",
        "l2_tamanho_kb", "l2_associatividade", "l2_latencia_hit",
        "l3_tamanho_kb", "l3_associatividade", "l3_latencia_hit",
        "hierarquia_inclusiva",
    }
    return keys


def validate_cross_fields(answers: dict[str, Any]) -> list[str]:
    """REQ: FR-03 — validação cruzada entre campos derivados.

    Implementa as 5 checagens pedidas: campo de registrador vs. nº de
    registradores, orçamento de bits da instrução, consistência de
    tamanho/associatividade/bloco de cache, espaço de endereço vs. memória
    física, e associatividade vs. número de blocos.
    """
    errors: list[str] = []
    get = answers.get

    # 1+2. bits do campo de registrador >= log2(nº de registradores), e
    # opcode + campos de registrador + imediato <= largura da instrução
    num_reg = get("num_registradores")
    if num_reg and num_reg > 0:
        reg_field_bits = max(1, math.ceil(math.log2(num_reg)))
        num_operandos_reg = 3 if get("tres_operandos") else 2
        bits_opcode = get("bits_opcode") or 0
        bits_imediato = get("bits_imediato") or 0
        largura_instrucao = get("largura_instrucao")
        if largura_instrucao:
            total = bits_opcode + (num_operandos_reg * reg_field_bits) + bits_imediato
            if total > largura_instrucao:
                errors.append(
                    f"Instrução não cabe: opcode ({bits_opcode}) + "
                    f"{num_operandos_reg} campo(s) de registrador "
                    f"({reg_field_bits} bits cada, pra endereçar "
                    f"{num_reg} registradores) + imediato ({bits_imediato}) "
                    f"= {total} bits, maior que a largura da instrução "
                    f"({largura_instrucao} bits)."
                )

    # 4. 2^(largura do endereço) >= RAM + ROM
    largura_endereco = get("largura_endereco")
    capacidade_ram_mb = get("capacidade_ram_mb")
    if largura_endereco and capacidade_ram_mb:
        espaco_enderecavel = 2 ** largura_endereco
        ram_bytes = capacidade_ram_mb * 1024 * 1024
        rom_bytes = (get("tamanho_boot_rom_kb") or 0) * 1024 if get("boot_rom") else 0
        if espaco_enderecavel < ram_bytes + rom_bytes:
            errors.append(
                f"Espaço de endereço (2^{largura_endereco} = "
                f"{espaco_enderecavel:,} bytes) menor que RAM + ROM "
                f"({ram_bytes + rom_bytes:,} bytes). Nota: espaço reservado "
                f"pra E/S mapeada em memória não entra nessa conta, esse "
                f"schema não pede o tamanho dela separadamente."
            )

    # 3+5. por nível de cache ativo: tamanho == conjuntos * associatividade *
    # bloco (checado via divisibilidade, já que "conjuntos" não é campo
    # direto), e associatividade <= número de blocos da cache.
    bloco = get("tamanho_bloco_bytes")
    niveis = get("niveis_cache") or 0
    for prefixo, nome, ativo in [
        ("l1i", "L1I", niveis >= 1 and get("l1_unificada") is False),
        ("l1d", "L1D", niveis >= 1 and get("l1_unificada") is False),
        ("l1", "L1", niveis >= 1 and get("l1_unificada") is not False),
        ("l2", "L2", niveis >= 2),
        ("l3", "L3", niveis >= 3),
    ]:
        if not ativo:
            continue
        tamanho_kb = get(f"{prefixo}_tamanho_kb")
        assoc = get(f"{prefixo}_associatividade")
        if not (tamanho_kb and assoc and bloco):
            continue
        tamanho_bytes = tamanho_kb * 1024
        if tamanho_bytes % (assoc * bloco) != 0:
            errors.append(
                f"{nome}: tamanho ({tamanho_kb} KB) não é múltiplo de "
                f"associatividade ({assoc}) × tamanho do bloco ({bloco} B) "
                f"— não dá pra formar um número inteiro de conjuntos."
            )
            continue
        num_blocos = tamanho_bytes // bloco
        if assoc > num_blocos:
            errors.append(
                f"{nome}: associatividade ({assoc}) maior que o número de "
                f"blocos da cache ({num_blocos})."
            )

    return errors
