import re

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


def assemble_rv32im(source: str) -> list[int]:
    """Assemble the RV32IM instructions used by this legal test program."""
    words = []

    for line in source.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue

        parts = line.replace(",", " ").split()
        mnemonic = parts[0].lower()

        def reg(token):
            token = token.lower()
            if not re.fullmatch(r"x(?:[0-9]|[12][0-9]|3[01])", token):
                raise ValueError(f"Invalid register: {token}")
            return int(token[1:])

        if mnemonic == "lui":
            rd = reg(parts[1])
            imm20 = int(parts[2], 0)
            words.append(((imm20 & 0xFFFFF) << 12) | (rd << 7) | 0x37)
        elif mnemonic == "addi":
            rd, rs1 = reg(parts[1]), reg(parts[2])
            imm12 = int(parts[3], 0)
            words.append(
                ((imm12 & 0xFFF) << 20)
                | (rs1 << 15)
                | (rd << 7)
                | 0x13
            )
        elif mnemonic == "srai":
            rd, rs1 = reg(parts[1]), reg(parts[2])
            shamt = int(parts[3], 0)
            if not 0 <= shamt <= 31:
                raise ValueError(f"Invalid SRAI shift amount: {shamt}")
            words.append(
                (0x20 << 25)
                | (shamt << 20)
                | (rs1 << 15)
                | (0x5 << 12)
                | (rd << 7)
                | 0x13
            )
        elif mnemonic == "sw":
            rs2 = reg(parts[1])
            match = re.fullmatch(r"(.+)\((x(?:[0-9]|[12][0-9]|3[01]))\)", parts[2])
            if match is None:
                raise ValueError(f"Invalid store address: {parts[2]}")
            imm12 = int(match.group(1), 0)
            rs1 = reg(match.group(2))
            imm = imm12 & 0xFFF
            words.append(
                (((imm >> 5) & 0x7F) << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (0x2 << 12)
                | ((imm & 0x1F) << 7)
                | 0x23
            )
        else:
            raise ValueError(f"Unsupported instruction in test source: {mnemonic}")

    return words


@cocotb.test()
async def srai_zero_shift_preserves_positive_value_in_store(dut):
    program = assemble_rv32im(
        """
        lui  x1, 0x80000
        addi x1, x1, -1
        srai x2, x1, 0
        sw   x2, 0(x0)
        """
    )
    instruction_memory = {index * 4: word for index, word in enumerate(program)}
    data_memory = {}

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = instruction_memory[0]
    dut.data_read_data.value = 0

    clock = Clock(dut.clk, 10, unit="ns")
    clock.start()

    # Hold asynchronous reset across a rising edge before execution.
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    dut.rst.value = 0
    await Timer(1, unit="ns")

    committed_store = None

    for pc in range(0, len(program) * 4, 4):
        assert int(dut.instr_addr.value) == pc, (
            f"Expected instr_addr=0x{pc:08X}, "
            f"observed 0x{int(dut.instr_addr.value):08X}"
        )
        dut.instr_data.value = instruction_memory[pc]
        await Timer(1, unit="ns")

        is_focal_store = pc == (len(program) - 1) * 4
        if is_focal_store:
            observed_write = int(dut.data_write.value)
            observed_addr = int(dut.data_addr.value)
            observed_width = int(dut.data_width.value)
            observed_data = int(dut.data_write_data.value)

            assert observed_write == 1, (
                f"Expected data_write=1 for the SRAI result store, "
                f"observed {observed_write}"
            )
            assert observed_addr == 0x00000000, (
                f"Expected data_addr=0x00000000, observed 0x{observed_addr:08X}"
            )
            assert observed_width == 0x2, (
                f"Expected data_width=0x2, observed 0x{observed_width:X}"
            )
            assert observed_data == 0x7FFFFFFF, (
                f"Expected store data=0x7FFFFFFF, observed 0x{observed_data:08X}"
            )

        await RisingEdge(dut.clk)

        if is_focal_store:
            committed_store = (
                int(dut.data_addr.value),
                int(dut.data_width.value),
                int(dut.data_write_data.value),
            )
            data_memory[committed_store[0]] = committed_store[2]

        await Timer(1, unit="ns")

    assert committed_store is not None, "Expected the focal store to commit"
    assert data_memory.get(0x00000000) == 0x7FFFFFFF, (
        f"Expected committed word at 0x00000000 to be 0x7FFFFFFF, "
        f"observed 0x{data_memory.get(0x00000000, 0):08X}"
    )
