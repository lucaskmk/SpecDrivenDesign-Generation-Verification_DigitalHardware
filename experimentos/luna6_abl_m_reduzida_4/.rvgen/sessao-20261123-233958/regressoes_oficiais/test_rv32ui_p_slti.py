import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble the small RV32IM source subset used by this test."""
    words = []

    def reg(token):
        token = token.strip().lower()
        if not token.startswith("x"):
            raise ValueError(f"Expected an integer register, got {token}")
        index = int(token[1:])
        if not 0 <= index <= 31:
            raise ValueError(f"Register index out of range: {token}")
        return index

    def encode_i(opcode, funct3, rd, rs1, immediate):
        imm = immediate & 0xFFF
        return (
            (imm << 20)
            | (rs1 << 15)
            | (funct3 << 12)
            | (rd << 7)
            | opcode
        )

    for raw_line in source.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue

        operation, operands_text = line.split(None, 1)
        operands = [part.strip() for part in operands_text.split(",")]

        if operation == "li":
            rd = reg(operands[0])
            value = int(operands[1], 0)
            value &= 0xFFFFFFFF
            signed_value = value if value < 0x80000000 else value - 0x100000000
            upper = (signed_value + 0x800) >> 12
            lower = signed_value - (upper << 12)

            if upper:
                words.append(
                    ((upper & 0xFFFFF) << 12) | (rd << 7) | 0x37
                )
                words.append(encode_i(0x13, 0x0, rd, rd, lower))
            else:
                words.append(encode_i(0x13, 0x0, rd, 0, lower))

        elif operation in ("addi", "slti"):
            rd = reg(operands[0])
            rs1 = reg(operands[1])
            immediate = int(operands[2], 0)
            funct3 = 0x0 if operation == "addi" else 0x2
            words.append(encode_i(0x13, funct3, rd, rs1, immediate))

        elif operation == "sw":
            rs2 = reg(operands[0])
            offset_text, base_text = operands[1].split("(", 1)
            immediate = int(offset_text.strip(), 0)
            rs1 = reg(base_text.rstrip(")"))
            imm = immediate & 0xFFF
            words.append(
                (((imm >> 5) & 0x7F) << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (0x2 << 12)
                | ((imm & 0x1F) << 7)
                | 0x23
            )

        else:
            raise ValueError(f"Unsupported assembly operation: {operation}")

    return words


@cocotb.test()
async def slti_zero_destination_remains_zero(dut):
    program = assemble_rv32im(
        """
        li x1, 0x00ff00ff
        addi x2, x0, 0x100
        slti x0, x1, -1
        sw x0, 0(x2)
        """
    )
    memory_words = {}

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000013
    dut.data_read_data.value = 0x00000000
    await Timer(1, unit="ns")
    observed_pc = int(dut.instr_addr.value)
    assert observed_pc == 0x00000000, (
        f"Expected reset instr_addr=0x00000000, observed 0x{observed_pc:08X}"
    )

    dut.rst.value = 0
    await Timer(1, unit="ns")

    for index, instruction in enumerate(program):
        expected_pc = index * 4
        observed_pc = int(dut.instr_addr.value)
        assert observed_pc == expected_pc, (
            f"Expected instr_addr=0x{expected_pc:08X}, observed 0x{observed_pc:08X}"
        )

        dut.instr_data.value = instruction
        await Timer(1, unit="ns")

        if index == len(program) - 1:
            observed_write = int(dut.data_write.value)
            observed_addr = int(dut.data_addr.value)
            observed_width = int(dut.data_width.value)
            observed_data = int(dut.data_write_data.value)

            assert observed_write == 1, (
                f"Expected data_write=1, observed {observed_write}"
            )
            assert observed_addr == 0x00000100, (
                f"Expected data_addr=0x00000100, observed 0x{observed_addr:08X}"
            )
            assert observed_width == 0x2, (
                f"Expected data_width=0x2, observed 0x{observed_width:X}"
            )
            assert observed_data == 0x00000000, (
                f"Expected data_write_data=0x00000000, observed 0x{observed_data:08X}"
            )

        dut.clk.value = 1
        await Timer(1, unit="ns")

        if int(dut.data_write.value) == 1:
            address = int(dut.data_addr.value)
            width = int(dut.data_width.value)
            data = int(dut.data_write_data.value)
            if width == 0x2:
                memory_words[address & 0xFFFFFFFC] = data

        expected_next_pc = (expected_pc + 4) & 0xFFFFFFFF
        observed_next_pc = int(dut.instr_addr.value)
        assert observed_next_pc == expected_next_pc, (
            f"Expected instr_addr=0x{expected_next_pc:08X}, "
            f"observed 0x{observed_next_pc:08X}"
        )

        dut.clk.value = 0
        await Timer(1, unit="ns")

    observed_memory = memory_words.get(0x00000100, None)
    assert observed_memory == 0x00000000, (
        f"Expected word at 0x00000100 to be 0x00000000, "
        f"observed {observed_memory!r}"
    )
