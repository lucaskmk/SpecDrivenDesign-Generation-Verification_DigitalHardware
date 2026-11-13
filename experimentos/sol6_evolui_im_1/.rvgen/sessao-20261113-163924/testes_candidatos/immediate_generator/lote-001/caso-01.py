import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_negative_store_immediate_sign_extension(dut):
    # sw x7, -1371(x9): the 12-bit displacement is 0xAA5.
    # Its lower 11 bits are 0x2A5.
    instruction = 0xAA74A2A3
    dut.instr.value = instruction & 0xFFFFFFFF
    await Timer(1, unit="ns")

    observed = int(dut.imm_s.value)
    lower_bits = observed & 0x7FF
    upper_bits = observed & 0xFFFFF800

    assert lower_bits == 0x2A5, (
        f"imm_s displacement bits: expected 0x2A5, observed 0x{lower_bits:03X}"
    )
    assert upper_bits == 0xFFFFF800, (
        f"imm_s sign-filled bits: expected 0xFFFFF800, "
        f"observed 0x{upper_bits:08X}"
    )
    assert observed == 0xFFFFFAA5, (
        f"imm_s: expected 0xFFFFFAA5, observed 0x{observed:08X}"
    )
