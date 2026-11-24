import re

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


def assemble_rv32im(source):
    """Assemble the RV32IM instructions used by this directed program."""
    pending = []
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

        pending.append((pc, line))
        pc += 4

    def reg(token):
        match = re.fullmatch(r"x([0-9]|[12][0-9]|3[01])", token.strip())
        if not match:
            raise ValueError(f"Invalid register: {token}")
        return int(match.group(1))

    def encode_i(opcode, funct3, rd, rs1, immediate):
        imm = immediate & 0xFFF
        return (
            (imm << 20)
            | (rs1 << 15)
            | (funct3 << 12)
            | (rd << 7)
            | opcode
        )

    def encode_s(funct3, rs1, rs2, immediate):
        imm = immediate & 0xFFF
        return (
            (((imm >> 5) & 0x7F) << 25)
            | (rs2 << 20)
            | (rs1 << 15)
            | (funct3 << 12)
            | ((imm & 0x1F) << 7)
            | 0x23
        )

    def encode_jal(rd, offset):
        imm = offset & 0x1FFFFF
        return (
            (((imm >> 20) & 1) << 31)
            | (((imm >> 1) & 0x3FF) << 21)
            | (((imm >> 11) & 1) << 20)
            | (((imm >> 12) & 0xFF) << 12)
            | (rd << 7)
            | 0x6F
        )

    words = []
    for instruction_pc, text in pending:
        mnemonic, operands_text = text.split(None, 1)
        operands = [part.strip() for part in operands_text.split(",")]

        if mnemonic == "addi":
            rd, rs1 = reg(operands[0]), reg(operands[1])
            immediate = int(operands[2], 0)
            words.append(encode_i(0x13, 0, rd, rs1, immediate))
        elif mnemonic == "srli":
            rd, rs1 = reg(operands[0]), reg(operands[1])
            shamt = int(operands[2], 0)
            if not 0 <= shamt <= 31:
                raise ValueError(f"Invalid SRLI shift amount: {shamt}")
            words.append(encode_i(0x13, 5, rd, rs1, shamt))
        elif mnemonic == "sw":
            rs2 = reg(operands[0])
            memory_operand = re.fullmatch(r"(-?(?:0x[0-9a-fA-F]+|[0-9]+))\((x(?:[0-9]|[12][0-9]|3[01]))\)", operands[1])
            if not memory_operand:
                raise ValueError(f"Invalid store operand: {operands[1]}")
            immediate = int(memory_operand.group(1), 0)
            rs1 = reg(memory_operand.group(2))
            words.append(encode_s(2, rs1, rs2, immediate))
        elif mnemonic == "jal":
            rd = reg(operands[0])
            target = labels[operands[1]]
            words.append(encode_jal(rd, target - instruction_pc))
        else:
            raise ValueError(f"Unsupported instruction: {mnemonic}")

    return words


@cocotb.test()
async def srli_zero_shift_preserves_all_ones(dut):
    program = assemble_rv32im(
        """
        addi x1, x0, -1
        srli x2, x1, 0
        sw x2, 0(x0)
    halt:
        jal x0, halt
        """
    )
    rom = {4 * index: word for index, word in enumerate(program)}

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected reset PC 0x00000000, observed 0x{int(dut.instr_addr.value):08X}"
    )
    dut.rst.value = 0

    committed_stores = []
    memory_bytes = {}

    for _ in range(len(program)):
        await Timer(1, unit="ns")
        current_pc = int(dut.instr_addr.value)
        assert current_pc in rom, (
            f"Expected a program address, observed PC 0x{current_pc:08X}"
        )
        dut.instr_data.value = rom[current_pc]
        await Timer(1, unit="ns")

        write = int(dut.data_write.value)
        if write:
            address = int(dut.data_addr.value)
            width = int(dut.data_width.value)
            write_data = int(dut.data_write_data.value)
            committed_stores.append((address, width, write_data))

        await RisingEdge(dut.clk)
        if write:
            byte_count = 1 << width
            for lane in range(byte_count):
                memory_bytes[address + lane] = (write_data >> (8 * lane)) & 0xFF
        await Timer(1, unit="ns")

    assert committed_stores == [(0x00000000, 0x2, 0xFFFFFFFF)], (
        "Expected one SW transaction at address 0x00000000 with width 0x2 "
        f"and data 0xFFFFFFFF, observed {committed_stores}"
    )
    assert [memory_bytes.get(address, 0) for address in range(4)] == [
        0xFF,
        0xFF,
        0xFF,
        0xFF,
    ], (
        "Expected the final stored word to be 0xFFFFFFFF, observed "
        f"{[memory_bytes.get(address, 0) for address in range(4)]}"
    )
