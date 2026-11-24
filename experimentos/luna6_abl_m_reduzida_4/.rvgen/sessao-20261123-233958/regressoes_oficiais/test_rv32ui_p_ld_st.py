import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer

import shutil
import struct
import subprocess
import tempfile
from pathlib import Path


def assemble_rv32im(source):
    """Assemble RV32IM source and return its .text section as 32-bit words."""
    assembler = (
        shutil.which("riscv64-unknown-elf-as")
        or shutil.which("riscv32-unknown-elf-as")
        or shutil.which("riscv64-linux-gnu-as")
    )
    objcopy = (
        shutil.which("riscv64-unknown-elf-objcopy")
        or shutil.which("riscv32-unknown-elf-objcopy")
        or shutil.which("riscv64-linux-gnu-objcopy")
    )
    if assembler is None or objcopy is None:
        raise RuntimeError("RV32 assembler and objcopy are required to assemble the test program")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        source_path = temp / "program.S"
        object_path = temp / "program.o"
        binary_path = temp / "program.bin"
        source_path.write_text(source)

        subprocess.run(
            [
                assembler,
                "-march=rv32im",
                "-mabi=ilp32",
                "-o",
                str(object_path),
                str(source_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [
                objcopy,
                "-O",
                "binary",
                "-j",
                ".text",
                str(object_path),
                str(binary_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        text = binary_path.read_bytes()

    if len(text) % 4:
        raise ValueError("Assembled .text is not a whole number of 32-bit instructions")
    return list(struct.unpack("<" + "I" * (len(text) // 4), text))


@cocotb.test()
async def signed_byte_load_followed_by_byte_store(dut):
    source = """
        .text
        .globl _start
        .option norvc
    _start:
        lb  x3, 0(x0)
        sb  x3, 1(x0)
    halt:
        j   halt
    """
    program = assemble_rv32im(source)
    assert len(program) == 3, f"Expected 3 assembled instructions, observed {len(program)}"

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000

    memory = {0: 0xDD, 1: 0x00, 2: 0x00, 3: 0x00}

    def read_word(address):
        base = address & 0xFFFFFFFC
        return sum((memory.get(base + lane, 0) & 0xFF) << (8 * lane) for lane in range(4))

    Clock(dut.clk, 10, unit="ns").start()
    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected reset instr_addr=0x00000000, observed 0x{int(dut.instr_addr.value):08X}"
    )

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    await FallingEdge(dut.clk)
    dut.rst.value = 0
    await Timer(1, unit="ns")

    expected_pcs = [0x00000000, 0x00000004, 0x00000008]
    for index, expected_pc in enumerate(expected_pcs):
        observed_pc = int(dut.instr_addr.value)
        assert observed_pc == expected_pc, (
            f"Expected instr_addr=0x{expected_pc:08X}, observed 0x{observed_pc:08X}"
        )

        dut.instr_data.value = program[index]
        await Timer(1, unit="ns")
        address = int(dut.data_addr.value)
        dut.data_read_data.value = read_word(address)
        await Timer(1, unit="ns")

        is_store = index == 1
        observed_write = int(dut.data_write.value)
        assert observed_write == int(is_store), (
            f"Expected data_write={int(is_store)}, observed {observed_write} at PC=0x{expected_pc:08X}"
        )

        if is_store:
            observed_address = int(dut.data_addr.value)
            assert observed_address == 0x00000001, (
                f"Expected store address 0x00000001, observed 0x{observed_address:08X}"
            )
            observed_width = int(dut.data_width.value)
            assert observed_width == 0x0, (
                f"Expected byte-store width 0x0, observed 0x{observed_width:X}"
            )
            observed_data = int(dut.data_write_data.value)
            assert observed_data == 0xFFFFFFDD, (
                f"Expected unshifted store data 0xFFFFFFDD, observed 0x{observed_data:08X}"
            )

        committed_address = int(dut.data_addr.value)
        committed_width = int(dut.data_width.value)
        committed_data = int(dut.data_write_data.value)
        await RisingEdge(dut.clk)

        if is_store:
            count = 1 if committed_width == 0x0 else 2 if committed_width == 0x1 else 4
            for lane in range(count):
                memory[committed_address + lane] = (committed_data >> (8 * lane)) & 0xFF

        await Timer(1, unit="ns")
        expected_next_pc = 0x00000008 if index == 2 else expected_pc + 4
        observed_next_pc = int(dut.instr_addr.value)
        assert observed_next_pc == expected_next_pc, (
            f"Expected next instr_addr=0x{expected_next_pc:08X}, "
            f"observed 0x{observed_next_pc:08X}"
        )
        await FallingEdge(dut.clk)

    assert memory[1] == 0xDD, (
        f"Expected byte at address 0x00000001 to be 0xDD, observed 0x{memory[1]:02X}"
    )
