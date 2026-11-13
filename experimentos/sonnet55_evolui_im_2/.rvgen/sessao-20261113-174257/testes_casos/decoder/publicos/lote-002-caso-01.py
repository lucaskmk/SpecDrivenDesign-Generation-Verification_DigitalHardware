import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_decoder_word_load_writeback_select(dut):
    """LW with non-zero rd/rs1/offset must decode to the Loads row (wb_select=0x1)."""
    # Legal source only; the instruction word comes from the assembler.
    program = assemble_rv32im("lw x13, 44(x21)")
    assert len(program) == 1, f"expected one assembled instruction, observed {len(program)}"
    word = program[0]

    dut.instr.value = word
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

    observed = []
    for name in names:
        sig = getattr(dut, name)
        text = str(sig.value)
        assert all(c in "01" for c in text), (
            f"output {name} is not a defined binary value for instr 0x{word:08X}: observed {text}"
        )
        observed.append(int(sig.value))
    observed = tuple(observed)

    # Loads row: reg_write, mem_write, alu_src_a_pc, alu_src_b_imm, alu_control (ADD),
    # branch_enable, jump, jalr, wb_select (data-memory read), muldiv_op
    expected = (1, 0, 0, 1, 0x0, 0, 0, 0, 0x1, 0)

    assert observed[8] == 0x1, (
        f"wb_select mismatch for LW: expected 0x1, observed 0x{observed[8]:X}"
    )
    assert observed == expected, (
        f"LW decode mismatch: expected {expected} "
        f"(reg_write, mem_write, alu_src_a_pc, alu_src_b_imm, alu_control, "
        f"branch_enable, jump, jalr, wb_select, muldiv_op), observed {observed}"
    )
