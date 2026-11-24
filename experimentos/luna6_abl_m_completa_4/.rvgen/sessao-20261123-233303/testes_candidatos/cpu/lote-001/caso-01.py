import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble the ADDI source instruction used by this test."""
    words = []
    for line in source.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue

        mnemonic, operands = line.split(None, 1)
        if mnemonic.lower() != "addi":
            raise ValueError(f"Unsupported instruction: {mnemonic}")

        rd_text, rs1_text, imm_text = (
            operand.strip() for operand in operands.split(",")
        )
        rd = int(rd_text.lower().removeprefix("x"))
        rs1 = int(rs1_text.lower().removeprefix("x"))
        immediate = int(imm_text, 0)

        if not 0 <= rd < 32 or not 0 <= rs1 < 32:
            raise ValueError("Register index is outside the RV32 register file")
        if not -2048 <= immediate <= 2047:
            raise ValueError("ADDI immediate is outside the signed 12-bit range")

        # Encode the parsed legal ADDI instruction fields.
        word = (
            ((immediate & 0xFFF) << 20)
            | (rs1 << 15)
            | (rd << 7)
            | 0x13
        )
        words.append(word)

    return words


@cocotb.test()
async def sequential_fetch_advances_by_four(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000
    await Timer(1, unit="ns")

    source = "addi x0, x0, 0"
    nop = assemble_rv32im(source)[0]

    dut.rst.value = 0
    await Timer(1, unit="ns")

    first_fetch = int(dut.instr_addr.value)
    program = {
        first_fetch: nop,
        (first_fetch + 4) & 0xFFFFFFFF: nop,
        (first_fetch + 8) & 0xFFFFFFFF: nop,
    }

    dut.instr_data.value = program[first_fetch]
    await Timer(1, unit="ns")

    dut.clk.value = 1
    await Timer(1, unit="ns")
    second_fetch = int(dut.instr_addr.value)
    expected_second = (first_fetch + 4) & 0xFFFFFFFF
    assert second_fetch == expected_second, (
        f"Expected next sequential fetch at 0x{expected_second:08X}, "
        f"observed 0x{second_fetch:08X}"
    )

    dut.clk.value = 0
    await Timer(1, unit="ns")
    dut.instr_data.value = program[second_fetch]
    await Timer(1, unit="ns")

    dut.clk.value = 1
    await Timer(1, unit="ns")
    third_fetch = int(dut.instr_addr.value)
    expected_third = (second_fetch + 4) & 0xFFFFFFFF
    assert third_fetch == expected_third, (
        f"Expected next sequential fetch at 0x{expected_third:08X}, "
        f"observed 0x{third_fetch:08X}"
    )
