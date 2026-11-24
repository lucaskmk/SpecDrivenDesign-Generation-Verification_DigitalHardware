import shutil
import subprocess
import tempfile
from pathlib import Path

import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source: str) -> int:
    """Assemble one RV32IM instruction from legal GNU assembler source."""
    toolchains = (
        ("riscv64-unknown-elf-as", "riscv64-unknown-elf-objcopy"),
        ("riscv32-unknown-elf-as", "riscv32-unknown-elf-objcopy"),
        ("riscv64-linux-gnu-as", "riscv64-linux-gnu-objcopy"),
    )

    for assembler_name, objcopy_name in toolchains:
        assembler = shutil.which(assembler_name)
        objcopy = shutil.which(objcopy_name)
        if assembler and objcopy:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                asm_path = temp_path / "instruction.s"
                obj_path = temp_path / "instruction.o"
                bin_path = temp_path / "instruction.bin"

                asm_path.write_text(f".text\n{source}\n", encoding="ascii")
                subprocess.run(
                    [assembler, "-march=rv32im", "-mabi=ilp32", "-o", str(obj_path), str(asm_path)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                subprocess.run(
                    [objcopy, "-O", "binary", "-j", ".text", str(obj_path), str(bin_path)],
                    check=True,
                    capture_output=True,
                    text=True,
                )

                instruction_bytes = bin_path.read_bytes()
                if len(instruction_bytes) != 4:
                    raise ValueError("Expected exactly one 32-bit instruction")
                return int.from_bytes(instruction_bytes, byteorder="little")

    raise RuntimeError("A GNU RV32IM assembler and matching objcopy are required")


@cocotb.test()
async def checks_store_immediate_packing(dut):
    displacement = 0x5A4
    dut.instr.value = assemble_rv32im(f"sw x5, {displacement}(x6)")

    await Timer(1, unit="ns")

    observed = int(dut.imm_s.value)
    assert observed == displacement, (
        f"Expected imm_s=0x{displacement:08X}, observed 0x{observed:08X}"
    )
