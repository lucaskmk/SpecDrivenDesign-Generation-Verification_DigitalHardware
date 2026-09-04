#!/usr/bin/env python3
"""Testbench of the instruction ROM, driven by the real golden program image.

# REQ: FR-06, FR-07, FR-13

This block is where the phase-3b toolchain meets the RTL, so the testbench is
deliberately not written against hand-made vectors. It checks:

  * that the generated `rom_image_pkg.vhd` carries exactly the words of
    `program.rm` (FR-13 / pipeline:FR-21 round-trip: bin -> .rm -> VHDL array);
  * that the same words are what `objdump -d` reports -- an oracle that comes
    from a *different* tool path (objdump on the ELF) than the image
    (objcopy -> bin -> .rm), so a bug in bin_to_rm.py cannot hide by being
    consistent with itself;
  * the fetch port addressing (word index = addr[11:2]);
  * the second read port used by .rodata loads, including `data_valid`;
  * the FR-07 rule for an out-of-range fetch: read as zeros, which the control
    unit then treats as an illegal instruction / nop (FR-14).
"""
import os
import re

import cocotb
from cocotb.triggers import Timer

ROM_SIZE_WORDS = 1024
ROM_BASE = 0x00000000

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM_DIR = os.path.join(HERE, "..", "..", "software", "riscv_base_test")
RM_PATH = os.path.join(PROGRAM_DIR, "program.rm")
DASM_PATH = os.path.join(PROGRAM_DIR, "program.dasm")
SYM_PATH = os.path.join(PROGRAM_DIR, "program.sym")

# "  2c:\t0031a023          \tsw\tx3,0(x3)"
DASM_RE = re.compile(r"^\s*([0-9a-f]+):\s+([0-9a-f]{8})\s")
# objdump -t: "00000274 g       .rodata\t00000000 const_a"
SYM_RE = re.compile(r"^([0-9a-f]{8})\s+\S+\s+.*\s(\S+)\s*$")


def read_rm(path):
    """Words of a .rm image, in order. Comment lines start with '#'."""
    words = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            words.append(int(line, 16))
    return words


def read_dasm(path):
    """{byte_addr: encoded_word} from objdump -d output."""
    words = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            match = DASM_RE.match(line)
            if match:
                words[int(match.group(1), 16)] = int(match.group(2), 16)
    return words


def read_symbols(path):
    """{symbol: byte_addr} from objdump -t output (section symbols dropped)."""
    symbols = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            match = SYM_RE.match(line)
            if match and not match.group(2).startswith("."):
                symbols[match.group(2)] = int(match.group(1), 16)
    return symbols


async def settle():
    """The DUT is purely combinational: just let the deltas propagate."""
    await Timer(1, unit="ns")


async def fetch(dut, byte_addr):
    dut.instr_addr.value = byte_addr
    await settle()
    return int(dut.instr_out.value)


async def data_read(dut, byte_addr):
    dut.data_addr.value = byte_addr
    await settle()
    return int(dut.data_out.value), int(dut.data_valid.value)


def init_inputs(dut):
    dut.instr_addr.value = 0
    dut.data_addr.value = 0


@cocotb.test()
async def test_image_matches_rm(dut):
    """REQ: FR-13 -- every ROM word equals the .rm, padding included."""
    init_inputs(dut)
    await settle()

    image = read_rm(RM_PATH)
    assert image, f"empty or missing .rm at {RM_PATH}"
    assert len(image) <= ROM_SIZE_WORDS, (
        f"program does not fit the ROM: {len(image)} > {ROM_SIZE_WORDS} words"
    )

    for index in range(ROM_SIZE_WORDS):
        expected = image[index] if index < len(image) else 0x00000000
        got = await fetch(dut, ROM_BASE + index * 4)
        assert got == expected, (
            f"ROM word {index} (addr 0x{ROM_BASE + index * 4:08X}): "
            f"expected 0x{expected:08X}, got 0x{got:08X}"
        )

    dut._log.info(
        "%d program words + %d zero-padded words match program.rm",
        len(image),
        ROM_SIZE_WORDS - len(image),
    )


