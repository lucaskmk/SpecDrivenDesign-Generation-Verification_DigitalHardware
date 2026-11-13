import cocotb
from cocotb.triggers import Timer

from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_decoder_store_word_controls(dut):
    """SW must decode to the Stores row: mem_write=1 and reg_write=0."""
    # One legal store-word with distinct non-zero rs1/rs2 and a non-zero offset.
    program = assemble_rv32im(
        "sw x7, 20(x12)\n"
        "done: jal x0, done\n"
    )
    pc = min(program.keys())
    instr_word = program[pc]

    dut.instr.value = instr_word
    await Timer(1, unit="ns")

    names = (
        "reg_write",
        "mem_write",
        "alu_src_a_pc",
        "alu_src_b_imm",
        "alu_control",
        "branch_enable",
        "jump",
        "jalr",
        "wb_select",
        "muldiv_op",
    )

    # Reject any non-binary value (U, X, Z, ...) before converting.
    observed_list = []
    for name in names:
        sig = getattr(dut, name)
        text = str(sig.value)
        assert all(ch in "01" for ch in text), (
            f"{name} has non-binary value {text} for SW decode; "
            f"expected a defined binary value"
        )
        observed_list.append(int(sig.value))
    observed = tuple(observed_list)

    # Stores row: reg_write, mem_write, alu_src_a_pc, alu_src_b_imm,
    # alu_control (ADD), branch_enable, jump, jalr, wb_select, muldiv_op
    expected = (0, 1, 0, 1, 0x0, 0, 0, 0, 0x0, 0)

    assert observed == expected, (
        f"SW decode mismatch: expected {expected} "
        f"(reg_write, mem_write, alu_src_a_pc, alu_src_b_imm, alu_control, "
        f"branch_enable, jump, jalr, wb_select, muldiv_op), observed {observed}"
    )
