import shutil
import subprocess
import tempfile
from pathlib import Path

import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble RV32IM source and return its instruction words."""
    for prefix in ("riscv64-unknown-elf-", "riscv32-unknown-elf-"):
        assembler = shutil.which(prefix + "as")
        objcopy = shutil.which(prefix + "objcopy")
        if assembler and objcopy:
            break
    else:
        raise RuntimeError("An RV32IM GNU assembler and objcopy are required")

    with tempfile.TemporaryDirectory() as directory:
        asm_path = Path(directory) / "program.s"
        obj_path = Path(directory) / "program.o"
        bin_path = Path(directory) / "program.bin"
        asm_path.write_text(source)
        subprocess.run(
            [assembler, "-march=rv32im", "-mabi=ilp32",
             "-o", str(obj_path), str(asm_path)],
            check=True,
        )
        subprocess.run(
            [objcopy, "-O", "binary", str(obj_path), str(bin_path)],
            check=True,
        )
        data = bin_path.read_bytes()

    assert len(data) % 4 == 0, "Assembled program is not word-aligned"
    return [
        int.from_bytes(data[offset:offset + 4], "little")
        for offset in range(0, len(data), 4)
    ]


@cocotb.test()
async def test_jal_immediate_implicit_low_bit(dut):
    dut.instr.value = 0x00000000
    await Timer(1, unit="ns")

    words = assemble_rv32im(
        """
        .text
        jal x1, forward
        addi x0, x0, 0
    forward:
        addi x0, x0, 0
        """
    )
    dut.instr.value = words[0]
    await Timer(1, unit="ns")

    observed = int(dut.imm_j.value) & 0x00000001
    assert observed == 0x00000000, (
        f"imm_j[0]: expected 0x00000000, observed 0x{observed:08X}"
    )