@cocotb.test()
async def test_image_matches_objdump(dut):
    """REQ: FR-13 -- independent oracle: objdump on the ELF."""
    init_inputs(dut)
    await settle()

    words = read_dasm(DASM_PATH)
    assert words, f"no instructions parsed out of {DASM_PATH}"

    for byte_addr, expected in sorted(words.items()):
        got = await fetch(dut, ROM_BASE + byte_addr)
        assert got == expected, (
            f"addr 0x{byte_addr:08X}: objdump says 0x{expected:08X}, "
            f"ROM gives 0x{got:08X}"
        )

    dut._log.info("%d instructions agree with objdump", len(words))


@cocotb.test()
async def test_rodata_port(dut):
    """REQ: FR-06, FR-07 -- the .rodata constants read through the data port."""
    init_inputs(dut)
    await settle()

    image = read_rm(RM_PATH)
    symbols = read_symbols(SYM_PATH)

    # const_a / const_b are .rodata words, so they have no instruction line in
    # the disassembly; they only show up in the ELF symbol table. Their
    # expected values are the ones written in program.S.
    expected_rodata = {"const_a": 0xA5A5A5A5, "const_b": 0x5A5A0001}
    for name, expected in expected_rodata.items():
        assert name in symbols, f"{name} not found in {SYM_PATH}"
        byte_addr = symbols[name]
        assert byte_addr % 4 == 0, f"{name} is not word aligned"
        assert image[byte_addr // 4] == expected, (
            f"{name} in the image is 0x{image[byte_addr // 4]:08X}, "
            f"program.S declares 0x{expected:08X}"
        )

        got, valid = await data_read(dut, ROM_BASE + byte_addr)
        assert valid == 1, f"data_valid low for {name} at 0x{byte_addr:08X}"
        assert got == expected, (
            f"{name} at 0x{byte_addr:08X}: expected 0x{expected:08X}, "
            f"got 0x{got:08X}"
        )

    dut._log.info("const_a/const_b readable through the .rodata port")


@cocotb.test()
async def test_out_of_range(dut):
    """REQ: FR-07, FR-14 -- outside the ROM: fetch reads 0, data_valid is 0."""
    init_inputs(dut)
    await settle()

    # 0x00FC8000 is the data RAM, 0x10000000 is unmapped, 0x00001000 is just
    # past the 4 KB ROM window.
    for addr in (0x00FC8000, 0x00FC8FFC, 0x10000000, 0x00001000, 0xFFFFFFFC):
        got = await fetch(dut, addr)
        assert got == 0x00000000, (
            f"fetch at 0x{addr:08X} is outside the ROM but returned 0x{got:08X}"
        )
        _, valid = await data_read(dut, addr)
        assert valid == 0, f"data_valid high for out-of-range 0x{addr:08X}"

    # Inside the window, data_valid must be high.
    _, valid = await data_read(dut, ROM_BASE + 0x10)
    assert valid == 1, "data_valid low for an address inside the ROM"


@cocotb.test()
async def test_ports_are_independent(dut):
    """REQ: FR-06 -- the two read ports do not interfere with each other."""
    init_inputs(dut)
    await settle()

    image = read_rm(RM_PATH)
    symbols = read_symbols(SYM_PATH)
    rodata_addr = symbols["const_a"]

    # fetch walks the program while the data port stays parked on a constant
    for index in range(0, min(len(image), 64)):
        dut.instr_addr.value = ROM_BASE + index * 4
        dut.data_addr.value = ROM_BASE + rodata_addr
        await settle()
        assert int(dut.instr_out.value) == image[index], (
            f"fetch of word {index} disturbed by the data port"
        )
        assert int(dut.data_out.value) == 0xA5A5A5A5, (
            f"data port disturbed by the fetch of word {index}"
        )
        assert int(dut.data_valid.value) == 1
