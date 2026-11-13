import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


def _read_binary(signal, name):
    """Read a port value and reject any non-binary content."""
    text = str(signal.value)
    assert all(ch in "01" for ch in text), (
        f"{name} has a non-binary value: expected only 0/1 bits, observed {text}"
    )
    return int(signal.value)


@cocotb.test()
async def test_decoder_auipc_pc_operand(dut):
    """AUIPC with non-zero rd and upper immediate selects PC as ALU operand A."""
    # Legal AUIPC source: rd=x11, non-zero upper immediate 0x2A5C3.
    program = assemble_rv32im("auipc x11, 0x2A5C3")
    assert len(program) == 1, (
        f"expected exactly 1 assembled instruction, observed {len(program)}"
    )
    word = program[min(program.keys())]

    # Drive the instruction and let the combinational outputs settle.
    dut.instr.value = word
    await Timer(1, unit="ns")

    observed = (
        _read_binary(dut.reg_write, "reg_write"),
        _read_binary(dut.mem_write, "mem_write"),
        _read_binary(dut.alu_src_a_pc, "alu_src_a_pc"),
        _read_binary(dut.alu_src_b_imm, "alu_src_b_imm"),
        _read_binary(dut.alu_control, "alu_control"),
        _read_binary(dut.branch_enable, "branch_enable"),
        _read_binary(dut.jump, "jump"),
        _read_binary(dut.jalr, "jalr"),
        _read_binary(dut.wb_select, "wb_select"),
        _read_binary(dut.muldiv_op, "muldiv_op"),
    )

    # (reg_write, mem_write, alu_src_a_pc, alu_src_b_imm, alu_control,
    #  branch_enable, jump, jalr, wb_select, muldiv_op)
    expected = (1, 0, 1, 1, 0x0, 0, 0, 0, 0x0, 0)

    assert observed == expected, (
        f"AUIPC decode mismatch: expected {expected} "
        f"(reg_write, mem_write, alu_src_a_pc, alu_src_b_imm, alu_control, "
        f"branch_enable, jump, jalr, wb_select, muldiv_op), observed {observed}"
    )

    # Focal assertion: PC selected as operand A, without jump or branch.
    assert observed[2] == 1 and observed[6] == 0 and observed[5] == 0, (
        f"AUIPC must have alu_src_a_pc=1, jump=0, branch_enable=0: "
        f"expected (1, 0, 0), observed ({observed[2]}, {observed[6]}, {observed[5]})"
    )
