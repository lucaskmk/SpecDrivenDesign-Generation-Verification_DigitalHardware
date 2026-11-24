import shutil
import subprocess
import tempfile
from pathlib import Path

import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble and link RV32IM source, returning its .text words."""
    gcc = next(
        (
            path
            for name in (
                "riscv64-unknown-elf-gcc",
                "riscv32-unknown-elf-gcc",
                "riscv64-linux-gnu-gcc",
            )
            if (path := shutil.which(name)) is not None
        ),
        None,
    )
    clang = shutil.which("clang")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        source_path = temp_path / "program.s"
        elf_path = temp_path / "program.elf"
        text_path = temp_path / "program.bin"
        source_path.write_text(source)

        if gcc is not None:
            command = [
                gcc,
                "-march=rv32im",
                "-mabi=ilp32",
                "-nostdlib",
                "-Wl,--no-relax",
                "-Wl,-Ttext=0x0",
                "-Wl,-e,loop",
                str(source_path),
                "-o",
                str(elf_path),
            ]
        elif clang is not None:
            command = [
                clang,
                "--target=riscv32-unknown-elf",
                "-march=rv32im",
                "-mabi=ilp32",
                "-nostdlib",
                "-Wl,--no-relax",
                "-Wl,-Ttext=0x0",
                "-Wl,-e,loop",
                str(source_path),
                "-o",
                str(elf_path),
            ]
        else:
            raise RuntimeError("No RISC-V-capable GCC or Clang assembler is available")

        subprocess.run(command, check=True, capture_output=True, text=True)

        objcopy = next(
            (
                path
                for name in (
                    "riscv64-unknown-elf-objcopy",
                    "riscv32-unknown-elf-objcopy",
                    "llvm-objcopy",
                    "objcopy",
                )
                if (path := shutil.which(name)) is not None
            ),
            None,
        )
        if objcopy is None:
            raise RuntimeError("No objcopy executable is available")

        subprocess.run(
            [
                objcopy,
                "-O",
                "binary",
                "-j",
                ".text",
                str(elf_path),
                str(text_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        text = text_path.read_bytes()
        if not text or len(text) % 4:
            raise RuntimeError("Assembler produced an invalid .text section")
        return [
            int.from_bytes(text[offset : offset + 4], byteorder="little")
            for offset in range(0, len(text), 4)
        ]


@cocotb.test()
async def jal_x0_self_loop_holds_instruction_address(dut):
    words = assemble_rv32im(
        """
        .section .text
        .globl loop
    loop:
        jal x0, loop
        """
    )
    assert len(words) == 1, f"Expected one instruction, observed {len(words)}"

    rom = {4 * index: word for index, word in enumerate(words)}

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000
    await Timer(1, unit="ns")

    dut.instr_data.value = rom.get(int(dut.instr_addr.value), 0x00000000)
    dut.rst.value = 0
    await Timer(1, unit="ns")

    for commit in range(3):
        address = int(dut.instr_addr.value)
        dut.instr_data.value = rom.get(address, 0x00000000)
        await Timer(1, unit="ns")

        dut.clk.value = 1
        await Timer(1, unit="ns")

        observed = int(dut.instr_addr.value)
        assert observed == 0x00000000, (
            f"After self-loop commit {commit + 1}, expected "
            f"instr_addr=0x00000000, observed 0x{observed:08X}"
        )

        dut.clk.value = 0
        await Timer(1, unit="ns")
