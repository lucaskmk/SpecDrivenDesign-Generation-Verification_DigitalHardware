import shutil
import subprocess
import tempfile
from pathlib import Path

import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble RV32IM source with a GNU RISC-V assembler."""
    tool_pairs = (
        ("riscv64-unknown-elf-as", "riscv64-unknown-elf-objcopy"),
        ("riscv32-unknown-elf-as", "riscv32-unknown-elf-objcopy"),
        ("riscv64-linux-gnu-as", "riscv64-linux-gnu-objcopy"),
        ("riscv32-linux-gnu-as", "riscv32-linux-gnu-objcopy"),
    )
    tools = next(
        (
            (shutil.which(assembler), shutil.which(objcopy))
            for assembler, objcopy in tool_pairs
            if shutil.which(assembler) and shutil.which(objcopy)
        ),
        None,
    )
    if tools is None:
        raise RuntimeError("A GNU RV32IM assembler and matching objcopy are required")

    assembler, objcopy = tools
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        source_path = temp / "program.s"
        object_path = temp / "program.o"
        binary_path = temp / "program.bin"
        source_path.write_text(source)

        subprocess.run(
            [assembler, "-march=rv32im", "-mabi=ilp32", "-o", str(object_path), str(source_path)],
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
        raise AssertionError(f"Expected 4-byte instruction alignment, got {len(binary)} bytes")
    return [
        int.from_bytes(binary[offset : offset + 4], byteorder="little")
        for offset in range(0, len(binary), 4)
    ]


@cocotb.test()
async def add_zero_and_0x7fff_is_stored_correctly(dut):
    source = """
        .option norvc
        .text
        .globl _start
    _start:
        addi x2, x0, 2047
        slli x2, x2, 4
        addi x2, x2, 15
        add  x3, x0, x2
        sw   x3, 0(x0)
    halt:
        j halt
    """
    words = assemble_rv32im(source)
    program = {4 * index: word for index, word in enumerate(words)}
    halt_address = 4 * (len(words) - 1)

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = words[0]
    dut.data_read_data.value = 0x00000000
    await Timer(1, unit="ns")

    observed_pc = int(dut.instr_addr.value)
    assert observed_pc == 0x00000000, (
        f"Expected reset instr_addr=0x00000000, observed 0x{observed_pc:08X}"
    )

    dut.rst.value = 0
    await Timer(1, unit="ns")

    memory = {}
    store_seen = False

    for _ in range(len(words) + 2):
        pc = int(dut.instr_addr.value)
        assert pc in program, f"Expected a program instruction at 0x{pc:08X}"
        dut.instr_data.value = program[pc]
        await Timer(1, unit="ns")

        if pc == halt_address:
            assert store_seen, "Expected the focal store before reaching halt"
            dut.clk.value = 1
            await Timer(1, unit="ns")
            dut.clk.value = 0
            await Timer(1, unit="ns")
            held_pc = int(dut.instr_addr.value)
            assert held_pc == halt_address, (
                f"Expected halt PC 0x{halt_address:08X}, observed 0x{held_pc:08X}"
            )
            break

        if int(dut.data_write.value):
            address = int(dut.data_addr.value)
            width = int(dut.data_width.value)
            write_data = int(dut.data_write_data.value)

            assert not store_seen, "Expected only the focal store transaction"
            assert address == 0x00000000, (
                f"Expected store address 0x00000000, observed 0x{address:08X}"
            )
            assert width == 0x2, f"Expected word width 0x2, observed 0x{width:X}"
            assert write_data == 0x00007FFF, (
                f"Expected store data 0x00007FFF, observed 0x{write_data:08X}"
            )

            dut.clk.value = 1
            memory[address] = write_data
            store_seen = True
            await Timer(1, unit="ns")
            dut.clk.value = 0
            await Timer(1, unit="ns")
        else:
            dut.clk.value = 1
            await Timer(1, unit="ns")
            dut.clk.value = 0
            await Timer(1, unit="ns")
    else:
        raise AssertionError("Expected the program to reach its halt loop")

    observed_memory = memory.get(0x00000000, 0x00000000)
    assert observed_memory == 0x00007FFF, (
        f"Expected word at 0x00000000 to be 0x00007FFF, "
        f"observed 0x{observed_memory:08X}"
    )
