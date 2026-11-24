import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_s_immediate_split_field_reconstruction(dut):
    # Encode sw x5, 676(x6). The S-type immediate is split between
    # instruction bits 31:25 and 11:7.
    immediate = 676
    instruction = (
        (((immediate >> 5) & 0x7F) << 25)
        | (5 << 20)
        | (6 << 15)
        | (2 << 12)
        | ((immediate & 0x1F) << 7)
        | 0x23
    )

    dut.instr.value = instruction
    await Timer(1, unit="ns")

    observed = int(dut.imm_s.value)
    expected = 0x000002A4
    assert observed == expected, (
        f"imm_s expected 0x{expected:08X}, observed 0x{observed:08X}"
    )
