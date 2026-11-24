import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble the small RV32IM assembly subset used by this test."""
    labels = {}
    statements = []
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

        statements.append((pc, line))
        pc += 4

    def reg_number(token):
        token = token.strip().lower()
        if not token.startswith("x"):
            raise ValueError(f"Expected a register, got {token}")
        number = int(token[1:])
        if not 0 <= number <= 31:
            raise ValueError(f"Register out of range: {token}")
        return number

    program = {}
    for address, line in statements:
        parts = line.replace(",", " ").split()
        mnemonic = parts[0].lower()
        operands = parts[1:]

        if mnemonic == "lui":
            rd = reg_number(operands[0])
            immediate = int(operands[1], 0)
            word = ((immediate & 0xFFFFF) << 12) | (rd << 7) | 0x37

        elif mnemonic == "addi":
            rd = reg_number(operands[0])
            rs1 = reg_number(operands[1])
            immediate = int(operands[2], 0) & 0xFFF
            word = (
                (immediate << 20)
                | (rs1 << 15)
                | (rd << 7)
                | 0x13
            )

        elif mnemonic == "and":
            rd = reg_number(operands[0])
            rs1 = reg_number(operands[1])
            rs2 = reg_number(operands[2])
            word = (
                (rs2 << 20)
                | (rs1 << 15)
                | (0x7 << 12)
                | (rd << 7)
                | 0x33
            )

        elif mnemonic == "sw":
            rs2 = reg_number(operands[0])
            offset, base = operands[1].split("(", 1)
            immediate = int(offset, 0) & 0xFFF
            rs1 = reg_number(base.rstrip(")"))
            word = (
                (((immediate >> 5) & 0x7F) << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (0x2 << 12)
                | ((immediate & 0x1F) << 7)
                | 0x23
            )

        elif mnemonic == "jal":
            rd = reg_number(operands[0])
            target = labels[operands[1]]
            immediate = target - address
            encoded = immediate & 0x1FFFFF
            word = (
                (((encoded >> 20) & 0x1) << 31)
                | (((encoded >> 1) & 0x3FF) << 21)
                | (((encoded >> 11) & 0x1) << 20)
                | (((encoded >> 12) & 0xFF) << 12)
                | (rd << 7)
                | 0x6F
            )

        else:
            raise ValueError(f"Unsupported instruction in test assembly: {mnemonic}")

        program[address] = word

    return program, labels


@cocotb.test()
async def and_result_is_stored_after_adjacent_source_writes(dut):
    source = """
        lui  x1, 0x0ff01
        addi x1, x1, -16
        lui  x2, 0xf0f0f
        addi x2, x2, 240
        and  x3, x1, x2
    store: sw x3, 0(x0)
    halt:  jal x0, halt
    """
    program, labels = assemble_rv32im(source)

    expected_result = 0x00F000F0
    memory_bytes = {}

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = program[0x00000000]
    dut.data_read_data.value = 0x00000000
    await Timer(1, unit="ns")

    observed_pc = int(dut.instr_addr.value)
    assert observed_pc == 0x00000000, (
        f"Expected reset instr_addr=0x00000000, observed 0x{observed_pc:08X}"
    )

    dut.clk.value = 1
    await Timer(1, unit="ns")
    dut.clk.value = 0
    await Timer(1, unit="ns")

    observed_pc = int(dut.instr_addr.value)
    assert observed_pc == 0x00000000, (
        f"Expected reset instr_addr=0x00000000, observed 0x{observed_pc:08X}"
    )

    dut.rst.value = 0
    await Timer(1, unit="ns")

    store_count = 0
    for pc in range(0, labels["halt"], 4):
        observed_pc = int(dut.instr_addr.value)
        assert observed_pc == pc, (
            f"Expected instr_addr=0x{pc:08X}, observed 0x{observed_pc:08X}"
        )

        dut.instr_data.value = program[pc]
        await Timer(1, unit="ns")

        write_enable = int(dut.data_write.value)
        if pc == labels["store"]:
            store_count += 1
            assert write_enable == 1, (
                f"Expected data_write=0x1 for focal store, observed 0x{write_enable:X}"
            )

            observed_address = int(dut.data_addr.value)
            assert observed_address == 0x00000000, (
                f"Expected store address=0x00000000, observed 0x{observed_address:08X}"
            )

            observed_width = int(dut.data_width.value)
            assert observed_width == 0x2, (
                f"Expected data_width=0x2, observed 0x{observed_width:X}"
            )

            observed_data = int(dut.data_write_data.value)
            assert observed_data == expected_result, (
                f"Expected store data=0x{expected_result:08X}, observed 0x{observed_data:08X}"
            )

        write_address = int(dut.data_addr.value)
        write_width = int(dut.data_width.value)
        write_data = int(dut.data_write_data.value)

        dut.clk.value = 1
        await Timer(1, unit="ns")

        if write_enable:
            byte_count = 1 << write_width
            for lane in range(byte_count):
                memory_bytes[write_address + lane] = (write_data >> (8 * lane)) & 0xFF

        dut.clk.value = 0
        await Timer(1, unit="ns")

    assert store_count == 1, f"Expected exactly one focal store, observed {store_count}"

    dut.instr_data.value = program[labels["halt"]]
    await Timer(1, unit="ns")
    dut.clk.value = 1
    await Timer(1, unit="ns")

    observed_pc = int(dut.instr_addr.value)
    assert observed_pc == labels["halt"], (
        f"Expected halt PC=0x{labels['halt']:08X}, observed 0x{observed_pc:08X}"
    )

    dut.clk.value = 0
    await Timer(1, unit="ns")

    observed_word = sum(
        memory_bytes.get(lane, 0) << (8 * lane) for lane in range(4)
    )
    assert observed_word == expected_result, (
        f"Expected stored word=0x{expected_result:08X}, observed 0x{observed_word:08X}"
    )
