import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble the ADDI source used by this test into instruction words."""
    words = []

    for line in source.splitlines():
        line = line.strip()
        if not line:
            continue

        mnemonic, operands = line.split(None, 1)
        fields = [field.strip() for field in operands.split(",")]
        if mnemonic.lower() != "addi" or len(fields) != 3:
            raise ValueError(f"unsupported instruction source: {line}")

        rd = int(fields[0].lower().removeprefix("x"))
        rs1 = int(fields[1].lower().removeprefix("x"))
        immediate = int(fields[2], 0)

        if not (0 <= rd < 32 and 0 <= rs1 < 32):
            raise ValueError(f"register out of range: {line}")
        if not (-2048 <= immediate <= 2047):
            raise ValueError(f"ADDI immediate out of range: {line}")

        word = (
            ((immediate & 0xFFF) << 20)
            | (rs1 << 15)
            | (rd << 7)
            | 0x13
        )
        words.append(word)

    return words


@cocotb.test()
async def non_store_instruction_keeps_data_write_low(dut):
    instruction = assemble_rv32im("addi x5, x0, 7")[0]

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = instruction
    dut.data_read_data.value = 0x00000000

    await Timer(1, unit="ns")
    dut.rst.value = 0
    await Timer(1, unit="ns")

    observed = int(dut.data_write.value)
    assert observed == 0, f"expected data_write 0, observed {observed}"
