import re

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


def assemble_rv32im(source):
    """Assemble the small RV32IM source program used by this test."""
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

    def register(token):
        token = token.strip().lower()
        if not re.fullmatch(r"x(?:[0-9]|[12][0-9]|3[01])", token):
            raise ValueError(f"Unsupported register: {token}")
        return int(token[1:])

    words = {}
    for address, line in instructions:
        mnemonic, _, operand_text = line.partition(" ")
        operands = [item.strip() for item in operand_text.split(",")]
        mnemonic = mnemonic.lower()

        if mnemonic == "lui":
            rd = register(operands[0])
            imm = int(operands[1], 0)
            if not 0 <= imm <= 0xFFFFF:
                raise ValueError("LUI immediate is outside the 20-bit range")
            word = (imm << 12) | (rd << 7) | 0x37

        elif mnemonic == "addi":
            rd = register(operands[0])
            rs1 = register(operands[1])
            imm = int(operands[2], 0)
            if not -2048 <= imm <= 2047:
                raise ValueError("ADDI immediate is outside the signed 12-bit range")
            word = (
                ((imm & 0xFFF) << 20)
                | (rs1 << 15)
                | (rd << 7)
                | 0x13
            )

        elif mnemonic == "sub":
            rd = register(operands[0])
            rs1 = register(operands[1])
            rs2 = register(operands[2])
            word = (
                (0x20 << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (rd << 7)
                | 0x33
            )

        elif mnemonic == "sw":
            rs2 = register(operands[0])
            match = re.fullmatch(r"\s*(-?(?:0[xX][0-9a-fA-F]+|[0-9]+))\s*\(\s*(x(?:[0-9]|[12][0-9]|3[01]))\s*\)\s*", operands[1])
            if not match:
                raise ValueError(f"Unsupported SW address: {operands[1]}")
            imm = int(match.group(1), 0)
            rs1 = register(match.group(2))
            if not -2048 <= imm <= 2047:
                raise ValueError("SW immediate is outside the signed 12-bit range")
            encoded_imm = imm & 0xFFF
            word = (
                (((encoded_imm >> 5) & 0x7F) << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (0x2 << 12)
                | ((encoded_imm & 0x1F) << 7)
                | 0x23
            )

        elif mnemonic == "jal":
            rd = register(operands[0])
            if operands[1] not in labels:
                raise ValueError(f"Undefined JAL label: {operands[1]}")
            offset = labels[operands[1]] - address
            if offset % 2 or not -(1 << 20) <= offset < (1 << 20):
                raise ValueError("JAL target offset is out of range or misaligned")
            encoded_imm = offset & 0x1FFFFF
            word = (
                (((encoded_imm >> 20) & 0x1) << 31)
                | (((encoded_imm >> 1) & 0x3FF) << 21)
                | (((encoded_imm >> 11) & 0x1) << 20)
                | (((encoded_imm >> 12) & 0xFF) << 12)
                | (rd << 7)
                | 0x6F
            )

        else:
            raise ValueError(f"Unsupported instruction: {mnemonic}")

        words[address] = word

    return words


@cocotb.test()
async def sub_result_for_official_case_is_stored(dut):
    source = """
        lui  x1, 0x80000
        addi x1, x1, -1
        sub  x3, x1, x0
        sw   x3, 0(x0)
    halt: jal  x0, halt
    """
    program = assemble_rv32im(source)

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000

    clock = Clock(dut.clk, 10, unit="ns")
    cocotb.start_soon(clock.start())

    await Timer(2, unit="ns")
    observed_pc = int(dut.instr_addr.value)
    assert observed_pc == 0x00000000, (
        f"Expected instr_addr=0x00000000 during reset, observed 0x{observed_pc:08X}"
    )
    dut.rst.value = 0
    await Timer(1, unit="ns")

    memory = {}
    committed_store = False

    for _ in range(12):
        fetch_address = int(dut.instr_addr.value)
        assert fetch_address in program, (
            f"Expected a program instruction at 0x{fetch_address:08X}"
        )
        dut.instr_data.value = program[fetch_address]
        dut.data_read_data.value = 0x00000000
        await Timer(1, unit="ns")

        write_enabled = int(dut.data_write.value)
        store = None
        if write_enabled:
            store_address = int(dut.data_addr.value)
            store_width = int(dut.data_width.value)
            store_data = int(dut.data_write_data.value)
            assert store_address == 0x00000000, (
                f"Expected store address 0x00000000, observed 0x{store_address:08X}"
            )
            assert store_width == 0x2, (
                f"Expected word width 0x2, observed 0x{store_width:X}"
            )
            assert store_data == 0x7FFFFFFF, (
                f"Expected sub result 0x7FFFFFFF on the store bus, "
                f"observed 0x{store_data:08X}"
            )
            store = (store_address, store_width, store_data)

        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")

        if store is not None:
            address, width, data = store
            byte_count = 1 << width
            for lane in range(byte_count):
                memory[address + lane] = (data >> (8 * lane)) & 0xFF
            committed_store = True
            break

    assert committed_store, "Expected the program to commit its result store"
    observed_word = sum(memory.get(lane, 0) << (8 * lane) for lane in range(4))
    assert observed_word == 0x7FFFFFFF, (
        f"Expected stored word 0x7FFFFFFF, observed 0x{observed_word:08X}"
    )
