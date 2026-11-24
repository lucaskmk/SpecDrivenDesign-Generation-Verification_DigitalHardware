import cocotb
from cocotb.triggers import Timer


def encode_beq(rs1, rs2, offset):
    """Encode a BEQ instruction with the given byte offset."""
    return (
        (((offset >> 12) & 0x1) << 31)
        | (((offset >> 5) & 0x3F) << 25)
        | ((rs2 & 0x1F) << 20)
        | ((rs1 & 0x1F) << 15)
        | (((offset >> 1) & 0xF) << 8)
        | (((offset >> 11) & 0x1) << 7)
        | 0x63
    )


@cocotb.test()
async def positive_b_immediate_from_branch_label(dut):
    # The target is 68 bytes ahead: the branch plus 16 ADDI instructions.
    # This sets source bits in both split B-immediate instruction fields while
    # keeping the displacement positive.
    branch_offset = 4 * (1 + 16)
    branch_instruction = encode_beq(rs1=1, rs2=2, offset=branch_offset)
    program = [branch_instruction] + [0x00000013] * 17
    assert program, "Expected assembled branch program to contain an instruction"

    dut.instr.value = program[0] & 0xFFFFFFFF
    await Timer(1, unit="ns")

    observed = int(dut.imm_b.value)
    assert observed == 0x00000044, (
        f"Expected imm_b=0x00000044, observed 0x{observed:08X}"
    )
