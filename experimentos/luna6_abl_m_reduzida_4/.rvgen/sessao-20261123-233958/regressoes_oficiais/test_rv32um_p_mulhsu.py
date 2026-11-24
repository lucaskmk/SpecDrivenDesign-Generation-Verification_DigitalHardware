import shutil
import subprocess
import tempfile
from pathlib import Path

import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble RV32IM source into raw .text bytes using GNU RISC-V binutils."""
    toolchains = (
        ("riscv64-unknown-elf-as", "riscv64-unknown-elf-objcopy"),
        ("riscv32-unknown-elf-as", "riscv32-unknown-elf-objcopy"),
        ("riscv64-linux-gnu-as", "riscv64-linux-gnu-objcopy"),
    )

    for assembler_name, objcopy_name in toolchains:
        assembler = shutil.which(assembler_name)
        objcopy = shutil.which(objcopy_name)
        if assembler and objcopy:
            break
    else:
        raise RuntimeError("GNU RISC-V assembler and objcopy were not found")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        source_path = temp_path / "program.S"
        object_path = temp_path / "program.o"
        binary_path = temp_path / "program.bin"
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
        return binary_path.read_bytes()


@cocotb.test()
async def mulhsu_official_case_stores_expected_result(dut):
    program_source = """
        .text
        .option norvc
        .globl _start
    _start:
        lui   x1, 0xaaaaa
        addi  x1, x1, -1365
        lui   x2, 0x30
        addi  x2, x2, -387
        mulhsu x3, x1, x2
        sw    x3, 0(x0)
    halt:
        jal   x0, halt
    """

    program_bytes = assemble_rv32im(program_source)
    assert len(program_bytes) % 4 == 0, (
        f"Expected program length divisible by 4, observed {len(program_bytes)}"
    )
    program = {
        address: int.from_bytes(program_bytes[address : address + 4], "little")
        for address in range(0, len(program_bytes), 4)
    }

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000
    await Timer(1, unit="ns")

    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected instr_addr=0x00000000 during reset, "
        f"observed 0x{int(dut.instr_addr.value):08X}"
    )
    assert int(dut.data_write.value) == 0, (
        f"Expected data_write=0 during reset, observed {int(dut.data_write.value)}"
    )

    dut.rst.value = 0
    await Timer(1, unit="ns")

    store_observed = False
    for _ in range(len(program) + 2):
        pc = int(dut.instr_addr.value)
        assert pc in program, f"Expected a program instruction at 0x{pc:08X}"
        dut.instr_data.value = program[pc]
        dut.data_read_data.value = 0x00000000
        await Timer(1, unit="ns")

        if int(dut.data_write.value) == 1:
            address = int(dut.data_addr.value)
            width = int(dut.data_width.value)
            write_data = int(dut.data_write_data.value)

            assert address == 0x00000000, (
                f"Expected store address 0x00000000, observed 0x{address:08X}"
            )
            assert width == 0x2, (
                f"Expected store width 0x2, observed 0x{width:X}"
            )
            assert write_data == 0xFFFF0081, (
                f"Expected MULHSU result 0xFFFF0081, observed 0x{write_data:08X}"
            )
            store_observed = True

        dut.clk.value = 1
        await Timer(1, unit="ns")
        dut.clk.value = 0
        await Timer(1, unit="ns")

        if store_observed:
            break

    assert store_observed, "Expected the program to store the MULHSU result"
