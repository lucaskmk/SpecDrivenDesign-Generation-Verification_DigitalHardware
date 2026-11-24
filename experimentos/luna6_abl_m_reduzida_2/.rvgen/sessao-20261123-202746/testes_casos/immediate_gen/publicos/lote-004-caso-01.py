import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source: str) -> int:
    """Assemble one RV32IM instruction and return its 32-bit encoding."""
    prefix = os.environ.get("RISCV_PREFIX", "riscv64-unknown-elf-")
    assembler = shutil.which(f"{prefix}as")
    objcopy = shutil.which(f"{prefix}objcopy")
    if assembler is None or objcopy is None:
        raise RuntimeError(
            f"RV32IM assembler tools not found for prefix {prefix!r}"
        )

    with tempfile.TemporaryDirectory() as directory:
        assembly_path = Path(directory) / "instruction.s"
        object_path = Path(directory) / "instruction.o"
        binary_path = Path(directory) / "instruction.bin"
        assembly_path.write_text(
            ".text\n"
            ".option norvc\n"
            f"{source}\n",
            encoding="utf-8",
        )

        subprocess.run(
            [
                assembler,
                "-march=rv32im",
                "-mabi=ilp32",
                "-o",
                str(object_path),
                str(assembly_path),
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
                "--only-section=.text",
                str(object_path),
                str(binary_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        instruction_bytes = binary_path.read_bytes()
        if len(instruction_bytes) != 4:
            raise ValueError(
                f"Expected one 32-bit instruction, got {len(instruction_bytes)} bytes"
            )
        return int.from_bytes(instruction_bytes, byteorder="little")


@cocotb.test()
async def test_negative_s_immediate_sign_extension(dut):
    instruction = assemble_rv32im("sw x5, -1707(x6)")
    dut.instr.value = instruction
    await Timer(1, unit="ns")

    observed = int(dut.imm_s.value)
    expected = 0xFFFFF955
    assert observed == expected, (
        f"imm_s: expected 0x{expected:08X}, observed 0x{observed:08X}"
    )
