import shutil
import subprocess
import tempfile
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer


def assemble_rv32im(source):
    """Assemble RV32IM source with an installed RISC-V GNU or LLVM toolchain."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        source_path = temp / "program.s"
        object_path = temp / "program.o"
        binary_path = temp / "program.bin"
        source_path.write_text(source)

        tool_pairs = (
            ("riscv64-unknown-elf-as", "riscv64-unknown-elf-objcopy"),
            ("riscv32-unknown-elf-as", "riscv32-unknown-elf-objcopy"),
            ("riscv64-linux-gnu-as", "riscv64-linux-gnu-objcopy"),
        )

        for assembler_name, objcopy_name in tool_pairs:
            assembler = shutil.which(assembler_name)
            objcopy = shutil.which(objcopy_name)
            if assembler and objcopy:
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
                break
        else:
            clang = shutil.which("clang")
            objcopy = shutil.which("llvm-objcopy") or shutil.which("llvm-objcopy-18")
            if not clang or not objcopy:
                raise RuntimeError("An RV32IM assembler and objcopy are required")
            subprocess.run(
                [
                    clang,
                    "--target=riscv32-unknown-elf",
                    "-march=rv32im",
                    "-mabi=ilp32",
                    "-c",
                    str(source_path),
                    "-o",
                    str(object_path),
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

        raw = binary_path.read_bytes()
        if len(raw) % 4:
            raise RuntimeError("Assembler emitted a non-word-aligned program")
        return [
            int.from_bytes(raw[offset : offset + 4], "little")
            for offset in range(0, len(raw), 4)
        ]


@cocotb.test()
async def srl_zero_shift_preserves_all_ones(dut):
    program = assemble_rv32im(
        """
        .section .text
        .option norvc
        .globl _start
    _start:
        addi x1, x0, -1
        addi x2, x0, 0
        srl  x3, x1, x2
        sw   x3, 0(x0)
    halt:
        j halt
        """
    )
    instruction_memory = {
        address: word for address, word in enumerate(program, start=0)
    }
    instruction_memory = {
        address * 4: word for address, word in instruction_memory.items()
    }

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000

    clock = Clock(dut.clk, 10, unit="ns")
    clock.start()

    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected reset instr_addr=0x00000000, "
        f"observed 0x{int(dut.instr_addr.value):08X}"
    )
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    dut.rst.value = 0

    memory_words = {}
    focal_store_seen = False

    for _ in range(4):
        await FallingEdge(dut.clk)
        pc = int(dut.instr_addr.value)
        dut.instr_data.value = instruction_memory.get(pc, 0x00000000)
        dut.data_read_data.value = 0x00000000
        await Timer(1, unit="ns")

        if int(dut.data_write.value) == 1:
            observed_addr = int(dut.data_addr.value)
            observed_width = int(dut.data_width.value)
            observed_data = int(dut.data_write_data.value)
            assert observed_addr == 0x00000000, (
                f"Expected store address 0x00000000, observed 0x{observed_addr:08X}"
            )
            assert observed_width == 0x2, (
                f"Expected word-store width 0x2, observed 0x{observed_width:X}"
            )
            assert observed_data == 0xFFFFFFFF, (
                f"Expected SRL result 0xFFFFFFFF, observed 0x{observed_data:08X}"
            )
            focal_store_seen = True

        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")

        if focal_store_seen:
            memory_words[observed_addr] = observed_data
            break

    assert focal_store_seen, "Expected the program to perform its focal word store"
    assert memory_words.get(0x00000000) == 0xFFFFFFFF, (
        f"Expected committed word 0xFFFFFFFF at 0x00000000, "
        f"observed 0x{memory_words.get(0x00000000, 0):08X}"
    )
