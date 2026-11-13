import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_muldiv_unit(dut):
    """Smoke test: MULHU on 0x80000000 x 0xFFFFFFFF gives 0x7FFFFFFF."""
    # Drive every input to a known value (no clock or reset ports exist).
    dut.operand_a.value = 0x80000000
    dut.operand_b.value = 0xFFFFFFFF
    dut.funct3.value = 0x3  # MULHU

    # Combinational unit: wait briefly for the outputs to settle.
    await Timer(1, unit="ns")

    expected = 0x7FFFFFFF
    observed = int(dut.result.value)
    assert observed == expected, (
        f"MULHU 0x80000000 x 0xFFFFFFFF: expected 0x{expected:08X}, "
        f"observed 0x{observed:08X}"
    )
