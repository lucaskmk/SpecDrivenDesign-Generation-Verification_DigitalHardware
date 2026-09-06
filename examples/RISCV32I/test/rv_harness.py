#!/usr/bin/env python3
"""Harness cocotb para a CPU RISC-V: clock, reset, término, métricas.

REQ: FR-RV-21 (reset, clock, teto de ciclos, término normal, travamento,
primeiro ciclo de falha, waveform, exit code), FR-RV-24 (métricas de
eficiência), FR-RV-06 (leitura de registradores e RAM).

Detalhes de interface descobertos na auditoria (`specs/decisions.md`, ADR-000)
e respeitados aqui:
  * `rst` é ATIVO EM NÍVEL ALTO e assíncrono;
  * o banco de registradores escreve na BORDA DE DESCIDA do clock;
  * ROM e RAM têm latência de leitura ZERO (combinacional);
  * a RAM de dados começa em DATA_RAM_BASE_ADDRESS = 0x00FC8100.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer

# Constantes do mapa de memória (memory_package.vhd)
DATA_RAM_BASE_ADDRESS = 0x00FC8100
DATA_RAM_SIZE_BYTES = 512
DATA_ROM_BASE_ADDRESS = 0x00FC8000

CLOCK_PERIOD_NS = 10          # 100 MHz, mesmo período do CPU_tb.vhd original

# Convenção de parada (ADR-003): auto-laço.
HALT_JAL_SELF = 0x0000006F    # JAL x0, 0
HALT_BEQ_SELF = 0x00000063    # BEQ x0, x0, 0
HALT_ENCODINGS = (HALT_JAL_SELF, HALT_BEQ_SELF)

# Ciclos rodados DEPOIS de detectar a parada, só para drenar o pipeline.
# Um `sw` imediatamente antes do auto-laço ainda está em MEM/WB quando o
# auto-laço chega em EX; sem drenar, a escrita não teria acontecido ainda.
# 5 ciclos cobrem a profundidade do pipeline (5 estágios) com folga.
HALT_DRAIN_CYCLES = 5

# --------------------------------------------------------------------------
# Por que a parada NÃO é detectada olhando o PC de busca (pc_f)
# --------------------------------------------------------------------------
# A CPU é always-not-taken e resolve saltos só no estágio EX (ADR-000).
# Portanto, num laço como
#
#       loop:  bge  x6, x7, fim
#              ...
#              j    loop
#       fim:   sw   x5, 0(x11)
#       halt:  j    halt
#
# o `j loop` só é resolvido depois que `pc_f` JÁ VISITOU especulativamente os
# dois endereços seguintes -- inclusive o endereço do auto-laço de parada.
# Ou seja: `pc_f` passa pelo endereço de parada UMA VEZ POR ITERAÇÃO do laço,
# muito antes de o programa terminar. Contar visitas a `pc_f` (o que esta
# versão do harness fazia) declarava término no meio do laço e produzia
# resultado errado com CPU correta.
#
# A detecção correta observa o COMMIT, não a busca: o auto-laço terminou
# quando a própria instrução de salto do endereço de parada está no estágio
# EX e é efetivamente tomada. Isso é observável em dois sinais internos:
#
#   pc_e     -- PC da instrução que está em EX
#   jump_e   -- '1' quando a instrução em EX é JAL/JALR; o flush do
#               decode_pipeline_register zera este bit, então uma bolha
#               NUNCA tem jump_e = '1'
#
# Logo `pc_e == endereço_de_parada and jump_e == '1'` identifica exatamente a
# execução real do auto-laço, sem falso positivo especulativo.
# REQ: FR-RV-21 (término normal determinístico)


def _safe_int(handle) -> int | None:
    """Lê um sinal tolerando metavalores ('U'/'X') dos primeiros ciclos."""
    try:
        return int(handle.value)
    except Exception:  # noqa: BLE001
        return None


def _bit(handle) -> int | None:
    s = str(handle.value)
    if s in ("0", "1"):
        return int(s)
    return None


@dataclass
class RunMetrics:
    """Métricas observadas na simulação.

    REQ: FR-RV-24. Todos os campos vêm de contagem de sinais reais do
    pipeline durante uma execução do GHDL — nenhum é estimado.
    """

    cycles: int = 0
    fetches: int = 0            # ciclos em que o fetch avançou (stall_pc = 0)
    stalls: int = 0             # ciclos com stall_pc = 1
    flush_d: int = 0            # ciclos com flush_d = 1 (bolha injetada em EX)
    flush_f: int = 0            # ciclos com flush_f = 1
    m_dispatches: int = 0       # instruções RV32M que executaram (FR-RV-24)
    halted: bool = False
    halt_pc: int | None = None
    drain_cycles: int = 0       # ciclos rodados apos a parada, so para drenar
    pc_trace: list[int] = field(default_factory=list)

    @property
    def jumps_taken(self) -> int:
        """Saltos/branches efetivamente tomados (observável).

        `flush_d` é assertado por DOIS motivos (hazard_control_unit.vhd):
        stall de load-use e salto tomado. `stall_pc` é assertado só pelo
        primeiro. A diferença isola o segundo.
        """
        return max(0, self.flush_d - self.stalls)

    @property
    def instructions(self) -> int:
        """Instruções do programa que chegaram a executar (observável).

        Derivação, a partir de sinais reais do pipeline:

            fetches                 instruções buscadas (ciclos com stall_pc = 0)
          - flush_f                 buscadas e mortas no registrador de fetch
          - (flush_d - stalls)      buscadas e mortas no registrador de decode

        Um salto tomado mata DUAS instruções buscadas especulativamente
        (flush_f e flush_d juntos), porque a CPU é always-not-taken e resolve
        o salto em EX. Um stall de load-use também assere flush_d, mas ali a
        instrução não é morta -- ela é apenas re-emitida no ciclo seguinte,
        já que `stall_f` segura o registrador de fetch. Por isso os ciclos de
        stall são descontados de `flush_d`.

        Declarado explicitamente porque a CPU não tem bit de "instrução
        válida" observável (ver ADR-000). REQ: FR-RV-24, NFR-RV-02.
        """
        return max(0, self.fetches - self.flush_f - self.jumps_taken)

    @property
    def cpi(self) -> float:
        return self.cycles / self.instructions if self.instructions else float("inf")

    @property
    def flushes(self) -> int:
        return self.flush_d + self.flush_f

    @property
    def estimated_time_ns(self) -> float:
        """Tempo estimado: ciclos x período. É ESTIMATIVA (NFR-RV-02).

        Depende do período de clock realmente atingível, que não é medido aqui.
        """
        return self.cycles * CLOCK_PERIOD_NS

    def as_dict(self) -> dict:
        return {
            "cycles": self.cycles,
            "instructions": self.instructions,
            "cpi": round(self.cpi, 4) if self.instructions else None,
            "fetches": self.fetches,
            "stalls": self.stalls,
            "flushes": self.flushes,
            "flush_d": self.flush_d,
            "flush_f": self.flush_f,
            "jumps_taken": self.jumps_taken,
            "m_dispatches": self.m_dispatches,
            "m_stall_cycles": 0,
            "m_stall_note":
                "a unidade M do ADR-007 e combinacional (1 ciclo, igual a ALU), "
                "logo nao introduz stall nenhum; o custo aparece em area e caminho "
                "critico, medidos por sintese real",
            "halted": self.halted,
            "halt_pc": self.halt_pc,
            "drain_cycles": self.drain_cycles,
            "estimated_time_ns": self.estimated_time_ns,
            "clock_period_ns": CLOCK_PERIOD_NS,
            "instructions_method":
                "fetches - flush_f - (flush_d - stalls); sinais reais do pipeline",
            "cycles_method":
                "ciclos do fim do reset ate o auto-laco de parada executar em EX "
                "(pc_e == halt_pc and jump_e == 1); os ciclos de dreno do pipeline "
                "NAO entram na contagem",
            "estimated_time_note": "ESTIMATIVA: ciclos x periodo nominal de 10 ns",
        }


class CpuTimeout(Exception):
    """A CPU não terminou dentro do teto de ciclos (FR-RV-21: travamento)."""


class CpuHarness:
    """Dirige a CPU e observa seu estado interno."""

    def __init__(self, dut, clock_period_ns: int = CLOCK_PERIOD_NS):
        self.dut = dut
        self.clock_period_ns = clock_period_ns
        self.metrics = RunMetrics()
        self._clock_started = False
        # Contagem de instruções RV32M (FR-RV-24).
        #
        # Observa `m_dispatch_e`, um sinal da própria arquitetura de CPU.vhd, e
        # NÃO a instância `mul_div_unit_inst`. Dois motivos:
        #   1. a instância vive dentro de um bloco `generate`, cujo escopo o VPI
        #      expõe com um nível a mais de hierarquia;
        #   2. `m_dispatch_e` existe nas DUAS configurações -- vale 0 constante na
        #      baseline RV32I --, então a mesma métrica é coletada nos dois lados
        #      da comparação, sem caminho de código condicional.
        # `m_dispatch_e = m_op_e and write_rd_e`, e o flush zera `write_rd_e`,
        # portanto uma bolha nunca é contada como instrução M.
        self._m_dispatch = getattr(dut, "m_dispatch_e", None)

    # -- infraestrutura ---------------------------------------------------

    async def start_clock(self) -> None:
        if not self._clock_started:
            cocotb.start_soon(Clock(self.dut.clk, self.clock_period_ns, unit="ns").start())
            self._clock_started = True

    async def reset(self, cycles: int = 3) -> None:
        """Reset assíncrono ativo em ALTO (FR-RV-15: comportamento de reset)."""
        self.dut.rst.value = 1
        await self.start_clock()
        for _ in range(cycles):
            await RisingEdge(self.dut.clk)
        # solta o reset longe das bordas, para não competir com a escrita do
        # banco de registradores (que ocorre na borda de descida)
        await Timer(self.clock_period_ns // 4, unit="ns")
        self.dut.rst.value = 0
        await RisingEdge(self.dut.clk)

    # -- observação de estado ---------------------------------------------

    def read_reg(self, index: int) -> int:
        """Lê xN do banco de registradores.

        x0 é arquiteturalmente zero (`register_file.vhd` força 0 na leitura e
        descarta escrita), portanto é devolvido como 0 por definição.
        """
        if not 0 <= index <= 31:
            raise ValueError(f"registrador fora da faixa: x{index}")
        if index == 0:
            return 0
        v = _safe_int(self.dut.register_file.registers[index])
        return 0 if v is None else v

    def read_all_regs(self) -> list[int]:
        return [self.read_reg(i) for i in range(32)]

    def read_ram_word(self, byte_addr: int) -> int:
        """Lê uma palavra de 32 bits da RAM de dados pelo endereço absoluto."""
        if byte_addr % 4 != 0:
            raise ValueError(f"endereço de RAM não alinhado: {byte_addr:#x}")
        offset = byte_addr - DATA_RAM_BASE_ADDRESS
        if not 0 <= offset < DATA_RAM_SIZE_BYTES:
            raise ValueError(
                f"endereço {byte_addr:#x} fora da RAM de dados "
                f"[{DATA_RAM_BASE_ADDRESS:#x}, "
                f"{DATA_RAM_BASE_ADDRESS + DATA_RAM_SIZE_BYTES:#x})"
            )
        v = _safe_int(self.dut.data_memory.data_ram.memory[offset // 4])
        return 0 if v is None else v

    def read_ram_words(self, byte_addr: int, count: int) -> list[int]:
        return [self.read_ram_word(byte_addr + 4 * i) for i in range(count)]

    @property
    def pc(self) -> int | None:
        return _safe_int(self.dut.pc_f)

    @property
    def fetched_instruction(self) -> int | None:
        return _safe_int(self.dut.instr_f)

    # -- execução ---------------------------------------------------------

    def _sample_cycle(self) -> None:
        m = self.metrics
        m.cycles += 1

        stall = _bit(self.dut.stall_pc)
        if stall == 1:
            m.stalls += 1
        else:
            m.fetches += 1

        if _bit(self.dut.flush_d) == 1:
            m.flush_d += 1
        if _bit(self.dut.flush_f) == 1:
            m.flush_f += 1

        if self._m_dispatch is not None:
            try:
                if _bit(self._m_dispatch) == 1:
                    m.m_dispatches += 1
            except Exception:  # noqa: BLE001
                pass

    # -- estado do estágio EX (commit), usado para detectar a parada --------

    @property
    def pc_execute(self) -> int | None:
        """PC da instrução que está no estágio EXECUTE."""
        return _safe_int(self.dut.pc_e)

    @property
    def jump_in_execute(self) -> bool:
        """True quando há um JAL/JALR REAL em EX.

        O flush do decode_pipeline_register zera `jump_out`, portanto uma
        bolha nunca satisfaz esta condição -- é o que torna a detecção de
        parada imune ao fetch especulativo.
        """
        return _bit(self.dut.jump_e) == 1

    def _at_halt(self, halt_pcs: set[int] | None) -> int | None:
        """Endereço de parada, se o auto-laço está executando agora em EX."""
        if not halt_pcs:
            return None
        if not self.jump_in_execute:
            return None
        pc_e = self.pc_execute
        return pc_e if pc_e in halt_pcs else None

    async def run_until_halt(self, max_cycles: int = 20000,
                             halt_pcs: set[int] | None = None,
                             trace_pc: bool = False) -> RunMetrics:
        """Executa até o auto-laço de parada ou até o teto de ciclos.

        REQ: FR-RV-21 -- término normal, detecção de travamento, primeiro
        ciclo de falha e exit code != 0.

        Término normal: a instrução de salto que está NO endereço de parada
        chega ao estágio EX e é tomada (`pc_e == halt_pc and jump_e == '1'`).
        Ver o comentário longo no topo deste arquivo sobre por que observar
        `pc_f` seria errado. Depois da detecção, roda HALT_DRAIN_CYCLES ciclos
        extras para que escritas em RAM ainda em MEM/WB sejam concluídas;
        esses ciclos são contados à parte, em `drain_cycles`, e NÃO entram na
        métrica de ciclos.

        Travamento: teto de `max_cycles` estourado. Levanta CpuTimeout, o que
        faz o cocotb reprovar o teste e o processo sair com código != 0.

        `halt_pcs` vem da tabela de símbolos do montador (as instruções de
        auto-laço encontradas na imagem). Sem ela, cai no reconhecimento da
        instrução buscada, que é aproximado e só serve para diagnóstico.
        """
        seen_pcs: dict[int, int] = {}
        fallback_visits = 0

        for _ in range(max_cycles):
            await RisingEdge(self.dut.clk)
            # amostra depois da borda de descida, quando o writeback já ocorreu
            await FallingEdge(self.dut.clk)
            self._sample_cycle()

            pc = self.pc
            if pc is not None:
                if trace_pc:
                    self.metrics.pc_trace.append(pc)
                seen_pcs[pc] = seen_pcs.get(pc, 0) + 1

            halted_at = self._at_halt(halt_pcs)
            if halted_at is None and not halt_pcs:
                # diagnóstico: sem tabela de símbolos, reconhece o encoding do
                # auto-laço no estágio de busca. Aproximado de propósito.
                if self.fetched_instruction in HALT_ENCODINGS:
                    fallback_visits += 1
                    if fallback_visits >= 8:
                        halted_at = pc

            if halted_at is not None:
                self.metrics.halted = True
                self.metrics.halt_pc = halted_at
                await self._drain()
                return self.metrics

        hottest = sorted(seen_pcs.items(), key=lambda kv: -kv[1])[:5]
        raise CpuTimeout(
            f"CPU não terminou em {max_cycles} ciclos (possível travamento). "
            f"PC de busca = {self.pc if self.pc is None else hex(self.pc)}, "
            f"PC em EX = "
            f"{self.pc_execute if self.pc_execute is None else hex(self.pc_execute)}, "
            f"instrução buscada = "
            f"{self.fetched_instruction if self.fetched_instruction is None else hex(self.fetched_instruction)}. "
            f"Endereços de parada esperados: "
            f"{[hex(p) for p in sorted(halt_pcs)] if halt_pcs else '(nenhum informado)'}. "
            f"PCs mais visitados: {[(hex(p), n) for p, n in hottest]}. "
            f"Métricas parciais: {self.metrics.as_dict()}"
        )

    async def _drain(self) -> None:
        """Escoa o pipeline depois da parada, sem contaminar as métricas."""
        for _ in range(HALT_DRAIN_CYCLES):
            await RisingEdge(self.dut.clk)
            await FallingEdge(self.dut.clk)
            self.metrics.drain_cycles += 1

    async def run_cycles(self, n: int) -> RunMetrics:
        """Executa exatamente n ciclos, sem exigir término."""
        for _ in range(n):
            await RisingEdge(self.dut.clk)
            await FallingEdge(self.dut.clk)
            self._sample_cycle()
        return self.metrics
