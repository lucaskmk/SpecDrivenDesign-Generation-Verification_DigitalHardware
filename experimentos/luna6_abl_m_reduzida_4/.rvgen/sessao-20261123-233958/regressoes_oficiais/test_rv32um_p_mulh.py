import shutil
import subprocess
import tempfile
from pathlib import Path

import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble RV32IM source with GNU RISC-V binutils and return its words."""
    assembler = next(
        (
            path
            for name in (
                "riscv64-unknown-elf-as",
                "riscv32-unknown-elf-as",
            )
            if (path := shutil.which(name)) is not None
        ),
        None,
    )
    objcopy = next(
        (
            path
            for name in (
                "riscv64-unknown-elf-objcopy",
                "riscv32-unknown-elf-objcopy",
            )
            if (path := shutil.which(name)) is not None
        ),
        None,
    )
    if assembler is None or objcopy is None:
        raise RuntimeError("RV32IM GNU assembler and objcopy are required")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        asm_path = temp / "program.S"
        obj_path = temp / "program.o"
        bin_path = temp / "program.bin"
        asm_path.write_text(source)

        subprocess.run(
            [
                assembler,
                "-march=rv32im",
                "-mabi=ilp32",
                "-o",
                str(obj_path),
                str(asm_path),
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
                str(obj_path),
                str(bin_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        image = bin_path.read_bytes()

    if len(image) % 4:
        raise RuntimeError("Assembler output is not a whole number of instructions")
    return [
        int.from_bytes(image[offset : offset + 4], "little")
        for offset in range(0, len(image), 4)
    ]


@cocotb.test()
async def mulh_signed_high_product_matches_official_failure_case(dut):
    source = """
        .option norvc
        .text
        .globl _start
_start:
        li   t0, 0xaaaaaaab
        li   t1, 0x0002fe7d
        mulh t2, t0, t1
        sw   t2, 0(zero)
halt:
        j    halt
"""
    program = assemble_rv32im(source)

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000
    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected reset instr_addr=0x00000000, "
        f"observed 0x{int(dut.instr_addr.value):08X}"
    )

    dut.rst.value = 0
    await Timer(1, unit="ns")

    memory = {}
    observed_store = False

    for _ in range(20):
        pc = int(dut.instr_addr.value)
        index = pc // 4
        assert index < len(program), (
            f"Expected fetch within assembled program at 0x{pc:08X}, "
            f"observed out-of-range PC 0x{pc:08X}"
        )

        dut.instr_data.value = program[index]
        await Timer(1, unit="ns")

        if int(dut.data_write.value) == 1:
            address = int(dut.data_addr.value)
            width = int(dut.data_width.value)
            write_data = int(dut.data_write_data.value)

            assert address == 0x00000000, (
                f"Expected store address 0x00000000, observed 0x{address:08X}"
            )
            assert width == 0x2, (
                f"Expected word-store width 0x2, observed 0x{width:X}"
            )
            assert write_data == 0xFFFF0081, (
                f"Expected MULH result/store data 0xFFFF0081, "
                f"observed 0x{write_data:08X}"
            )

            dut.clk.value = 1
            await Timer(1, unit="ns")
            memory[address] = write_data
            dut.clk.value = 0
            await Timer(1, unit="ns")

            observed_store = True
            break

        dut.clk.value = 1
        await Timer(1, unit="ns")
        dut.clk.value = 0
        await Timer(1, unit="ns")

    assert observed_store, "Expected the final word store of the MULH result"
    assert memory.get(0x00000000) == 0xFFFF0081, (
        f"Expected committed memory word 0xFFFF0081, "
        f"observed 0x{memory.get(0x00000000, 0):08X}"
    )
