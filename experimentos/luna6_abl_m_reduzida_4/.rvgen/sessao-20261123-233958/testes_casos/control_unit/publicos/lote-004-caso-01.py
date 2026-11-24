import shutil
import subprocess
import tempfile
from pathlib import Path

import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble RV32IM source and return its first instruction word."""
    assembler = next(
        (
            shutil.which(name)
            for name in (
                "riscv64-unknown-elf-as",
                "riscv32-unknown-elf-as",
                "riscv64-linux-gnu-as",
            )
            if shutil.which(name)
        ),
        None,
    )
    objcopy = next(
        (
            shutil.which(name)
            for name in (
                "riscv64-unknown-elf-objcopy",
                "riscv32-unknown-elf-objcopy",
                "riscv64-linux-gnu-objcopy",
            )
            if shutil.which(name)
        ),
        None,
    )
    if assembler is None or objcopy is None:
        raise RuntimeError("An RV32-capable GNU assembler and objcopy are required")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        source_path = temp_path / "program.s"
        object_path = temp_path / "program.o"
        binary_path = temp_path / "program.bin"
        source_path.write_text(f".text\n{source}\n")

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
        code = binary_path.read_bytes()

    if len(code) < 4:
        raise RuntimeError("Assembler produced no complete instruction")
    return int.from_bytes(code[:4], byteorder="little")


@cocotb.test()
async def lui_selects_immediate_for_alu_operand_b(dut):
    dut.instr.value = assemble_rv32im("lui x19, 0x12345")
    await Timer(1, unit="ns")

    observed = int(dut.alu_src_b_imm.value)
    assert observed == 1, f"Expected alu_src_b_imm=1, observed {observed}"
