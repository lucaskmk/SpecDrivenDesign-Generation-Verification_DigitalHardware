import cocotb
from cocotb.triggers import Timer


def assemble_rv32i(source: str) -> int:
    """Assemble the legal ADDI instruction used by this standalone test."""
    parts = source.replace(",", " ").split()
    if len(parts) != 4 or parts[0].lower() != "addi":
        raise ValueError(f"unsupported instruction source: {source}")

    rd = int(parts[1].lower().removeprefix("x"))
    rs1 = int(parts[2].lower().removeprefix("x"))
    immediate = int(parts[3], 0)
    if not (0 <= rd < 32 and 0 <= rs1 < 32 and -2048 <= immediate <= 2047):
        raise ValueError(f"invalid ADDI operands: {source}")

    return (
        ((immediate & 0xFFF) << 20)
        | (rs1 << 15)
        | (rd << 7)
        | 0x13
    )


@cocotb.test()
async def test_unsupported_instruction_output_defaults(dut):
    dut.instr.value = assemble_rv32i("addi x1, x2, 1")
    dut.effective_address.value = 0x12345679
    dut.store_data_in.value = 0xA1B2C3D4
    dut.data_read_data.value = 0xD3A5C67E

    await Timer(1, unit="ns")

    assert int(dut.data_write.value) == 0, (
        f"expected data_write 0, observed {int(dut.data_write.value)}"
    )
    assert int(dut.data_write_data.value) == 0x00000000, (
        f"expected data_write_data 0x00000000, "
        f"observed 0x{int(dut.data_write_data.value):08X}"
    )
    assert int(dut.load_result.value) == 0x00000000, (
        f"expected load_result 0x00000000, "
        f"observed 0x{int(dut.load_result.value):08X}"
    )
    assert int(dut.data_width.value) == 0x2, (
        f"expected data_width 0x2, observed 0x{int(dut.data_width.value):X}"
    )
