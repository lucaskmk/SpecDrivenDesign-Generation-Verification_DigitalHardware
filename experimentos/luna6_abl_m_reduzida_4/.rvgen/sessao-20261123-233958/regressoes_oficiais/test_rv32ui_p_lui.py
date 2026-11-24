import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer


def assemble_rv32im(source):
    """Assemble RV32IM source with an installed GNU RISC-V toolchain."""
    toolchains = (
        ("riscv64-unknown-elf-as", "riscv64-unknown-elf-objcopy"),
        ("riscv32-unknown-elf-as", "riscv32-unknown-elf-objcopy"),
        ("riscv64-linux-gnu-as", "riscv64-linux-gnu-objcopy"),
    )
    assembler = next(
        (shutil.which(as_name) for as_name, _ in toolchains if shutil.which(as_name)),
        None,
    )
    objcopy = next(
        (
            shutil.which(copy_name)
            for as_name, copy_name in toolchains
            if shutil.which(as_name) and shutil.which(copy_name)
        ),
        None,
    )
    if assembler is None or objcopy is None:
        raise RuntimeError("A GNU RISC-V assembler and objcopy are required")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        source_path = temp_path / "program.S"
        object_path = temp_path / "program.o"
        binary_path = temp_path / "program.bin"
        source_path.write_text(".section .text\n.option norvc\n" + source)

        subprocess.run(
            [assembler, "-march=rv32im", "-mabi=ilp32", "-o", str(object_path), str(source_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [objcopy, "-O", "binary", "-j", ".text", str(object_path), str(binary_path)],
            check=True,
            capture_output=True,
            text=True,
        )

        program_bytes = binary_path.read_bytes()
        if len(program_bytes) % 4:
            raise RuntimeError("Assembler produced a non-word-aligned program")
        return [
            int.from_bytes(program_bytes[offset : offset + 4], byteorder="little")
            for offset in range(0, len(program_bytes), 4)
        ]


@cocotb.test()
async def lui_to_x0_preserves_zero_for_store(dut):
    program = assemble_rv32im(
        """
        lui x0, 0x80000
        sw x0, 0(x0)
    halt:
        jal x0, halt
        """
    )
    instruction_memory = {4 * index: word for index, word in enumerate(program)}
    byte_memory = {}

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = program[0]
    dut.data_read_data.value = 0x00000000

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await Timer(1, unit="ns")
    observed_pc = int(dut.instr_addr.value)
    assert observed_pc == 0x00000000, (
        f"Expected reset instr_addr=0x00000000, observed 0x{observed_pc:08X}"
    )
    assert int(dut.data_write.value) == 0, "Expected data_write=0 during reset"

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    observed_pc = int(dut.instr_addr.value)
    assert observed_pc == 0x00000000, (
        f"Expected reset instr_addr=0x00000000, observed 0x{observed_pc:08X}"
    )
    dut.rst.value = 0

    observed_stores = []
    for expected_pc in (0x00000000, 0x00000004):
        await FallingEdge(dut.clk)
        observed_pc = int(dut.instr_addr.value)
        assert observed_pc == expected_pc, (
            f"Expected instr_addr=0x{expected_pc:08X}, observed 0x{observed_pc:08X}"
        )

        dut.instr_data.value = instruction_memory[expected_pc]
        dut.data_read_data.value = 0x00000000
        await Timer(1, unit="ns")

        write_enable = int(dut.data_write.value)
        if expected_pc == 0x00000000:
            assert write_enable == 0, "Expected LUI to leave data_write=0"
        else:
            assert write_enable == 1, "Expected SW to assert data_write"
            address = int(dut.data_addr.value)
            width = int(dut.data_width.value)
            write_data = int(dut.data_write_data.value)
            assert address == 0x00000000, (
                f"Expected store address 0x00000000, observed 0x{address:08X}"
            )
            assert width == 0x2, f"Expected store width 0x2, observed 0x{width:X}"
            assert write_data == 0x00000000, (
                f"Expected store data 0x00000000, observed 0x{write_data:08X}"
            )
            observed_stores.append((address, width, write_data))

        captured_write = write_enable
        captured_address = int(dut.data_addr.value)
        captured_width = int(dut.data_width.value)
        captured_data = int(dut.data_write_data.value)

        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")

        if captured_write:
            byte_count = 1 << captured_width
            for lane in range(byte_count):
                byte_memory[captured_address + lane] = (
                    captured_data >> (8 * lane)
                ) & 0xFF

        next_pc = int(dut.instr_addr.value)
        expected_next_pc = expected_pc + 4
        assert next_pc == expected_next_pc, (
            f"Expected instr_addr=0x{expected_next_pc:08X}, observed 0x{next_pc:08X}"
        )

    assert observed_stores == [(0x00000000, 0x2, 0x00000000)], (
        f"Expected one zero-valued word store, observed {observed_stores}"
    )
    observed_bytes = [byte_memory.get(address, 0) for address in range(4)]
    assert observed_bytes == [0, 0, 0, 0], (
        f"Expected stored bytes [0, 0, 0, 0], observed {observed_bytes}"
    )
