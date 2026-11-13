import cocotb
from cocotb.triggers import Timer

from rvgen.riscv_asm import assemble_rv32im


def _binary_int(signal, name):
    """Return the integer value of a signal, requiring a defined binary value."""
    text = str(signal.value)
    assert all(ch in "01" for ch in text), (
        f"{name} must be a defined binary value (no U/X/Z), observed {text}"
    )
    return int(signal.value)


@cocotb.test()
async def test_decoder_branch_blt_controls(dut):
    """BLT with distinct non-zero rs1/rs2 and a forward offset decodes to the Branches row."""
    program = assemble_rv32im(
        "blt x5, x6, target\n"
        "addi x0, x0, 0\n"
        "target: jal x0, target\n"
    )

    # The BLT is the first instruction, at the lowest PC.
    blt_pc = min(program.keys())
    instr_word = program[blt_pc]

    dut.instr.value = instr_word
    await Timer(1, unit="ns")

    observed = {
        "branch_enable": _binary_int(dut.branch_enable, "branch_enable"),
        "alu_control": _binary_int(dut.alu_control, "alu_control"),
        "reg_write": _binary_int(dut.reg_write, "reg_write"),
        "mem_write": _binary_int(dut.mem_write, "mem_write"),
        "alu_src_a_pc": _binary_int(dut.alu_src_a_pc, "alu_src_a_pc"),
        "alu_src_b_imm": _binary_int(dut.alu_src_b_imm, "alu_src_b_imm"),
        "jump": _binary_int(dut.jump, "jump"),
        "jalr": _binary_int(dut.jalr, "jalr"),
        "wb_select": _binary_int(dut.wb_select, "wb_select"),
        "muldiv_op": _binary_int(dut.muldiv_op, "muldiv_op"),
    }

    expected = {
        "branch_enable": 1,
        "alu_control": 0x2,  # BLT branch-condition selector
        "reg_write": 0,
        "mem_write": 0,
        "alu_src_a_pc": 0,
        "alu_src_b_imm": 0,
        "jump": 0,
        "jalr": 0,
        "wb_select": 0x0,
        "muldiv_op": 0,
    }

    for name, exp in expected.items():
        assert observed[name] == exp, (
            f"BLT decode mismatch on {name}: expected {exp:#x}, "
            f"observed {observed[name]:#x}; full observed tuple {observed}"
        )
