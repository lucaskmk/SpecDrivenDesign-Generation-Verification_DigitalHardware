import re

import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble the small RV32I source program used by this test."""
    instructions = []
    labels = {}
    pc = 0

    for raw_line in source.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue

        if ":" in line:
            label, line = line.split(":", 1)
            labels[label.strip()] = pc
            line = line.strip()
            if not line:
                continue

        instructions.append((pc, line))
        pc += 4

    words = {}
    for address, line in instructions:
        fields = line.replace(",", " ").split()
        mnemonic = fields[0].lower()

        if mnemonic == "addi":
            rd, rs1, immediate = map(int, fields[1:4])
            imm = immediate & 0xFFF
            word = (
                (imm << 20)
                | (rs1 << 15)
                | (0x0 << 12)
                | (rd << 7)
                | 0x13
            )
        elif mnemonic == "sw":
            rs2, memory_operand = fields[1:3]
            match = re.fullmatch(r"(-?\d+)\((x\d+)\)", memory_operand)
            if match is None:
                raise ValueError(f"Invalid store operand: {memory_operand}")
            immediate = int(match.group(1))
            rs1 = int(match.group(2)[1:])
            rs2 = int(rs2[1:])
            imm = immediate & 0xFFF
            word = (
                (((imm >> 5) & 0x7F) << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (0x2 << 12)
                | ((imm & 0x1F) << 7)
                | 0x23
            )
        elif mnemonic == "jal":
            rd = int(fields[1][1:])
            target = labels[fields[2]]
            offset = target - address
            imm = offset & 0x1FFFFF
            word = (
                (((imm >> 20) & 0x1) << 31)
                | (((imm >> 1) & 0x3FF) << 21)
                | (((imm >> 11) & 0x1) << 20)
                | (((imm >> 12) & 0xFF) << 12)
                | (rd << 7)
                | 0x6F
            )
        else:
            raise ValueError(f"Unsupported assembly instruction: {mnemonic}")

        words[address] = word

    return words


@cocotb.test()
async def jal_x0_skips_instruction_and_reaches_target(dut):
    program = assemble_rv32im(
        """
        start:
            addi x1, x0, 1
            jal x0, target
            addi x1, x0, 2
        target:
            addi x1, x1, 2
            sw x1, 0(x0)
            jal x0, halt
        halt:
            jal x0, halt
        """
    )

    # Initialize every input and assert asynchronous reset.
    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = program[0]
    dut.data_read_data.value = 0x00000000
    await Timer(1, unit="ns")

    observed_pc = int(dut.instr_addr.value)
    assert observed_pc == 0x00000000, (
        f"Expected reset PC 0x00000000, observed 0x{observed_pc:08X}"
    )
    assert int(dut.data_write.value) == 0, "Expected no store during reset"

    dut.rst.value = 0

    expected_path = (0x00, 0x04, 0x0C, 0x10, 0x14, 0x18)
    expected_next = (0x04, 0x0C, 0x10, 0x14, 0x18, 0x18)
    transactions = []
    memory_bytes = {}

    for pc, next_pc in zip(expected_path, expected_next):
        observed_pc = int(dut.instr_addr.value)
        assert observed_pc == pc, (
            f"Expected fetch PC 0x{pc:08X}, observed 0x{observed_pc:08X}"
        )

        dut.instr_data.value = program[pc]
        await Timer(1, unit="ns")

        if pc == 0x10:
            assert int(dut.data_write.value) == 1, "Expected the target store"
            observed_addr = int(dut.data_addr.value)
            observed_width = int(dut.data_width.value)
            observed_data = int(dut.data_write_data.value)
            assert observed_addr == 0x00000000, (
                f"Expected store address 0x00000000, observed 0x{observed_addr:08X}"
            )
            assert observed_width == 0x2, (
                f"Expected word width 0x2, observed 0x{observed_width:X}"
            )
            assert observed_data == 0x00000003, (
                f"Expected store data 0x00000003, observed 0x{observed_data:08X}"
            )
            transactions.append((observed_addr, observed_width, observed_data))
        else:
            assert int(dut.data_write.value) == 0, (
                f"Expected no store at PC 0x{pc:08X}"
            )

        # The external memory commits a store on the rising edge.
        if int(dut.data_write.value) == 1:
            address = int(dut.data_addr.value)
            width = int(dut.data_width.value)
            value = int(dut.data_write_data.value)
            byte_count = 1 << width
            for lane in range(byte_count):
                memory_bytes[address + lane] = (value >> (8 * lane)) & 0xFF

        dut.clk.value = 1
        await Timer(1, unit="ns")

        observed_next_pc = int(dut.instr_addr.value)
        assert observed_next_pc == next_pc, (
            f"Expected next PC 0x{next_pc:08X}, "
            f"observed 0x{observed_next_pc:08X}"
        )

        dut.clk.value = 0
        await Timer(1, unit="ns")

    assert transactions == [(0x00000000, 0x2, 0x00000003)], (
        f"Expected one word store (0x00000000, 0x2, 0x00000003), "
        f"observed {transactions}"
    )
    expected_bytes = {
        0x00000000: 0x03,
        0x00000001: 0x00,
        0x00000002: 0x00,
        0x00000003: 0x00,
    }
    assert memory_bytes == expected_bytes, (
        f"Expected memory bytes {expected_bytes}, observed {memory_bytes}"
    )
