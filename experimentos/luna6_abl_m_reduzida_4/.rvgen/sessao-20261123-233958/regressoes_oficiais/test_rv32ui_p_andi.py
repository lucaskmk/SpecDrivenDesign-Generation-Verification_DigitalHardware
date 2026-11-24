import re

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


def assemble_rv32im(source):
    """Assemble the small RV32I source program used by this test."""
    labels = {}
    instructions = []
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

    def register(name):
        match = re.fullmatch(r"x([0-9]|[12][0-9]|3[01])", name)
        if not match:
            raise ValueError(f"Invalid register: {name}")
        return int(match.group(1))

    words = []
    for inst_pc, line in instructions:
        fields = re.split(r"[\s,]+", line)
        mnemonic = fields[0].lower()

        if mnemonic == "lui":
            rd = register(fields[1])
            imm = int(fields[2], 0)
            if not 0 <= imm <= 0xFFFFF:
                raise ValueError("LUI immediate is out of range")
            word = (imm << 12) | (rd << 7) | 0x37

        elif mnemonic in ("addi", "andi"):
            rd = register(fields[1])
            rs1 = register(fields[2])
            imm = int(fields[3], 0)
            if not -2048 <= imm <= 2047:
                raise ValueError(f"{mnemonic} immediate is out of range")
            funct3 = 0 if mnemonic == "addi" else 7
            word = (
                ((imm & 0xFFF) << 20)
                | (rs1 << 15)
                | (funct3 << 12)
                | (rd << 7)
                | 0x13
            )

        elif mnemonic == "sw":
            rs2 = register(fields[1])
            match = re.fullmatch(r"(-?(?:0[xX][0-9a-fA-F]+|[0-9]+))\((x[0-9]+)\)", fields[2])
            if not match:
                raise ValueError(f"Invalid store address: {fields[2]}")
            imm = int(match.group(1), 0)
            rs1 = register(match.group(2))
            if not -2048 <= imm <= 2047:
                raise ValueError("Store immediate is out of range")
            imm &= 0xFFF
            word = (
                (((imm >> 5) & 0x7F) << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (2 << 12)
                | ((imm & 0x1F) << 7)
                | 0x23
            )

        elif mnemonic == "jal":
            rd = register(fields[1])
            if fields[2] not in labels:
                raise ValueError(f"Unknown JAL label: {fields[2]}")
            offset = labels[fields[2]] - inst_pc
            if offset & 1 or not -(1 << 20) <= offset < (1 << 20):
                raise ValueError("JAL offset is out of range")
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

        words.append(word)

    return words


@cocotb.test()
async def andi_write_to_x0_is_discarded(dut):
    source = """
        lui  x1, 0x00ff0
        addi x1, x1, 255
        andi x0, x1, 0x70f
        sw   x0, 0(x0)
    halt: jal  x0, halt
    """
    program = assemble_rv32im(source)

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0
    dut.data_read_data.value = 0

    Clock(dut.clk, 10, unit="ns").start()
    await Timer(2, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected reset PC 0x00000000, observed 0x{int(dut.instr_addr.value):08X}"
    )
    dut.rst.value = 0
    await Timer(1, unit="ns")

    committed_stores = []
    store_pc = 12

    for index in range(4):
        expected_pc = index * 4
        observed_pc = int(dut.instr_addr.value)
        assert observed_pc == expected_pc, (
            f"Expected instruction address 0x{expected_pc:08X}, "
            f"observed 0x{observed_pc:08X}"
        )

        dut.instr_data.value = program[index]
        await Timer(1, unit="ns")

        if expected_pc == store_pc:
            observed_write = int(dut.data_write.value)
            observed_addr = int(dut.data_addr.value)
            observed_width = int(dut.data_width.value)
            observed_data = int(dut.data_write_data.value)

            assert observed_write == 1, (
                f"Expected data_write=1 for the witness store, observed {observed_write}"
            )
            assert observed_addr == 0x00000000, (
                f"Expected store address 0x00000000, observed 0x{observed_addr:08X}"
            )
            assert observed_width == 0x2, (
                f"Expected data_width=0x2, observed 0x{observed_width:X}"
            )
            assert observed_data == 0x00000000, (
                f"Expected x0 store data 0x00000000, observed 0x{observed_data:08X}"
            )

            await RisingEdge(dut.clk)
            committed_stores.append(
                (observed_addr, observed_width, observed_data)
            )
            await Timer(1, unit="ns")
            break

        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")

    assert committed_stores == [(0x00000000, 0x2, 0x00000000)], (
        "Expected one committed word store at 0x00000000 with data 0x00000000, "
        f"observed {committed_stores}"
    )
