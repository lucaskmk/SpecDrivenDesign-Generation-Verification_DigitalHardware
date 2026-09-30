#!/usr/bin/env python3
"""O que uma CPU gerada precisa cumprir, por tipo, e o `cpu.toml` dela.

REQ: FR-RV-47 (tipos e ISAs aceitos, `cpu.toml` deterministico, recusa do que
o rvverify nao sabe julgar), FR-RV-05, FR-RV-06, FR-RV-09, FR-RV-15, FR-RV-16.

A ideia central: tudo o que NAO precisa de IA nao passa por IA. O modelo so
escreve VHDL. O top-level, os nomes que o testbench le por hierarquia e o
manifesto sao fixados aqui -- o mesmo contrato que um aluno recebe em
`entregas/README.md`, com os nomes escolhidos de antemao. Assim o `cpu.toml`
sai sempre certo, e o modelo nao gasta iteracao adivinhando caminho de
observacao.

As interfaces das memorias e da `mul_div_unit` entram no prompt LIDAS DOS
ARQUIVOS REAIS de `cpus/rv32i_pipeline/src/`, nunca copiadas para ca: se um
arquivo fornecido mudar, o prompt muda junto.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .config import REPO_ROOT

__all__ = [
    "ErroContrato",
    "Bloco",
    "Tipo",
    "TIPOS",
    "ISAS",
    "TOP",
    "FORNECIDOS",
    "FORNECIDOS_DIR",
    "ENTIDADES_RESERVADAS",
    "validar",
    "declaracoes_de_entidade",
    "interfaces_fornecidas",
    "texto_do_contrato",
    "arquitetura_padrao",
    "renderizar_cpu_toml",
]

TOP = "cpu_top"
ISAS = ("rv32i", "rv32im")

FORNECIDOS_DIR = REPO_ROOT / "cpus" / "rv32i_pipeline" / "src"
# Ordem de ANALISE: pacotes antes de quem os usa (a mesma de entregas/_modelo).
FORNECIDOS = (
    "cpu_package.vhd",
    "memory_package.vhd",
    "mul_div_unit.vhd",
    "data_ram.vhd",
    "data_rom.vhd",
    "data_memory.vhd",
    "instruction_memory.vhd",
)
# Nomes que o modelo nao pode reusar: ja existem na biblioteca `work`.
ENTIDADES_RESERVADAS = frozenset({
    "cpu_package", "memory_package", "mul_div_unit", "data_ram", "data_rom",
    "data_memory", "instruction_memory",
})


class ErroContrato(ValueError):
    """Tipo ou ISA que o rvverify nao sabe julgar."""


@dataclass(frozen=True)
class Bloco:
    """Um bloco da decomposicao: uma entidade, um arquivo."""

    name: str
    responsibility: str
    ports: tuple[str, ...]
    satisfies: tuple[str, ...]
    design_rationale: str

    def como_dict(self) -> dict:
        return {"name": self.name, "file": f"src/{self.name}.vhd",
                "responsibility": self.responsibility, "ports": list(self.ports),
                "satisfies": list(self.satisfies),
                "design_rationale": self.design_rationale}


# --------------------------------------------------------------------------
# blocos padrao -- usados quando a decomposicao proposta pelo modelo e
# invalida (FR-RV-48 nao pode parar por causa de um JSON ruim)
# --------------------------------------------------------------------------

_REGFILE = Bloco(
    "register_file",
    "32 x 32-bit registers, two asynchronous read ports and one synchronous "
    "write port; x0 always reads 0 and writes to it are ignored.",
    ("clk : in std_logic", "rst : in std_logic",
     "rs1_addr : in std_logic_vector(4 downto 0)",
     "rs2_addr : in std_logic_vector(4 downto 0)",
     "rd_addr : in std_logic_vector(4 downto 0)",
     "rd_data : in std_logic_vector(31 downto 0)", "rd_we : in std_logic",
     "rs1_data : out std_logic_vector(31 downto 0)",
     "rs2_data : out std_logic_vector(31 downto 0)"),
    ("FR-RV-04", "FR-RV-06", "FR-RV-15"),
    "Storage is the 1-D signal `registers`, the only shape the GHDL VPI "
    "exposes to the test bench (ADR-002).",
)
_ALU = Bloco(
    "alu",
    "Combinational RV32I arithmetic, logic, shifts and comparisons.",
    ("op1 : in std_logic_vector(31 downto 0)",
     "op2 : in std_logic_vector(31 downto 0)",
     "op : in ALU_OP_TYPE_t",
     "result : out std_logic_vector(31 downto 0)"),
    ("FR-RV-04",),
    "Reuses ALU_OP_TYPE_t from cpu_package so the same selector drives the "
    "provided mul_div_unit (ADR-007).",
)
_DECODER = Bloco(
    "decoder",
    "Combinational instruction decoder and immediate generator: register "
    "indices, sign-extended immediate, ALU operation and control flags.",
    ("instr : in std_logic_vector(31 downto 0)",
     "rs1_addr : out std_logic_vector(4 downto 0)",
     "rs2_addr : out std_logic_vector(4 downto 0)",
     "rd_addr : out std_logic_vector(4 downto 0)",
     "imm : out std_logic_vector(31 downto 0)",
     "alu_op : out ALU_OP_TYPE_t", "alu_src_imm : out std_logic",
     "reg_we : out std_logic", "mem_we : out std_logic",
     "mem_width : out MEM_ACCESS_WIDTH_t", "is_load : out std_logic",
     "is_branch : out std_logic", "is_jal : out std_logic",
     "is_jalr : out std_logic", "is_lui : out std_logic",
     "is_auipc : out std_logic",
     "funct3 : out std_logic_vector(2 downto 0)"),
    ("FR-RV-04", "FR-RV-13", "FR-RV-16"),
    "Generic RV32M_ENABLE gates the funct7 = 0000001 decode, so the RV32I "
    "configuration treats the M instructions as it did before (FR-RV-16).",
)
_TOP_DESCR = ("Top level: instantiates the provided memories and the blocks "
              "above, holds the program counter and the writeback path.")


def _top(extra: str) -> Bloco:
    return Bloco(TOP, f"{_TOP_DESCR} {extra}",
                 ("rst : in std_logic", "clk : in std_logic"),
                 ("FR-RV-05", "FR-RV-06", "FR-RV-09", "FR-RV-12", "FR-RV-15",
                  "FR-RV-16"),
                 "Fixed interface of the rvverify contract (cpu.toml).")


@dataclass(frozen=True)
class Tipo:
    """Uma microarquitetura que o gerador sabe pedir e o rvverify sabe julgar."""

    nome: str
    descricao: str                      # para a tela, em portugues
    microarquitetura: str               # para o prompt, em ingles
    sinais: tuple[tuple[str, str], ...]  # sinais obrigatorios no cpu_top
    observe: dict
    halt: dict
    metrics: dict
    blocos: tuple[Bloco, ...]


TIPOS: dict[str, Tipo] = {t.nome: t for t in (
    Tipo(
        "monociclo",
        "um ciclo por instrucao; o PC e o unico registrador do nucleo",
        "Single-cycle datapath: every instruction completes in exactly one "
        "clock cycle. Fetch, decode, register read, ALU/branch, data memory "
        "access and writeback are combinational within the cycle; the PC, the "
        "register file and the data RAM commit on the rising edge. Branches "
        "and jumps are resolved in the same cycle, so there is no speculation "
        "and no flush.",
        (("pc", "std_logic_vector(31 downto 0): the PC register, address of "
                "the instruction executing in this cycle"),
         ("instr", "std_logic_vector(31 downto 0): the instruction read from "
                   "instruction_memory"),
         ("m_dispatch", "std_logic: '1' in a cycle where a real RV32M "
                        "instruction executes; constant '0' when RV32M_ENABLE "
                        "is false")),
        {"pc_fetch": "pc", "instr_fetch": "instr"},
        {"mode": "fetch_pc", "pc": "pc", "stationary": 2, "drain": 2},
        {"m_dispatch": "m_dispatch"},
        (_REGFILE, _ALU, _DECODER, _top("Single-cycle next-PC logic.")),
    ),
    Tipo(
        "multiciclo",
        "maquina de estados; cada instrucao leva de 3 a 5 ciclos",
        "Multi-cycle datapath controlled by a finite state machine (FETCH, "
        "DECODE, EXECUTE, MEMORY, WRITEBACK); an instruction takes 3 to 5 "
        "cycles and skips the states it does not need. An instruction "
        "register holds the fetched instruction. The register file and the "
        "data RAM are written at most once per instruction, only in the "
        "proper state. `pc` keeps the address of the instruction being "
        "executed until it completes and changes only in its last state.",
        (("pc", "std_logic_vector(31 downto 0): address of the instruction "
                "being executed; changes only when that instruction completes"),
         ("instr", "std_logic_vector(31 downto 0): the instruction register"),
         ("m_dispatch", "std_logic: '1' for one cycle when a real RV32M "
                        "instruction is executed; constant '0' when "
                        "RV32M_ENABLE is false")),
        {"pc_fetch": "pc", "instr_fetch": "instr"},
        # estacionario > latencia maxima de uma instrucao (entregas/_modelo)
        {"mode": "fetch_pc", "pc": "pc", "stationary": 8, "drain": 4},
        {"m_dispatch": "m_dispatch"},
        (_REGFILE, _ALU, _DECODER,
         Bloco("control_fsm",
               "Finite state machine that sequences FETCH, DECODE, EXECUTE, "
               "MEMORY and WRITEBACK and drives the write enables.",
               ("clk : in std_logic", "rst : in std_logic",
                "is_load : in std_logic", "is_store : in std_logic",
                "reg_we_decoded : in std_logic",
                "ir_we : out std_logic", "pc_we : out std_logic",
                "reg_we : out std_logic", "mem_we : out std_logic"),
               ("FR-RV-04", "FR-RV-21"),
               "Separating sequencing from decoding keeps the decoder "
               "combinational and the per-state enables in one place."),
         _top("Holds the instruction register and the state-dependent "
              "datapath registers.")),
    ),
    Tipo(
        "pipeline",
        "5 estagios com forwarding, stall de load-use e flush em salto",
        "Five-stage pipeline IF, ID, EX, MEM, WB with pipeline registers "
        "between stages. Forwarding from MEM and WB to EX; a one-cycle stall "
        "of IF and ID with a bubble into EX on a load-use hazard; branches "
        "and jumps resolved in EX with an always-not-taken predictor, "
        "flushing the two younger instructions when taken. A register "
        "written in WB must be seen by a read in ID in the same cycle "
        "(write-through bypass in the register file, or write on the "
        "falling edge).",
        (("pc_f", "std_logic_vector(31 downto 0): fetch PC"),
         ("instr_f", "std_logic_vector(31 downto 0): fetched instruction"),
         ("pc_e", "std_logic_vector(31 downto 0): PC of the instruction in EX"),
         ("jump_e", "std_logic: '1' when the instruction in EX is a valid JAL "
                    "or JALR; '0' for a bubble or a flushed instruction"),
         ("stall_pc", "std_logic: '1' in a cycle where the PC is stalled"),
         ("flush_d", "std_logic: '1' in a cycle where ID/EX is flushed"),
         ("flush_f", "std_logic: '1' in a cycle where IF/ID is flushed"),
         ("m_dispatch_e", "std_logic: '1' when a real RV32M instruction is in "
                          "EX; constant '0' when RV32M_ENABLE is false")),
        {"pc_fetch": "pc_f", "instr_fetch": "instr_f"},
        {"mode": "commit_pc", "pc": "pc_e", "taken": "jump_e", "drain": 5},
        {"stall": "stall_pc", "flush_d": "flush_d", "flush_f": "flush_f",
         "m_dispatch": "m_dispatch_e"},
        (_REGFILE, _ALU, _DECODER,
         Bloco("hazard_unit",
               "Forwarding selects for the EX operands, load-use stall and "
               "flush on taken branch or jump.",
               ("rs1_addr_e : in std_logic_vector(4 downto 0)",
                "rs2_addr_e : in std_logic_vector(4 downto 0)",
                "rs1_addr_d : in std_logic_vector(4 downto 0)",
                "rs2_addr_d : in std_logic_vector(4 downto 0)",
                "rd_addr_e : in std_logic_vector(4 downto 0)",
                "rd_addr_m : in std_logic_vector(4 downto 0)",
                "rd_addr_w : in std_logic_vector(4 downto 0)",
                "reg_we_m : in std_logic", "reg_we_w : in std_logic",
                "is_load_e : in std_logic", "taken_e : in std_logic",
                "fwd_a : out std_logic_vector(1 downto 0)",
                "fwd_b : out std_logic_vector(1 downto 0)",
                "stall : out std_logic", "flush_d : out std_logic",
                "flush_f : out std_logic"),
               ("FR-RV-04", "FR-RV-17", "FR-RV-22"),
               "All hazard decisions in one combinational block, as in the "
               "reference pipeline (hazard_control_unit.vhd)."),
         _top("Holds the four pipeline registers as clocked processes.")),
    ),
)}


def validar(tipo: str, isa: str) -> Tipo:
    """O `Tipo` pedido, ou erro com a lista do que e aceito (FR-RV-47)."""
    if tipo not in TIPOS:
        raise ErroContrato(f"tipo {tipo!r} desconhecido; aceitos: {', '.join(TIPOS)}")
    if isa not in ISAS:
        raise ErroContrato(
            f"ISA {isa!r} nao e julgada pelo rvverify; aceitas: {', '.join(ISAS)}. "
            f"Outra extensao exige primeiro estender o validador (spec, modelo "
            f"de referencia, montador e casos)."
        )
    return TIPOS[tipo]


# --------------------------------------------------------------------------
# o que o modelo le
# --------------------------------------------------------------------------

_ENTIDADE_RE = re.compile(r"^[ \t]*entity\s+(\w+)\s+is\b.*?^[ \t]*end\b[^;]*;",
                          re.IGNORECASE | re.MULTILINE | re.DOTALL)


def declaracoes_de_entidade(texto: str) -> list[str]:
    """Os blocos `entity ... end ...;` de um texto VHDL."""
    return [m.group(0).strip() for m in _ENTIDADE_RE.finditer(texto)]


def _sem_comentarios(texto: str) -> str:
    linhas = [ln.rstrip() for ln in texto.splitlines()
              if ln.strip() and not ln.strip().startswith("--")]
    return "\n".join(linhas)


def interfaces_fornecidas(diretorio: Path = FORNECIDOS_DIR) -> str:
    """O pacote de tipos inteiro, as constantes do mapa de memoria e as
    entidades fornecidas -- tudo lido dos arquivos reais."""
    partes = ["-- cpu_package.vhd (types and constants you must use)",
              _sem_comentarios((diretorio / "cpu_package.vhd").read_text(encoding="utf-8"))]
    mem = (diretorio / "memory_package.vhd").read_text(encoding="utf-8")
    constantes = [ln.strip() for ln in mem.splitlines()
                  if re.match(r"\s*constant\s+\w+\s*:\s*integer", ln, re.IGNORECASE)]
    partes += ["-- memory_package.vhd (integer constants of the memory map)",
               "\n".join(constantes)]
    for arquivo in ("instruction_memory.vhd", "data_memory.vhd", "mul_div_unit.vhd"):
        texto = (diretorio / arquivo).read_text(encoding="utf-8")
        for decl in declaracoes_de_entidade(texto):
            partes += [f"-- {arquivo}", decl]
    return "\n\n".join(partes)


_RV32I = ("lui auipc jal jalr beq bne blt bge bltu bgeu lb lh lw lbu lhu sb sh sw "
          "addi slti sltiu xori ori andi slli srli srai "
          "add sub sll slt sltu xor srl sra or and")
_RV32M = "mul mulh mulhsu mulhu div divu rem remu"


def texto_do_contrato(tipo: Tipo, isa: str) -> str:
    """O prompt de sistema: o contrato inteiro, em ingles."""
    sinais = "\n".join(f"- `{n}` : {d}" for n, d in tipo.sinais)
    if isa == "rv32im":
        extensao = (
            f"RV32M ({_RV32M}) when the generic RV32M_ENABLE is true: decode "
            f"opcode 0110011 with funct7 = 0000001 into ALU_OP_TYPE_MUL .. "
            f"ALU_OP_TYPE_REMU and instantiate the PROVIDED mul_div_unit inside "
            f"`if RV32M_ENABLE generate` (it is combinational and already "
            f"implements division by zero and overflow). When RV32M_ENABLE is "
            f"false the M instructions need not execute. The test bench runs "
            f"the same CPU twice: first with RV32M_ENABLE = false, then true."
        )
    else:
        extensao = ("RV32M is NOT required: keep the generic RV32M_ENABLE "
                    "declared, but you may ignore it and leave mul_div_unit "
                    "uninstantiated.")
    return f"""You write VHDL for a RISC-V CPU that an automatic conformance suite
