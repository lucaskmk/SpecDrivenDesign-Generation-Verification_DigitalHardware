import re

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer


def assemble_rv32im(source):
    """Assemble the small legal RV32IM subset used by this test."""
    instructions = []
    labels = {}

    for raw_line in source.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue

        if ":" in line:
            label, line = line.split(":", 1)
            labels[label.strip()] = len(instructions) * 4
            line = line.strip()
            if not line:
                continue

        instructions.append(line)

    words = {}
    for index, line in enumerate(instructions):
        pc = index * 4
        fields = line.replace(",", " ").split()
        mnemonic = fields[0].lower()

        def reg(token):
            if not re.fullmatch(r"x(?:[0-9]|[12][0-9]|3[01])", token.lower()):
                raise ValueError(f"Invalid register: {token}")
            return int(token[1:])

        def immediate(token):
            return int(token, 0)

        if mnemonic == "lui":
            rd = reg(fields[1])
            imm = immediate(fields[2])
            word = ((imm & 0xFFFFF) << 12) | (rd << 7) | 0x37

        elif mnemonic == "addi":
            rd = reg(fields[1])
            rs1 = reg(fields[2])
            imm = immediate(fields[3]) & 0xFFF
            word = (imm << 20) | (rs1 << 15) | (rd << 7) | 0x13

        elif mnemonic == "bltu":
            rs1 = reg(fields[1])
            rs2 = reg(fields[2])
            offset = labels[fields[3]] - pc
            imm = offset & 0x1FFF
            word = (
                (((imm >> 12) & 1) << 31)
                | (((imm >> 5) & 0x3F) << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (0x6 << 12)
                | (((imm >> 1) & 0xF) << 8)
                | (((imm >> 11) & 1) << 7)
                | 0x63
            )

        elif mnemonic == "sw":
            rs2 = reg(fields[1])
            match = re.fullmatch(r"(-?(?:0[xX][0-9a-fA-F]+|[0-9]+))\((x[0-9]+)\)", fields[2])
            if not match:
                raise ValueError(f"Invalid store address: {fields[2]}")
            imm = int(match.group(1), 0) & 0xFFF
            rs1 = reg(match.group(2))
            word = (
                (((imm >> 5) & 0x7F) << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (0x2 << 12)
                | ((imm & 0x1F) << 7)
                | 0x23
            )

        elif mnemonic == "jal":
            rd = reg(fields[1])
            offset = labels[fields[2]] - pc
            imm = offset & 0x1FFFFF
            word = (
                (((imm >> 20) & 1) << 31)
                | (((imm >> 1) & 0x3FF) << 21)
                | (((imm >> 11) & 1) << 20)
                | (((imm >> 12) & 0xFF) << 12)
                | (rd << 7)
                | 0x6F
            )

        else:
            raise ValueError(f"Unsupported instruction in test source: {mnemonic}")

        words[pc] = word

    return words, labels


@cocotb.test()
async def bltu_uses_unsigned_comparison(dut):
    source = """
        lui   x1, 0x80000
        addi  x2, x0, 1
    compare:
        bltu  x1, x2, wrong_path
        addi  x3, x0, 1
        sw    x3, 0(x0)
        jal   x0, halt
    wrong_path:
        addi  x3, x0, 2
        sw    x3, 0(x0)
    halt:
        jal   x0, halt
    """
    program, labels = assemble_rv32im(source)

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000013
    dut.data_read_data.value = 0x00000000

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await Timer(2, unit="ns")
    observed_pc = int(dut.instr_addr.value)
    assert observed_pc == 0x00000000, (
        f"Expected reset instr_addr=0x00000000, observed 0x{observed_pc:08X}"
    )
    dut.rst.value = 0

    stores = []
    branch_next_pc = None
    pc = None

    for _ in range(20):
        await FallingEdge(dut.clk)
        pc = int(dut.instr_addr.value)
        instruction = program.get(pc, 0x00000013)
        dut.instr_data.value = instruction
        await Timer(1, unit="ns")

        write = int(dut.data_write.value)
        if write:
            store = (
                int(dut.data_addr.value),
                int(dut.data_width.value),
                int(dut.data_write_data.value),
            )
        else:
            store = None

        await RisingEdge(dut.clk)
        if store is not None:
            stores.append(store)
        await Timer(1, unit="ns")

        next_pc = int(dut.instr_addr.value)
        if pc == labels["compare"]:
            branch_next_pc = next_pc

        if pc == labels["halt"] and next_pc == pc:
            break
    else:
        assert False, "Expected program to reach its JAL x0, 0 halt loop"

    assert branch_next_pc == labels["compare"] + 4, (
        f"Expected unsigned BLTU to fall through to 0x{labels['compare'] + 4:08X}, "
        f"observed {branch_next_pc!r}"
    )
    assert stores == [(0x00000000, 0x2, 0x00000001)], (
        "Expected one SW of 0x00000001 to address 0x00000000 with word width; "
        f"observed {stores!r}"
    )
