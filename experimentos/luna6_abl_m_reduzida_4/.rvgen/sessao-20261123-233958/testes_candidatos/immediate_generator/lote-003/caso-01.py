import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_s_immediate_source_field_routing(dut):
    # Encode LUI x11, 0x2D3A5 directly. The immediate and destination provide
    # distinct, nonzero S-immediate source fields, while keeping instr[31] clear.
    instr = ((0x2D3A5 << 12) | (11 << 7) | 0x37) & 0xFFFFFFFF

    dut.instr.value = instr
    await Timer(1, unit="ns")

    expected = ((((instr >> 25) & 0x7F) << 5) | ((instr >> 7) & 0x1F))
    observed = int(dut.imm_s.value)
    assert observed == expected, (
        f"imm_s: expected 0x{expected:08X}, observed 0x{observed:08X}"
    )
