import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_add_disables_m_writeback(dut):
    program = assemble_rv32im("add x5, x6, x7")
    dut.instr.value = program[0x00000000]
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
        "m_enable",
    )
    expected = (1, 0, 0, 0, 0x0, 0, 0, 0, 0x0, 0)
    observed = tuple(int(getattr(dut, name).value) for name in names)

    def format_controls(values):
        return ", ".join(
            f"{name}=0x{value:X}" if name in ("alu_control", "wb_select")
            else f"{name}={value}"
            for name, value in zip(names, values)
        )

    assert observed == expected, (
        f"Expected {format_controls(expected)}; "
        f"observed {format_controls(observed)}"
    )