(GHDL + cocotb, the `rvverify` validator) will judge by running real RISC-V
programs and comparing the data RAM with a reference model. Follow this
contract exactly: a CPU that deviates from it cannot be observed and fails.

# Target
ISA: RV32I ({_RV32I}).
{extensao}
Not required: FENCE, ECALL, EBREAK, CSRs, interrupts, misaligned accesses.
Microarchitecture ({tipo.nome}): {tipo.microarquitetura}

# Provided files (compiled BEFORE yours; never rewrite, copy or redeclare them)
{", ".join(FORNECIDOS)}
Use `library ieee; use ieee.std_logic_1164.all; use ieee.numeric_std.all;
use work.cpu_package.all; use work.memory_package.all;` as needed.

# Top level: file src/{TOP}.vhd, exactly this interface
entity {TOP} is
    generic(
        ROM_INIT_FILE  : string  := "";
        ROM_SIZE_WORDS : integer := 0;
        RV32M_ENABLE   : boolean := false
    );
    port(
        rst : in std_logic;   -- asynchronous, ACTIVE HIGH
        clk : in std_logic
    );
end {TOP};

Inside {TOP} the test bench reads these by hierarchical name, so the labels
and signal names are mandatory:
- instance label `instruction_memory`: entity work.instruction_memory, with
  generic map (ROM_INIT_FILE => ROM_INIT_FILE, ROM_SIZE_WORDS => ROM_SIZE_WORDS);
  asynchronous read of the instruction at `addr`.
