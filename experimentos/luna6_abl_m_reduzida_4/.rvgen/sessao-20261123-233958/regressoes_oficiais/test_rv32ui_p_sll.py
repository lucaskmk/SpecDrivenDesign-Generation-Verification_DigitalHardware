import shutil
import subprocess
import tempfile
from pathlib import Path

import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble RV32IM source with GNU binutils and return its .text words."""
    assembler = next(
        (
            path
            for name in (
                "riscv64-unknown-elf-as",
                "riscv32-unknown-elf-as",
                "riscv64-linux-gnu-as",
                "riscv32-linux-gnu-as",
            )
            if (path := shutil.which(name)) is not None
        ),
        None,
    )
    if assembler is None:
        raise RuntimeError("A GNU RISC-V assembler is required to assemble the test program")

    objcopy_name = assembler.rsplit("/", 1)[-1].replace("-as", "-objcopy")
    objcopy = shutil.which(objcopy_name)
    if objcopy is None:
        raise RuntimeError(f"Could not find the matching objcopy tool: {objcopy_name}")

    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)
        source_path = directory / "program.S"
        object_path = directory / "program.o"
        binary_path = directory / "program.bin"
        source_path.write_text(
            ".option norvc\n"
            ".text\n"
            ".globl _start\n"
            "_start:\n"
            + source
        )

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

        binary = binary_path.read_bytes()

    if len(binary) % 4:
        raise RuntimeError("Assembler produced a .text section that is not word-aligned")
    return [
        int.from_bytes(binary[offset : offset + 4], byteorder="little")
        for offset in range(0, len(binary), 4)
    ]


@cocotb.test()
async def sll_zero_shift_preserves_all_bits_in_store(dut):
    program = assemble_rv32im(
        """
        addi x1, x0, -1
        sll  x3, x1, x0
        sw   x3, 0(x0)
    halt:
        jal  x0, halt
        """
    )
    rom = {4 * index: instruction for index, instruction in enumerate(program)}
    data_memory = bytearray(16)

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = program[0]
    dut.data_read_data.value = 0x00000000
    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected reset instr_addr=0x00000000, observed 0x{int(dut.instr_addr.value):08X}"
    )

    dut.clk.value = 1
    await Timer(1, unit="ns")
    dut.clk.value = 0
    await Timer(1, unit="ns")
    dut.rst.value = 0
    await Timer(1, unit="ns")

    async def present_current_instruction():
        pc = int(dut.instr_addr.value)
        assert pc in rom, f"Expected a program instruction at 0x{pc:08X}"
        dut.instr_data.value = rom[pc]

        address = int(dut.data_addr.value)
        base = address & 0xFFFFFFFC
        word = int.from_bytes(data_memory[base : base + 4], byteorder="little")
        dut.data_read_data.value = word
        await Timer(1, unit="ns")

    async def tick():
        dut.clk.value = 1
        await Timer(1, unit="ns")
        dut.clk.value = 0
        await Timer(1, unit="ns")

    # Execute the setup ADDI and the focal SLL instruction.
    await present_current_instruction()
    await tick()
    await present_current_instruction()
    await tick()

    # Check the public store transaction produced by SLL with shift amount zero.
    await present_current_instruction()
    observed_write = int(dut.data_write.value)
    observed_address = int(dut.data_addr.value)
    observed_width = int(dut.data_width.value)
    observed_data = int(dut.data_write_data.value)

    assert observed_write == 1, f"Expected data_write=1, observed {observed_write}"
    assert observed_address == 0x00000000, (
        f"Expected store address 0x00000000, observed 0x{observed_address:08X}"
    )
    assert observed_width == 0x2, f"Expected data_width=0x2, observed 0x{observed_width:X}"
    assert observed_data == 0xFFFFFFFF, (
        f"Expected store data 0xFFFFFFFF, observed 0x{observed_data:08X}"
    )

    # Commit the externally visible word store at its rising edge.
    dut.clk.value = 1
    await Timer(1, unit="ns")
    data_memory[observed_address : observed_address + 4] = observed_data.to_bytes(
        4, byteorder="little"
    )
    dut.clk.value = 0
    await Timer(1, unit="ns")

    observed_memory = int.from_bytes(data_memory[0:4], byteorder="little")
    assert observed_memory == 0xFFFFFFFF, (
        f"Expected committed memory value 0xFFFFFFFF, observed 0x{observed_memory:08X}"
    )
