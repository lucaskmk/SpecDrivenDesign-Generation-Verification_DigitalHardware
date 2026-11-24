import re

import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble the small RV32IM source subset used by this test."""
    lines = []
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

        lines.append((pc, line))
        pc += 4

    def reg(token):
        token = token.strip().lower()
        if not token.startswith("x"):
            raise ValueError(f"Expected register, got {token}")
        value = int(token[1:], 10)
        if not 0 <= value < 32:
            raise ValueError(f"Register out of range: {token}")
        return value

    def encode_i_imm(value):
        if not -2048 <= value <= 2047:
            raise ValueError(f"I-immediate out of range: {value}")
        return value & 0xFFF

    program = {}
    for address, line in lines:
        parts = line.replace(",", " ").split()
        mnemonic = parts[0].lower()
        operands = parts[1:]

        if mnemonic == "lui":
            rd = reg(operands[0])
            imm = int(operands[1], 0)
            if not 0 <= imm <= 0xFFFFF:
                raise ValueError(f"LUI immediate out of range: {imm}")
            word = (imm << 12) | (rd << 7) | 0x37

        elif mnemonic in ("addi", "sltiu"):
            rd = reg(operands[0])
            rs1 = reg(operands[1])
            imm = encode_i_imm(int(operands[2], 0))
            funct3 = 0x0 if mnemonic == "addi" else 0x3
            word = (imm << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | 0x13

        elif mnemonic == "sw":
            rs2 = reg(operands[0])
            match = re.fullmatch(r"(-?(?:0x[0-9a-fA-F]+|\d+))\((x\d+)\)", operands[1])
            if match is None:
                raise ValueError(f"Invalid SW address operand: {operands[1]}")
            imm = encode_i_imm(int(match.group(1), 0))
            rs1 = reg(match.group(2))
            word = (
                ((imm >> 5) << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (0x2 << 12)
                | ((imm & 0x1F) << 7)
                | 0x23
            )

        elif mnemonic == "jal":
            rd = reg(operands[0])
            target = labels[operands[1]]
            imm = target - address
            if imm & 1 or not -(1 << 20) <= imm < (1 << 20):
                raise ValueError(f"JAL target out of range or unaligned: {target}")
            encoded = imm & 0x1FFFFF
            word = (
                (((encoded >> 20) & 1) << 31)
                | (((encoded >> 1) & 0x3FF) << 21)
                | (((encoded >> 11) & 1) << 20)
                | (((encoded >> 12) & 0xFF) << 12)
                | (rd << 7)
                | 0x6F
            )

        else:
            raise ValueError(f"Unsupported instruction in test program: {mnemonic}")

        program[address] = word

    return program


@cocotb.test()
async def sltiu_zero_destination_remains_zero(dut):
    program = assemble_rv32im(
        """
        start:
            lui   x1, 0x00ff0
            addi  x1, x1, 255
            addi  x2, x0, 256
            sltiu x0, x1, -1
            sw    x0, 0(x2)
        halt:
            jal   x0, halt
        """
    )

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000
    await Timer(2, unit="ns")

    observed_pc = int(dut.instr_addr.value)
    assert observed_pc == 0x00000000, (
        f"Expected reset PC=0x00000000, observed 0x{observed_pc:08X}"
    )
    observed_write = int(dut.data_write.value)
    assert observed_write == 0, f"Expected data_write=0, observed {observed_write}"

    dut.rst.value = 0
    await Timer(1, unit="ns")

    store_seen = False
    stored_word = None

    for _ in range(6):
        pc = int(dut.instr_addr.value)
        assert pc in program, f"Expected a program instruction at 0x{pc:08X}"
        dut.instr_data.value = program[pc]
        await Timer(1, unit="ns")

        if pc == 0x00000010:
            store_seen = True
            observed_write = int(dut.data_write.value)
            assert observed_write == 1, (
                f"Expected data_write=1 for the witness store, observed {observed_write}"
            )

            observed_addr = int(dut.data_addr.value)
            assert observed_addr == 0x00000100, (
                f"Expected store address=0x00000100, observed 0x{observed_addr:08X}"
            )

            observed_width = int(dut.data_width.value)
            assert observed_width == 0x2, (
                f"Expected word width=0x2, observed 0x{observed_width:X}"
            )

            observed_data = int(dut.data_write_data.value)
            assert observed_data == 0x00000000, (
                f"Expected x0 store data=0x00000000, observed 0x{observed_data:08X}"
            )
        else:
            observed_write = int(dut.data_write.value)
            assert observed_write == 0, (
                f"Expected no store at PC=0x{pc:08X}, observed data_write={observed_write}"
            )

        dut.clk.value = 1
        if int(dut.data_write.value) == 1:
            stored_word = int(dut.data_write_data.value)
        await Timer(1, unit="ns")
        dut.clk.value = 0
        await Timer(1, unit="ns")

        if store_seen:
            break

    assert store_seen, "Expected the SLTIU zero-destination witness store"
    assert stored_word == 0x00000000, (
        f"Expected committed word=0x00000000, observed "
        f"{'no write' if stored_word is None else f'0x{stored_word:08X}'}"
    )