- instance label `data_memory`: entity work.data_memory. Pass the full byte
  address (it routes DATA_ROM at 0x00FC8000 and DATA_RAM at 0x00FC8100 by
  itself). Reads are asynchronous, writes happen on the rising edge. Byte and
  halfword loads come back ZERO-extended: the core must sign-extend LB and LH.
- instance label `register_file`: your register file entity, whose storage is
  a signal named `registers` of type `array (0 to 31) of
  std_logic_vector(31 downto 0)` (declare the type in that file).
- signals declared in {TOP}:
{sinais}

Reset: while rst = '1' (asynchronous), the PC is RESET_HANDLER_ADDRESS
(0x00000000) and all registers are 0. Programs end in the self-loop
`halt: j halt` (JAL x0, 0); nothing special is needed for it.

# VHDL rules (each one already broke a real design in this project)
1. VHDL-2008 analyzed by `ghdl -a --std=08`. Use only ieee.std_logic_1164 and
   ieee.numeric_std (never std_logic_arith / std_logic_unsigned).
2. Every array the test bench reads is a 1-D array of 32-bit words, never 2-D.
3. Never compute an array index in one signal and its range guard in another
   signal: keep the guard and the indexing in the same conditional expression.
4. Write combinational logic as concurrent assignments; in a combinational
   process assign every output on every path, so no latch is inferred.
