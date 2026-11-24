import re

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


def assemble_rv32im(source):
    """Assemble the small legal RV32I source program used by this test."""
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

    def reg(token):
        match = re.fullmatch(r"x([0-9]|[12][0-9]|3[01])", token.strip())
        if not match:
            raise ValueError(f"Invalid register: {token}")
        return int(match.group(1))

    def check_imm(value, low, high):
        if not low <= value <= high:
            raise ValueError(f"Immediate out of range: {value}")
        return value & 0xFFF

    words = {}
    for address, line in instructions:
        parts = line.replace(",", " ").split()
        mnemonic = parts[0].lower()

        if mnemonic == "addi":
            rd, rs1 = reg(parts[1]), reg(parts[2])
            imm = check_imm(int(parts[3], 0), -2048, 2047)
            words[address] = (imm << 20) | (rs1 << 15) | (rd << 7) | 0x13

        elif mnemonic in ("lh", "sw"):
            rd_or_rs2 = reg(parts[1])
            match = re.fullmatch(r"(-?(?:0[xX][0-9a-fA-F]+|[0-9]+))\((x(?:[0-9]|[12][0-9]|3[01]))\)", parts[2])
            if not match:
                raise ValueError(f"Invalid memory operand: {parts[2]}")
            offset = int(match.group(1), 0)
            rs1 = reg(match.group(2))
            imm = check_imm(offset, -2048, 2047)

            if mnemonic == "lh":
                words[address] = (
                    (imm << 20) | (rs1 << 15) | (1 << 12)
                    | (rd_or_rs2 << 7) | 0x03
                )
            else:
                words[address] = (
                    ((imm >> 5) << 25) | (rd_or_rs2 << 20)
                    | (rs1 << 15) | (2 << 12) | ((imm & 0x1F) << 7)
                    | 0x23
                )

        elif mnemonic == "jal":
            rd = reg(parts[1])
            if parts[2] not in labels:
                raise ValueError(f"Unknown label: {parts[2]}")
            offset = labels[parts[2]] - address
            if offset & 1 or not -(1 << 20) <= offset < (1 << 20):
                raise ValueError(f"JAL offset out of range: {offset}")
            encoded = offset & 0x1FFFFF
            words[address] = (
                (((encoded >> 20) & 1) << 31)
                | (((encoded >> 1) & 0x3FF) << 21)
                | (((encoded >> 11) & 1) << 20)
                | (((encoded >> 12) & 0xFF) << 12)
                | (rd << 7) | 0x6F
            )

        else:
            raise ValueError(f"Unsupported instruction in test assembler: {mnemonic}")

    return words, labels


@cocotb.test()
async def reproduce_lh_halfword_load_case(dut):
    program, labels = assemble_rv32im(
        """
        addi x1, x0, 256
        addi x3, x0, 512
        lh   x2, 4(x1)
        sw   x2, 0(x3)
    halt:
        jal  x0, halt
        """
    )
    halt_pc = labels["halt"]

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000

    clock = Clock(dut.clk, 10, unit="ns")
    clock.start()

    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected reset instr_addr=0x00000000, observed "
        f"0x{int(dut.instr_addr.value):08X}"
    )
    assert int(dut.data_write.value) == 0, "Expected data_write=0 during reset"

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected reset instr_addr=0x00000000 after clock, observed "
        f"0x{int(dut.instr_addr.value):08X}"
    )
    dut.rst.value = 0

    # The word at the effective load address contains 0x0FF0 in its low half.
    memory_words = {0x00000104: 0xA55A0FF0}
    observed_load = False
    observed_store = False
    committed_stores = 0

    for _ in range(12):
        pc = int(dut.instr_addr.value)
        assert pc in program, f"Unexpected instruction address 0x{pc:08X}"
        dut.instr_data.value = program[pc]
        await Timer(1, unit="ns")

        data_addr = int(dut.data_addr.value)
        aligned_addr = data_addr & 0xFFFFFFFC
        dut.data_read_data.value = memory_words.get(aligned_addr, 0x00000000)
        await Timer(1, unit="ns")

        if pc == 0x00000008:
            assert data_addr == 0x00000104, (
                f"Expected LH address 0x00000104, observed 0x{data_addr:08X}"
            )
            assert int(dut.data_width.value) == 0x1, (
                f"Expected LH data_width=0x1, observed "
                f"0x{int(dut.data_width.value):X}"
            )
            assert int(dut.data_write.value) == 0, (
                "Expected data_write=0 during the LH instruction"
            )
            assert int(dut.data_read_data.value) == 0xA55A0FF0, (
                f"Expected read word 0xA55A0FF0, observed "
                f"0x{int(dut.data_read_data.value):08X}"
            )
            observed_load = True

        if pc == 0x0000000C:
            assert int(dut.data_write.value) == 1, (
                "Expected data_write=1 during the result store"
            )
            assert data_addr == 0x00000200, (
                f"Expected store address 0x00000200, observed 0x{data_addr:08X}"
            )
            assert int(dut.data_width.value) == 0x2, (
                f"Expected SW data_width=0x2, observed "
                f"0x{int(dut.data_width.value):X}"
            )
            assert int(dut.data_write_data.value) == 0x00000FF0, (
                f"Expected LH result 0x00000FF0, observed "
                f"0x{int(dut.data_write_data.value):08X}"
            )
            observed_store = True

        write = int(dut.data_write.value)
        if write:
            width = int(dut.data_width.value)
            address = int(dut.data_addr.value)
            value = int(dut.data_write_data.value)
            old_word = memory_words.get(address & 0xFFFFFFFC, 0x00000000)
            if width == 0x0:
                shift = (address & 0x3) * 8
                mask = 0xFF << shift
                new_word = (old_word & ~mask) | ((value & 0xFF) << shift)
            elif width == 0x1:
                shift = (address & 0x2) * 8
                mask = 0xFFFF << shift
                new_word = (old_word & ~mask) | ((value & 0xFFFF) << shift)
            else:
                new_word = value
            memory_words[address & 0xFFFFFFFC] = new_word & 0xFFFFFFFF
            committed_stores += 1

        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")

        if pc == halt_pc:
            next_pc = int(dut.instr_addr.value)
            assert next_pc == halt_pc, (
                f"Expected halt PC 0x{halt_pc:08X}, observed 0x{next_pc:08X}"
            )
            break

    assert observed_load, "The LH instruction at 0x00000008 was not observed"
    assert observed_store, "The result store at 0x0000000C was not observed"
    assert committed_stores == 1, (
        f"Expected one committed store, observed {committed_stores}"
    )
    assert memory_words.get(0x00000200) == 0x00000FF0, (
        f"Expected stored LH result 0x00000FF0, observed "
        f"0x{memory_words.get(0x00000200, 0):08X}"
    )
