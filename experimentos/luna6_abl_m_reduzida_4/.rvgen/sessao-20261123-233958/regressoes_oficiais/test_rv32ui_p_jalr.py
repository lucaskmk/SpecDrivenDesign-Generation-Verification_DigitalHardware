import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


def assemble_rv32im(source):
    """Assemble RV32IM source at address zero and return its .text words."""
    toolchains = (
        "riscv64-unknown-elf",
        "riscv32-unknown-elf",
        "riscv64-unknown-linux-gnu",
        "riscv32-unknown-linux-gnu",
    )

    for prefix in toolchains:
        gcc = shutil.which(f"{prefix}-gcc")
        objcopy = shutil.which(f"{prefix}-objcopy")
        if gcc and objcopy:
            break
    else:
        raise RuntimeError("No supported RV32IM GCC and objcopy toolchain found")

    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        source_path = directory / "jalr_case.S"
        elf_path = directory / "jalr_case.elf"
        binary_path = directory / "jalr_case.bin"
        source_path.write_text(source)

        subprocess.run(
            [
                gcc,
                "-march=rv32im",
                "-mabi=ilp32",
                "-fno-pic",
                "-fno-pie",
                "-nostdlib",
                "-nostartfiles",
                "-Wl,-Ttext=0",
                "-Wl,-e,_start",
                "-Wl,--no-relax",
                "-Wl,--build-id=none",
                "-o",
                str(elf_path),
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
                str(elf_path),
                str(binary_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        text = binary_path.read_bytes()

    assert len(text) % 4 == 0, f"Expected 4-byte instructions, observed {len(text)} text bytes"
    return list(struct.unpack(f"<{len(text) // 4}I", text))


@cocotb.test()
async def jalr_clears_only_the_low_target_bit(dut):
    words = assemble_rv32im(
        """
        .option norvc
        .text
        .globl _start
_start:
        li      t0, 1
        la      t1, target
        addi    t1, t1, 1
        jalr    t0, t1, 0
target:
        sw      t0, 4(x0)
halt:
        jal     x0, halt
"""
    )

    rom = {index * 4: word for index, word in enumerate(words)}
    halt_word = words[-1]

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0
    dut.data_read_data.value = 0
    Clock(dut.clk, 10, unit="ns").start()

    await Timer(1, unit="ns")
    observed_pc = int(dut.instr_addr.value)
    assert observed_pc == 0x00000000, (
        f"Expected reset PC=0x00000000, observed 0x{observed_pc:08X}"
    )

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    dut.rst.value = 0
    await Timer(1, unit="ns")

    fetch_trace = []
    transactions = []
    memory_words = {}

    for _ in range(12):
        pc = int(dut.instr_addr.value)
        fetch_trace.append(pc)
        dut.instr_data.value = rom.get(pc, halt_word)
        await Timer(1, unit="ns")

        write = int(dut.data_write.value)
        if write:
            address = int(dut.data_addr.value)
            width = int(dut.data_width.value)
            write_data = int(dut.data_write_data.value)
        else:
            address = 0
            width = 0
            write_data = 0

        await RisingEdge(dut.clk)

        if write:
            transactions.append((address, width, write_data))
            if width == 2:
                memory_words[address] = write_data
            elif width == 1:
                old_word = memory_words.get(address & 0xFFFFFFFC, 0)
                shift = (address & 0x2) * 8
                mask = 0xFFFF << shift
                memory_words[address & 0xFFFFFFFC] = (
                    (old_word & ~mask) | ((write_data & 0xFFFF) << shift)
                )
            else:
                old_word = memory_words.get(address & 0xFFFFFFFC, 0)
                shift = (address & 0x3) * 8
                mask = 0xFF << shift
                memory_words[address & 0xFFFFFFFC] = (
                    (old_word & ~mask) | ((write_data & 0xFF) << shift)
                )

        await Timer(1, unit="ns")
        if transactions:
            break

    expected_trace = [0x00000000, 0x00000004, 0x00000008, 0x0000000C, 0x00000010, 0x00000014]
    assert fetch_trace == expected_trace, (
        f"Expected fetch trace {[f'0x{x:08X}' for x in expected_trace]}, "
        f"observed {[f'0x{x:08X}' for x in fetch_trace]}"
    )

    expected_transaction = (0x00000004, 0x2, 0x00000014)
    assert transactions == [expected_transaction], (
        f"Expected store transaction (address=0x00000004, width=0x2, data=0x00000014), "
        f"observed {transactions}"
    )

    observed_memory_word = memory_words.get(0x00000004, 0)
    assert observed_memory_word == 0x00000014, (
        f"Expected memory[0x00000004]=0x00000014, observed 0x{observed_memory_word:08X}"
    )