5. One entity per file, entity name = file name, English identifiers and
   comments.
6. Start every file with a comment header containing `-- REQ:` and the
   requirement IDs it implements: FR-RV-04 (RV32I semantics), FR-RV-05 (top
   level and memories), FR-RV-06 (observable state), FR-RV-12/FR-RV-13/FR-RV-14
   (M extension), FR-RV-15 (reset), FR-RV-16 (RV32M_ENABLE).
7. When asked for a file, answer with the COMPLETE file in a single ```vhdl
   block: no placeholders, no "...", no other files.

# Provided declarations
{interfaces_fornecidas()}
"""


def arquitetura_padrao(tipo: Tipo, isa: str, nome: str) -> dict:
    """A decomposicao padrao do tipo, no formato de `architecture.json`."""
    return {
        "design": nome,
        "tipo": tipo.nome,
        "isa": isa,
        "top": TOP,
        "origem": "padrao",
        "provided": [f"cpus/rv32i_pipeline/src/{f}" for f in FORNECIDOS],
        "blocks": [b.como_dict() for b in tipo.blocos],
        "notes": "",
    }


# --------------------------------------------------------------------------
# o manifesto
# --------------------------------------------------------------------------

def _relativo(alvo: Path, pasta: Path) -> str:
    """Caminho de `alvo` visto de `pasta`, com barras POSIX (vale no Docker)."""
    try:
        rel = os.path.relpath(alvo.resolve(), pasta.resolve())
    except ValueError:                       # outra unidade no Windows
        return alvo.resolve().as_posix()
    return PurePosixPath(*Path(rel).parts).as_posix()


def _toml(valor: object) -> str:
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, int):
        return str(valor)
    return '"' + str(valor).replace("\\", "\\\\").replace('"', '\\"') + '"'


def renderizar_cpu_toml(nome: str, pasta: Path, tipo: Tipo, isa: str,
                        arquivos: list[str]) -> str:
    """O `cpu.toml` da entrega. Nenhum campo vem do modelo."""
    fontes = [_relativo(FORNECIDOS_DIR / f, pasta) for f in FORNECIDOS] + list(arquivos)
    linhas = [
        "# Manifesto gerado por rvgen (FR-RV-47): deterministico, a partir do",
        f"# contrato do tipo `{tipo.nome}` em rvgen/contrato.py. Nao foi escrito",
        "# pelo modelo de linguagem; so as fontes em src/ foram.",
        "#",
        "# REQ: FR-RV-05, FR-RV-06, FR-RV-09, FR-RV-15, FR-RV-16, FR-RV-21",
        "",
        "[design]",
        f"name = {_toml(nome)}",
        f"top  = {_toml(TOP)}",
        'std  = "08"',
    ]
    if isa == "rv32im":
        linhas.append('rv32m_generic = "RV32M_ENABLE"')
    linhas.append("sources = [")
    linhas += [f"    {_toml(f)}," for f in fontes]
    linhas += [
        "]",
        "",
        "[clock]",
        'signal    = "clk"',
        "period_ns = 10",
        "",
        "[reset]",
        'signal = "rst"',
        'active = "high"',
        "cycles = 3",
        "",
        "[program]",
        'mode         = "rom_init_file"',
        'generic      = "ROM_INIT_FILE"',
        'size_generic = "ROM_SIZE_WORDS"',
        "size_words   = 1024",
        "",
        "[memory]",
        "ram_base  = 0x00FC8100",
        "ram_bytes = 512",
        "",
        "[observe]",
        'ram       = "data_memory.data_ram.memory"',
        'registers = "register_file.registers"',
    ]
    linhas += [f"{k} = {_toml(v)}" for k, v in tipo.observe.items()]
    linhas += ["", "[halt]"]
    linhas += [f"{k} = {_toml(v)}" for k, v in tipo.halt.items()]
    linhas += ["", "[metrics]"]
    linhas += [f"{k} = {_toml(v)}" for k, v in tipo.metrics.items()]
    return "\n".join(linhas) + "\n"
