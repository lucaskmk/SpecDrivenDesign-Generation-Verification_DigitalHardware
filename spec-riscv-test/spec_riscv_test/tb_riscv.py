"""Cocotb virtual ROM/RAM plus the riscv-tests `tohost` completion protocol."""
from __future__ import annotations

import json
import os
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, ReadWrite, RisingEdge, Timer

from .elf import load

MASK32 = 0xFFFFFFFF


def _decode(instruction: int) -> str:
    """A compact decoder: enough context for an LLM, not a second ISA model."""
    opcode, rd = instruction & 0x7f, (instruction >> 7) & 31
    funct3, rs1, rs2 = (instruction >> 12) & 7, (instruction >> 15) & 31, (instruction >> 20) & 31
    if instruction == 0x00000013:
        return "nop"
    if opcode == 0x33:
        names = {(0, 0): "add", (0, 0x20): "sub", (7, 0): "and", (6, 0): "or", (4, 0): "xor", (1, 0): "sll", (5, 0): "srl", (5, 0x20): "sra", (2, 0): "slt", (3, 0): "sltu"}
        return f"{names.get((funct3, (instruction >> 25) & 0x7f), 'op')} x{rd}, x{rs1}, x{rs2}"
    if opcode == 0x13:
        imm = instruction >> 20
        imm -= 0x1000 if imm & 0x800 else 0
        return f"op-imm(funct3={funct3}) x{rd}, x{rs1}, {imm}"
    if opcode == 0x63:
        return f"branch(funct3={funct3}) x{rs1}, x{rs2}"
    if opcode == 0x03:
        return f"load(funct3={funct3}) x{rd}, {rs1}+imm"
    if opcode == 0x23:
        return f"store(funct3={funct3}) x{rs2}, {rs1}+imm"
    if opcode == 0x6f:
        return f"jal x{rd}, imm"
    if opcode == 0x67:
        return f"jalr x{rd}, x{rs1}, imm"
    return f"unknown 0x{instruction:08x}"


def _word(memory: dict[int, int], address: int) -> int:
    return sum(memory.get(address + index, 0) << (8 * index) for index in range(4))


def _store(memory: dict[int, int], address: int, width: int, value: int) -> None:
    count = (1, 2, 4)[width] if width in (0, 1, 2) else 0
    if not count:
        raise AssertionError(f"largura de escrita inválida da CPU: {width}")
    for index in range(count):
        memory[address + index] = (value >> (8 * index)) & 0xFF


def _write_report(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


@cocotb.test()
async def run_riscv_test(dut):
    config = json.loads(Path(os.environ["SPEC_RISCV_TEST_CONFIG"]).read_text(encoding="utf-8"))
    report = Path(config["report"])
    program = load(config["elf"])
    tohost = program.symbols.get("tohost")
    if tohost is None:
        raise AssertionError("ELF não define o símbolo `tohost`; não é um riscv-tests p compatível")
    memory = dict(program.memory)
    clock = Clock(dut.clk, 10, unit="ns")
    cocotb.start_soon(clock.start())
    dut.rst.value = 1
    dut.instr_data.value = 0
    dut.data_read_data.value = 0
    await Timer(1, unit="ns")
    for _ in range(3):
        await RisingEdge(dut.clk)
    dut.rst.value = 0
    last_pc = 0
    trace: list[dict] = []
    full_trace: list[dict] = []
    trace_path = Path(config["trace"]) if config.get("trace") else None
    try:
        for cycle in range(1, int(config["max_cycles"]) + 1):
            await FallingEdge(dut.clk)
            pc = int(dut.instr_addr.value) & MASK32
            instruction = _word(memory, pc)
            dut.instr_data.value = instruction

            # The CPU instruction port is asynchronous. Let its decoder and
            # address-generation logic settle before sampling the matching
            # data request; otherwise the response belongs to the preceding
            # instruction and an official failure is not DUT evidence.
            await ReadWrite()
            address = int(dut.data_addr.value) & MASK32
            read_word = _word(memory, address & ~3)
            dut.data_read_data.value = read_word

            # The memory response is also asynchronous and must be stable at
            # the instruction's committing edge.
            await ReadWrite()
            write = int(dut.data_write.value)
            width = int(dut.data_width.value)
            write_address = int(dut.data_addr.value) & MASK32
            write_value = int(dut.data_write_data.value) & MASK32
            event = {"cycle": cycle, "pc": f"0x{pc:08x}", "instruction": f"0x{instruction:08x}",
                     "decoded": _decode(instruction), "data_addr": f"0x{address:08x}",
                     "data_read_address": f"0x{address & ~3:08x}",
                     "data_read_data": f"0x{read_word:08x}", "data_write": write,
                     "data_width": width}
            if write:
                event.update({"write_address": f"0x{write_address:08x}", "write_width": width,
                               "write_value": f"0x{write_value:08x}"})

            await RisingEdge(dut.clk)
            last_pc = pc
            if write:
                _store(memory, write_address, width, write_value)
            trace.append(event)
            trace = trace[-16:]
            if trace_path:
                full_trace.append(event)
            if write:
                if write_address == tohost:
                    result = {"status": "passed" if write_value == 1 else "failed", "test": config["test"],
                               "cycle": cycle, "pc": f"0x{pc:08x}", "tohost": f"0x{write_value:08x}",
                               "tohost_raw": write_value,
                               "test_case": write_value >> 1 if write_value & 1 else None,
                               "last_instruction": {"word": f"0x{instruction:08x}", "decoded": _decode(instruction)},
                               "trace": trace[-16:],
                               "message": "riscv-tests reportou PASS" if write_value == 1 else
                              "riscv-tests reportou FAIL; o valor de tohost codifica o caso interno"}
                    if trace_path:
                        _write_report(trace_path, {"test": config["test"], "events": full_trace})
                        result["trace_file"] = str(trace_path)
                    _write_report(report, result)
                    assert write_value == 1, result["message"]
                    return
        raise AssertionError(f"timeout: {config['max_cycles']} ciclos sem escrita em tohost")
    except BaseException as error:
        # A failing tohost report is already complete. Do not overwrite its
        # architectural failure details with the AssertionError raised to
        # make Cocotb mark the test as failed.
        if report.exists():
            raise
        result = {"status": "failed", "test": config["test"], "cycle": cycle,
                  "pc": f"0x{last_pc:08x}", "message": str(error), "trace": trace[-16:]}
        if trace_path:
            _write_report(trace_path, {"test": config["test"], "events": full_trace})
            result["trace_file"] = str(trace_path)
        _write_report(report, result)
        raise
