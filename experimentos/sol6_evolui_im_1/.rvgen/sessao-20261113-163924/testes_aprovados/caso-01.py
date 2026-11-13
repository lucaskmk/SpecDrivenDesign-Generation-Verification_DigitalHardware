import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_branch_split_field_reassembly(dut):
    # The branch is at 0x00000000; the label is at 0x00000ABA.
    displacement = 0x00000ABA

    # Encode beq x3, x7, target directly, without an external assembler.
    instruction = (
        (((displacement >> 12) & 0x1) << 31)
        | (((displacement >> 5) & 0x3F) << 25)
        | (0x7 << 20)
        | (0x3 << 15)
        | (((displacement >> 1) & 0xF) << 8)
        | (((displacement >> 11) & 0x1) << 7)
        | 0x63
    ) & 0xFFFFFFFF

    dut.instr.value = instruction
    await Timer(1, unit="ns")

    observed = int(dut.imm_b.value)
    assert observed == displacement, (
        f"imm_b: expected 0x{displacement:08X}, observed 0x{observed:08X}"
    )
