import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_divider_smoke(dut):
    """Smoke test: signed quotient of -7 / 2 truncates toward zero."""
    # Drive every input to a known value (combinational entity: no clk, no rst)
    dut.operand_a.value = 0xFFFFFFF9  # -7
    dut.operand_b.value = 0x00000002  # 2
    dut.is_signed.value = 1
    dut.want_rem.value = 0

    await Timer(1, unit="ns")

    expected = 0xFFFFFFFD  # -3
    observed = int(dut.result.value)
    assert observed == expected, (
        f"DIV 0xFFFFFFF9 / 0x00000002: expected 0x{expected:08X}, "
        f"observed 0x{observed:08X}"
    )
