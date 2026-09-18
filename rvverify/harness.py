#!/usr/bin/env python3
"""Harness cocotb PARAMETRIZADO por manifesto: clock, reset, parada, metricas.

REQ: FR-RV-21 (reset, clock, teto de ciclos, termino normal, travamento,
primeiro ciclo de falha, exit code), FR-RV-24 (metricas de eficiencia),
FR-RV-06 (leitura de registradores e RAM), NFR-RV-02 (nada e declarado como
medido sem a ferramenta correspondente).

Este modulo nao sabe nada sobre nenhuma CPU especifica. Tudo o que ele le
dentro do design vem de caminhos declarados no `cpu.toml`:

    [observe].ram          array 1-D de palavras -- OBRIGATORIO
    [observe].registers    array 1-D de 32 palavras -- opcional
    [observe].pc_fetch     PC de busca -- opcional (diagnostico e snapshot)
    [metrics].*            sinais de eficiencia -- opcionais

DEGRADACAO GRACIOSA. O que nao foi declarado nao vira estimativa: vira
`null` com o motivo escrito ao lado, e o campo `unobserved` do relatorio
lista tudo o que ficou de fora. Um numero so aparece aqui se saiu de um
sinal real, num ciclo real de simulacao.

TRES MODOS DE PARADA, e a razao de serem tres:

    commit_pc     pipeline com busca especulativa. O auto-laco so terminou
                  quando a INSTRUCAO DE SALTO do endereco de parada esta no
                  estagio de commit e e tomada. Observar o PC de busca aqui
                  daria resultado errado: numa CPU always-not-taken que
                  resolve saltos em EX, o PC de busca visita o endereco de
                  parada uma vez por iteracao de laco (ADR-008).
    fetch_pc      monociclo/multiciclo sem especulacao. O PC de busca fica
                  ESTACIONARIO no auto-laco; e isso que se observa.
    fixed_cycles  roda N ciclos e le a RAM. Sempre funciona, nao mede nada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer

from .manifest import CpuManifest

__all__ = [
    "CpuHarness",
    "CpuTimeout",
    "ObservationError",
    "RunMetrics",
    "resolve_handle",
]

# Convencao de parada (ADR-003): auto-laco. Usado apenas no reconhecimento
# aproximado, quando o chamador nao informa os enderecos de parada.
HALT_JAL_SELF = 0x0000006F    # JAL x0, 0
HALT_BEQ_SELF = 0x00000063    # BEQ x0, x0, 0
HALT_ENCODINGS = (HALT_JAL_SELF, HALT_BEQ_SELF)


class ObservationError(AssertionError):
    """Um caminho declarado em [observe]/[metrics] nao existe no design."""


class CpuTimeout(Exception):
    """A CPU nao terminou dentro do teto de ciclos (FR-RV-21: travamento).

    `dados` carrega o mesmo diagnostico da mensagem, estruturado, para quem
    precisa apresenta-lo sem interpretar texto (FR-RV-28).
    """

    def __init__(self, message: str, dados: dict | None = None):
        super().__init__(message)
        self.dados = dados or {}


# --------------------------------------------------------------------------
# resolucao de caminhos dentro do DUT
# --------------------------------------------------------------------------

def _children(handle: Any) -> list[str]:
    """Nomes dos sub-handles de um escopo, para a mensagem de erro."""
    names: list[str] = []
    try:
        for child in handle:
            raw = getattr(child, "_name", None) or getattr(child, "_path", None)
            if raw:
                names.append(str(raw).rsplit(".", 1)[-1])
    except Exception:  # noqa: BLE001 -- enumerar e best effort
        pass
    if not names:
        try:
            names = list(getattr(handle, "_sub_handles", {}).keys())
        except Exception:  # noqa: BLE001
            pass
    return sorted({str(n) for n in names})


def resolve_handle(dut: Any, dotted: str, *, field_name: str) -> Any:
    """Percorre `dotted` a partir do DUT, atributo a atributo.

    A mensagem de erro diz qual passo falhou e o que existe naquele escopo --
    sem isso, um caminho errado no manifesto vira um AttributeError sem
    contexto no meio da simulacao.
    """
    obj = dut
    walked: list[str] = []
    for segment in dotted.split("."):
        try:
            nxt = getattr(obj, segment)
        except Exception as e:  # noqa: BLE001 -- o VPI levanta varios tipos
            escopo = ".".join(walked) if walked else "<topo do DUT>"
            disponiveis = _children(obj)
            lista = (", ".join(disponiveis) if disponiveis
                     else "(nao foi possivel enumerar os filhos deste escopo)")
            raise ObservationError(
                f"o manifesto declara {field_name} = {dotted!r} mas "
                f"{segment!r} nao existe em {escopo!r}; "
                f"sinais disponiveis: {lista}"
            ) from e
        if nxt is None:
            escopo = ".".join(walked) if walked else "<topo do DUT>"
            raise ObservationError(
                f"o manifesto declara {field_name} = {dotted!r} mas "
                f"{segment!r} resolveu para None em {escopo!r}"
            )
        obj = nxt
        walked.append(segment)
    return obj


def _safe_int(handle: Any) -> int | None:
    """Le um sinal tolerando metavalores (U/X) dos primeiros ciclos."""
    if handle is None:
        return None
    try:
        return int(handle.value)
    except Exception:  # noqa: BLE001
        return None


def _bit(handle: Any) -> int | None:
    """Le um std_logic como 0/1; devolve None em metavalor."""
    if handle is None:
        return None
    try:
        s = str(handle.value)
    except Exception:  # noqa: BLE001
        return None
    return int(s) if s in ("0", "1") else None


# --------------------------------------------------------------------------
# metricas
# --------------------------------------------------------------------------

@dataclass
class RunMetrics:
    """Metricas observadas numa execucao real.

    REQ: FR-RV-24, NFR-RV-02. Cada campo aqui vem de contagem de sinal real
    durante uma execucao do GHDL. O que nao foi declarado no manifesto nao
    e contado nem estimado -- sai como `null` com o motivo.
    """

    clock_period_ns: int = 10
    observes_instructions: bool = False
    observes_m: bool = False
    measures_cycles: bool = True
    unobserved: list[str] = field(default_factory=list)

    cycles: int = 0
    fetches: int = 0            # ciclos em que a busca avancou (stall = 0)
    stalls: int = 0             # ciclos com stall = 1
    flush_d: int = 0            # ciclos com flush_d = 1
    flush_f: int = 0            # ciclos com flush_f = 1
    m_dispatches: int = 0       # instrucoes RV32M que executaram
    halted: bool = False
    halt_pc: int | None = None
    drain_cycles: int = 0       # ciclos apos a parada, so para drenar
    pc_trace: list[int] = field(default_factory=list)

    @property
    def jumps_taken(self) -> int:
        """Saltos/branches efetivamente tomados (observavel).

        `flush_d` e assertado por DOIS motivos: stall de load-use e salto
        tomado. `stall` e assertado so pelo primeiro. A diferenca isola o
        segundo.
        """
        return max(0, self.flush_d - self.stalls)

    @property
    def instructions(self) -> int | None:
        """Instrucoes que chegaram a executar, ou None se nao observavel.

        Derivacao, a partir de sinais reais do pipeline:

            fetches                 instrucoes buscadas (ciclos sem stall)
          - flush_f                 buscadas e mortas no registrador de fetch
          - (flush_d - stalls)      buscadas e mortas no registrador de decode

        Um salto tomado mata DUAS instrucoes buscadas especulativamente,
        porque a CPU e always-not-taken e resolve o salto em EX. Um stall de
        load-use tambem assere flush_d, mas ali a instrucao nao e morta -- ela
        e re-emitida no ciclo seguinte. Por isso os ciclos de stall sao
        descontados de flush_d.

        Sem os tres sinais em [metrics] nao ha derivacao possivel, e a
        resposta e None -- nunca um numero chutado (NFR-RV-02).
        """
        if not self.observes_instructions:
            return None
        return max(0, self.fetches - self.flush_f - self.jumps_taken)

    @property
    def cpi(self) -> float | None:
        n = self.instructions
        if n is None:
            return None
        return self.cycles / n if n else float("inf")

    @property
    def flushes(self) -> int:
        return self.flush_d + self.flush_f

    @property
    def estimated_time_ns(self) -> float:
        """Tempo ESTIMADO: ciclos x periodo nominal. Nao e medicao."""
        return self.cycles * self.clock_period_ns

    def as_dict(self) -> dict:
        """Relatorio da execucao, com o que NAO foi observado explicito."""
        n = self.instructions
        cpi = self.cpi
        out: dict[str, Any] = {
            "cycles": self.cycles,
            "instructions": n,
            "cpi": round(cpi, 4) if (n and cpi is not None) else None,
            "halted": self.halted,
            "halt_pc": self.halt_pc,
            "drain_cycles": self.drain_cycles,
            "estimated_time_ns": self.estimated_time_ns,
            "clock_period_ns": self.clock_period_ns,
            "estimated_time_note":
                f"ESTIMATIVA: ciclos x periodo nominal de "
                f"{self.clock_period_ns} ns",
            "unobserved": list(self.unobserved),
        }

        if self.observes_instructions:
            out.update({
                "fetches": self.fetches,
                "stalls": self.stalls,
                "flushes": self.flushes,
                "flush_d": self.flush_d,
                "flush_f": self.flush_f,
                "jumps_taken": self.jumps_taken,
                "instructions_method":
                    "fetches - flush_f - (flush_d - stalls); sinais reais do "
                    "pipeline",
            })
        else:
            out["instructions_method"] = (
                "NAO OBSERVADO: [metrics] do cpu.toml nao declara os sinais de "
                "stall/flush necessarios para derivar o numero de instrucoes. "
                "instructions e cpi ficam null de proposito -- estimar aqui "
                "violaria NFR-RV-02."
            )

        if self.observes_m:
            out.update({
                "m_dispatches": self.m_dispatches,
                "m_stall_cycles": 0,
                "m_stall_note":
                    "o validador nao conta ciclos de stall atribuiveis a unidade "
                    "M: [metrics] nao declara sinal para isso, entao 0 aqui "
                    "significa NAO OBSERVADO, e nao medido como zero",
            })
        else:
            out["m_dispatches"] = None

        out["cycles_method"] = (
            "ciclos do fim do reset ate a parada declarada em [halt]; os ciclos "
            "de dreno do pipeline NAO entram na contagem"
            if self.measures_cycles else
            "NAO MEDIDO: [halt].mode = fixed_cycles roda um numero fixo de "
            "ciclos e nao observa o fim do programa"
        )
        return out


# --------------------------------------------------------------------------
# harness
# --------------------------------------------------------------------------

class CpuHarness:
    """Dirige uma CPU descrita por manifesto e observa o que ele declarar."""

    def __init__(self, dut, manifest: CpuManifest,
                 clock_period_ns: int | None = None):
        self.dut = dut
        self.manifest = manifest
        self.clock_period_ns = int(clock_period_ns or manifest.clock.period_ns)
        self._clock_started = False

        caps = manifest.observability()
        self.capabilities = caps
        self.metrics = RunMetrics(
            clock_period_ns=self.clock_period_ns,
            observes_instructions=caps["instructions"],
            observes_m=caps["m_instructions"],
            measures_cycles=caps["cycles"],
            unobserved=list(caps["unobserved"]),
        )

        self._cache: dict[str, Any] = {}
        # estado do modo de parada `fetch_pc`: ha quantos ciclos seguidos o PC
        # de busca esta parado no mesmo endereco de parada
        self._stationary = 0
        self._stationary_pc: int | None = None

        # -- sinais sem os quais nao ha simulacao: falham agora -------------
        self._clk = self._resolve("[clock].signal", manifest.clock.signal)
        self._rst = self._resolve("[reset].signal", manifest.reset.signal)

        # -- metricas: declaradas mas ausentes DEGRADAM, nao abortam -------
        # Uma metrica e, por definicao, informacao extra: se o sinal nao
        # existe nesta elaboracao (por exemplo uma versao mais antiga do RTL,
        # sem a unidade M), a execucao continua valida e o relatorio passa a
        # dizer que aquela metrica nao foi observada. Abortar aqui trocaria
        # uma verificacao funcional boa por nenhuma verificacao.
        mt = manifest.metrics
        self._stall = self._resolve_optional("[metrics].stall", mt.stall)
        self._flush_d = self._resolve_optional("[metrics].flush_d", mt.flush_d)
        self._flush_f = self._resolve_optional("[metrics].flush_f", mt.flush_f)
        self._m_dispatch = self._resolve_optional("[metrics].m_dispatch",
                                                  mt.m_dispatch)
        self.metrics.observes_instructions = (
            caps["instructions"]
            and None not in (self._stall, self._flush_d, self._flush_f)
        )
        self.metrics.observes_m = (caps["m_instructions"]
                                   and self._m_dispatch is not None)

    # -- resolucao de sinais ----------------------------------------------
    #
    # Os caminhos de [observe] e [halt] sao resolvidos NA PRIMEIRA LEITURA, e
    # nao na construcao, de proposito: um mesmo manifesto e usado contra
    # arvores de RTL diferentes (o A/B contra o design original, FR-RV-07), e
    # nem toda execucao le tudo. Uma foto de PC e registradores nao precisa da
    # RAM; exigir a RAM ali abortaria uma comparacao valida. Quem le, exige --
    # e ai o erro aponta o campo do manifesto e o escopo que falhou.

    def _resolve(self, field_name: str, dotted: str | None) -> Any:
        if dotted is None:
            return None
        if field_name not in self._cache:
            self._cache[field_name] = resolve_handle(self.dut, dotted,
                                                     field_name=field_name)
        return self._cache[field_name]

    def _resolve_optional(self, field_name: str, dotted: str | None) -> Any:
        """Resolve um sinal cuja ausencia vira 'nao observado' no relatorio."""
        if dotted is None:
            return None
        try:
            return self._resolve(field_name, dotted)
        except ObservationError as e:
            self.metrics.unobserved.append(
                f"{field_name} = {dotted}: declarado no manifesto mas ausente "
                f"nesta elaboracao, entao a metrica correspondente NAO foi "
                f"coletada ({e})"
            )
            return None

    @property
    def _ram(self) -> Any:
        return self._resolve("[observe].ram", self.manifest.observe.ram)

    @property
    def _registers(self) -> Any:
        return self._resolve("[observe].registers", self.manifest.observe.registers)

    @property
    def _pc_fetch(self) -> Any:
        return self._resolve("[observe].pc_fetch", self.manifest.observe.pc_fetch)

    @property
    def _instr_fetch(self) -> Any:
        return self._resolve("[observe].instr_fetch",
                             self.manifest.observe.instr_fetch)

    @property
    def _halt_pc_sig(self) -> Any:
        return self._resolve("[halt].pc", self.manifest.halt.pc)

    @property
    def _halt_taken(self) -> Any:
        return self._resolve("[halt].taken", self.manifest.halt.taken)

    # -- infraestrutura ---------------------------------------------------

    async def start_clock(self) -> None:
        if not self._clock_started:
            cocotb.start_soon(
                Clock(self._clk, self.clock_period_ns, unit="ns").start()
            )
            self._clock_started = True

    async def reset(self, cycles: int | None = None) -> None:
        """Aplica reset com a POLARIDADE declarada em [reset].active."""
        r = self.manifest.reset
        n = int(cycles if cycles is not None else r.cycles)
        self._rst.value = r.asserted
        await self.start_clock()
        for _ in range(n):
            await RisingEdge(self._clk)
        # solta o reset longe das bordas, para nao competir com escritas de
        # registrador que ocorram na borda de descida
        await Timer(max(1, self.clock_period_ns // 4), unit="ns")
        self._rst.value = r.released
        await RisingEdge(self._clk)

    # -- observacao de estado ---------------------------------------------

    @property
    def observes_registers(self) -> bool:
        return self.manifest.observe.registers is not None

    def read_reg(self, index: int) -> int:
        """Le xN do banco de registradores declarado em [observe].registers.

        x0 e arquiteturalmente zero na RISC-V, entao e devolvido como 0 por
        definicao, sem depender do que o RTL guarda na posicao 0.
        """
        if not 0 <= index <= 31:
            raise ValueError(f"registrador fora da faixa: x{index}")
        if not self.observes_registers:
            raise ObservationError(
                "leitura de registrador pedida, mas o cpu.toml nao declara "
                "[observe].registers; sem esse caminho o validador nao consegue "
                "verificar registrador nenhum (so RAM e ciclos)"
            )
        if index == 0:
            return 0
        v = _safe_int(self._registers[index])
        return 0 if v is None else v

    def read_all_regs(self) -> list[int]:
        return [self.read_reg(i) for i in range(32)]

    def read_ram_word(self, byte_addr: int) -> int:
        """Le uma palavra de 32 bits da RAM pelo endereco absoluto."""
        if byte_addr % 4 != 0:
            raise ValueError(f"endereco de RAM nao alinhado: {byte_addr:#x}")
        mem = self.manifest.memory
        if not mem.contains(byte_addr):
            raise ValueError(
                f"endereco {byte_addr:#x} fora da RAM de dados declarada em "
                f"[memory]: [{mem.ram_base:#x}, "
                f"{mem.ram_base + mem.ram_bytes:#x})"
            )
        v = _safe_int(self._ram[mem.word_index(byte_addr)])
        return 0 if v is None else v

    def read_ram_words(self, byte_addr: int, count: int) -> list[int]:
        return [self.read_ram_word(byte_addr + 4 * i) for i in range(count)]

    @property
    def pc(self) -> int | None:
        """PC de busca, se [observe].pc_fetch foi declarado."""
        return _safe_int(self._pc_fetch)

    @property
    def fetched_instruction(self) -> int | None:
        return _safe_int(self._instr_fetch)

    @property
    def halt_stage_pc(self) -> int | None:
        """PC no estagio que [halt] observa (commit ou busca)."""
        return _safe_int(self._halt_pc_sig)

    # compatibilidade com o vocabulario do pipeline de 5 estagios
    @property
    def pc_execute(self) -> int | None:
        return self.halt_stage_pc

    @property
    def jump_in_execute(self) -> bool:
        return _bit(self._halt_taken) == 1

    # -- execucao ---------------------------------------------------------

    def _sample_cycle(self) -> None:
        m = self.metrics
        m.cycles += 1

        if self._stall is not None:
            if _bit(self._stall) == 1:
                m.stalls += 1
            else:
                m.fetches += 1
        if self._flush_d is not None and _bit(self._flush_d) == 1:
            m.flush_d += 1
        if self._flush_f is not None and _bit(self._flush_f) == 1:
            m.flush_f += 1
        if self._m_dispatch is not None and _bit(self._m_dispatch) == 1:
            m.m_dispatches += 1

    async def _tick(self) -> None:
        """Avanca um ciclo e amostra depois da borda de descida.

        Amostrar na descida (e nao na subida) garante que uma escrita de
        registrador feita na borda de descida ja aconteceu quando o valor e
        lido, e vale igualmente para designs que escrevem na subida.
        """
        await RisingEdge(self._clk)
        await FallingEdge(self._clk)
        self._sample_cycle()

    def _at_halt(self, halt_pcs: set[int] | None) -> int | None:
        """Endereco de parada, se a condicao de [halt] vale AGORA."""
        mode = self.manifest.halt.mode
        if mode == "commit_pc":
            if not halt_pcs or not self.jump_in_execute:
                return None
            pc = self.halt_stage_pc
            return pc if pc in halt_pcs else None
        if mode == "fetch_pc":
            if not halt_pcs:
                return None
            pc = self.halt_stage_pc
            if pc is None or pc not in halt_pcs:
                self._stationary = 0
                self._stationary_pc = None
                return None
            # ESTACIONARIO: o mesmo endereco de parada, ciclos seguidos.
            if self._stationary_pc == pc:
                self._stationary += 1
            else:
                self._stationary_pc = pc
                self._stationary = 1
            return pc if self._stationary >= self.manifest.halt.stationary else None
        return None

    async def run_until_halt(self, max_cycles: int = 20000,
                             halt_pcs: set[int] | None = None,
                             trace_pc: bool = False) -> RunMetrics:
        """Executa ate a parada declarada em [halt] ou ate o teto de ciclos.

        REQ: FR-RV-21 -- termino normal, deteccao de travamento, primeiro
        ciclo de falha e exit code != 0.

        Depois da deteccao roda `[halt].drain` ciclos extras, para que
        escritas em RAM ainda em voo sejam concluidas; esses ciclos sao
        contados a parte, em `drain_cycles`, e NAO entram na metrica de
        ciclos.

        Travamento: teto de `max_cycles` estourado. Levanta CpuTimeout, o que
        faz o cocotb reprovar o teste e o processo sair com codigo != 0.
        """
        if self.manifest.halt.mode == "fixed_cycles":
            return await self._run_fixed_cycles(max_cycles, trace_pc)

        self._stationary = 0
        self._stationary_pc = None
        seen_pcs: dict[int, int] = {}
        fallback_visits = 0

        for _ in range(max_cycles):
            await self._tick()

            pc = self.pc
            if pc is not None:
                if trace_pc:
                    self.metrics.pc_trace.append(pc)
                seen_pcs[pc] = seen_pcs.get(pc, 0) + 1

            halted_at = self._at_halt(halt_pcs)
            if halted_at is None and not halt_pcs:
                # diagnostico: sem tabela de simbolos, reconhece o encoding do
                # auto-laco no estagio de busca. Aproximado de proposito.
                if self.fetched_instruction in HALT_ENCODINGS:
                    fallback_visits += 1
                    if fallback_visits >= 8:
                        halted_at = pc

            if halted_at is not None:
                self.metrics.halted = True
                self.metrics.halt_pc = halted_at
                await self._drain()
                return self.metrics

        raise CpuTimeout(self._timeout_message(max_cycles, halt_pcs, seen_pcs),
                         dados=self._timeout_data(max_cycles, halt_pcs, seen_pcs))

    async def _run_fixed_cycles(self, max_cycles: int,
                                trace_pc: bool) -> RunMetrics:
        """[halt].mode = fixed_cycles -- roda N ciclos e para. Nao mede nada."""
        n = int(self.manifest.halt.cycles or 0)
        if n > max_cycles:
            raise CpuTimeout(
                f"[halt].cycles = {n} e maior que o teto de {max_cycles} ciclos "
                f"pedido pelo caso de teste; aumente max_cycles ou reduza "
                f"[halt].cycles",
                dados={"max_ciclos": max_cycles, "halt_cycles": n},
            )
        for _ in range(n):
            await self._tick()
            if trace_pc:
                pc = self.pc
                if pc is not None:
                    self.metrics.pc_trace.append(pc)
        self.metrics.halted = True
        self.metrics.halt_pc = self.pc
        await self._drain()
        return self.metrics

    def _timeout_message(self, max_cycles: int, halt_pcs: set[int] | None,
                         seen_pcs: dict[int, int]) -> str:
        hottest = sorted(seen_pcs.items(), key=lambda kv: -kv[1])[:5]

        def _hex(v: int | None) -> str:
            return "None" if v is None else hex(v)

        return (
            f"CPU nao terminou em {max_cycles} ciclos (possivel travamento). "
            f"Modo de parada: {self.manifest.halt.mode}. "
            f"PC de busca = {_hex(self.pc)}, "
            f"PC observado por [halt].pc = {_hex(self.halt_stage_pc)}, "
            f"instrucao buscada = {_hex(self.fetched_instruction)}. "
            f"Enderecos de parada esperados: "
            f"{[hex(p) for p in sorted(halt_pcs)] if halt_pcs else '(nenhum informado)'}. "
            f"PCs mais visitados: {[(hex(p), n) for p, n in hottest]}. "
            f"Metricas parciais: {self.metrics.as_dict()}"
        )

    def _timeout_data(self, max_cycles: int, halt_pcs: set[int] | None,
                      seen_pcs: dict[int, int]) -> dict:
        """O diagnostico de `_timeout_message`, sem precisar ler texto."""
        hottest = sorted(seen_pcs.items(), key=lambda kv: -kv[1])[:5]
        return {
            "max_ciclos": max_cycles,
            "modo_parada": self.manifest.halt.mode,
            "pc_busca": self.pc,
            "pc_parada_observado": self.halt_stage_pc,
            "instrucao_buscada": self.fetched_instruction,
            "enderecos_de_parada": sorted(halt_pcs) if halt_pcs else [],
            "pcs_mais_visitados": [[p, n] for p, n in hottest],
            "pc_observavel": self.manifest.observe.pc_fetch is not None,
        }

    async def _drain(self) -> None:
        """Escoa o pipeline depois da parada, sem contaminar as metricas."""
        for _ in range(self.manifest.halt.drain):
            await RisingEdge(self._clk)
            await FallingEdge(self._clk)
            self.metrics.drain_cycles += 1

    async def run_cycles(self, n: int) -> RunMetrics:
        """Executa exatamente n ciclos, sem exigir termino."""
        for _ in range(n):
            await self._tick()
        return self.metrics
