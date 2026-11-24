import re

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


def assemble_rv32im(source):
    """Assemble the small RV32IM assembly subset used by this test."""
    words = []

    def register(text):
        text = text.strip().lower()
        if not re.fullmatch(r"x(?:[0-9]|[12][0-9]|3[01])", text):
            raise ValueError(f"Invalid register: {text}")
        return int(text[1:])

    for line in source.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue

        mnemonic, operands_text = line.lower().split(None, 1)
        operands = [item.strip() for item in operands_text.split(",")]

        if mnemonic == "lui":
            rd = register(operands[0])
            immediate = int(operands[1], 0)
            words.append(((immediate & 0xFFFFF) << 12) | (rd << 7) | 0x37)

        elif mnemonic == "addi":
            rd = register(operands[0])
            rs1 = register(operands[1])
            immediate = int(operands[2], 0)
            words.append(
                ((immediate & 0xFFF) << 20)
                | (rs1 << 15)
                | (rd << 7)
                | 0x13
            )

        elif mnemonic == "sw":
            rs2 = register(operands[0])
            match = re.fullmatch(r"(.+)\((x(?:[0-9]|[12][0-9]|3[01]))\)", operands[1])
            if match is None:
                raise ValueError(f"Invalid store address: {operands[1]}")
            immediate = int(match.group(1), 0)
            rs1 = register(match.group(2))
            immediate &= 0xFFF
            words.append(
                (((immediate >> 5) & 0x7F) << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (0x2 << 12)
                | ((immediate & 0x1F) << 7)
                | 0x23
            )

        else:
            raise ValueError(f"Unsupported instruction: {mnemonic}")

    return words


@cocotb.test()
async def addi_preserves_0x7fffffff_for_store(dut):
    program = assemble_rv32im(
        """
        lui x1, 0x80000
        addi x1, x1, -1
        addi x2, x1, 0
        sw x2, 0(x0)
        """
    )

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = program[0]
    dut.data_read_data.value = 0x00000000

    clock = Clock(dut.clk, 10, unit="ns")
    cocotb.start_soon(clock.start())

    await Timer(1, unit="ns")
    observed_pc = int(dut.instr_addr.value)
    assert observed_pc == 0x00000000, (
        f"Expected instr_addr=0x00000000 during reset, observed 0x{observed_pc:08X}"
    )

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    dut.rst.value = 0

    memory = {}
    for index, instruction in enumerate(program):
        expected_pc = index * 4
        observed_pc = int(dut.instr_addr.value)
        assert observed_pc == expected_pc, (
            f"Expected instr_addr=0x{expected_pc:08X}, observed 0x{observed_pc:08X}"
        )

        dut.instr_data.value = instruction
        await Timer(1, unit="ns")

        write_enable = int(dut.data_write.value)
        address = int(dut.data_addr.value)
        width = int(dut.data_width.value)
        write_data = int(dut.data_write_data.value)

        if index < 3:
            assert write_enable == 0, (
                f"Expected data_write=0 before focal store, observed {write_enable}"
            )
        else:
            assert write_enable == 1, (
                f"Expected focal store data_write=1, observed {write_enable}"
            )
            assert address == 0x00000000, (
                f"Expected store address=0x00000000, observed 0x{address:08X}"
            )
            assert width == 0x2, (
                f"Expected store data_width=0x2, observed 0x{width:X}"
            )
            assert write_data == 0x7FFFFFFF, (
                f"Expected ADDI result/store data=0x7FFFFFFF, observed 0x{write_data:08X}"
            )

        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")

        if write_enable:
            if width == 0x2:
                memory[address & 0xFFFFFFFC] = write_data
            elif width == 0x1:
                memory[address & 0xFFFFFFFC] = write_data & 0xFFFF
            else:
                memory[address & 0xFFFFFFFC] = write_data & 0xFF

    observed_memory = memory.get(0x00000000, 0x00000000)
    assert observed_memory == 0x7FFFFFFF, (
        f"Expected memory[0x00000000]=0x7FFFFFFF, observed 0x{observed_memory:08X}"
    )
