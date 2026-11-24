import shutil
import subprocess
import tempfile
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer


def assemble_rv32im(source):
    """Assemble RV32IM source with an available GNU RISC-V toolchain."""
    prefixes = (
        "riscv64-unknown-elf",
        "riscv32-unknown-elf",
        "riscv64-linux-gnu",
        "riscv32-linux-gnu",
    )
    tools = None
    for prefix in prefixes:
        candidate = tuple(shutil.which(f"{prefix}-{name}") for name in ("as", "ld", "objcopy"))
        if all(candidate):
            tools = candidate
            break
    if tools is None:
        raise RuntimeError("A GNU RISC-V assembler, linker, and objcopy are required")

    assembler, linker, objcopy = tools
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        source_path = temp / "program.s"
        object_path = temp / "program.o"
        elf_path = temp / "program.elf"
        binary_path = temp / "program.bin"

        source_path.write_text(source, encoding="utf-8")
        subprocess.run(
            [assembler, "-march=rv32im", "-mabi=ilp32", "-o", str(object_path), str(source_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [
                linker,
                "-m",
                "elf32lriscv",
                "-Ttext=0",
                "-e",
                "_start",
                "-o",
                str(elf_path),
                str(object_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [objcopy, "-O", "binary", "-j", ".text", str(elf_path), str(binary_path)],
            check=True,
            capture_output=True,
            text=True,
        )

        binary = binary_path.read_bytes()
        assert len(binary) % 4 == 0, "Expected a word-aligned RV32IM program"
        return [
            int.from_bytes(binary[offset : offset + 4], "little")
            for offset in range(0, len(binary), 4)
        ]


@cocotb.test()
async def sltu_zero_destination_remains_zero(dut):
    program = assemble_rv32im(
        """
        .option norvc
        .text
        .globl _start
        _start:
            addi x1, x0, 16
            addi x2, x0, 30
            sltu x0, x1, x2
            sw x0, 0(x0)
        halt:
            j halt
        """
    )
    assert len(program) == 5, f"Expected 5 instructions, observed {len(program)}"
    instructions = {4 * index: word for index, word in enumerate(program)}

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0
    dut.data_read_data.value = 0
    await Timer(1, unit="ns")
    observed_pc = int(dut.instr_addr.value)
    assert observed_pc == 0, f"Expected reset PC=0x00000000, observed 0x{observed_pc:08X}"

    dut.rst.value = 0
    clock = Clock(dut.clk, 10, unit="ns")
    cocotb.start_soon(clock.start())

    store_count = 0
    halt_pc = 0x00000010

    for _ in range(8):
        await FallingEdge(dut.clk)
        pc = int(dut.instr_addr.value)
        assert pc in instructions, f"Unexpected instruction address 0x{pc:08X}"
        dut.instr_data.value = instructions[pc]
        dut.data_read_data.value = 0
        await Timer(1, unit="ns")

        is_store = int(dut.data_write.value)
        if pc == 0x0000000C:
            assert is_store == 1, f"Expected store at 0x0000000C, observed data_write={is_store}"
            observed_addr = int(dut.data_addr.value)
            observed_width = int(dut.data_width.value)
            observed_data = int(dut.data_write_data.value)
            assert observed_addr == 0x00000000, (
                f"Expected store address 0x00000000, observed 0x{observed_addr:08X}"
            )
            assert observed_width == 0x2, (
                f"Expected word width 0x2, observed 0x{observed_width:X}"
            )
            assert observed_data == 0x00000000, (
                f"Expected x0 store data 0x00000000 after SLTU, observed 0x{observed_data:08X}"
            )
        else:
            assert is_store == 0, f"Unexpected store at PC 0x{pc:08X}"

        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")

        if pc == 0x0000000C:
            store_count += 1
        if pc == halt_pc:
            next_pc = int(dut.instr_addr.value)
            assert next_pc == halt_pc, (
                f"Expected halt loop PC=0x{halt_pc:08X}, observed 0x{next_pc:08X}"
            )
            break

    assert store_count == 1, f"Expected one focal store, observed {store_count}"
