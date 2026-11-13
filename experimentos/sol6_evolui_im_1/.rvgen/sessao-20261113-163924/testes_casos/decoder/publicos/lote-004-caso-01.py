import cocotb
from cocotb.triggers import Timer

from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_sltu_selects_unsigned_less_than(dut):
    program = assemble_rv32im("sltu x5, x6, x7")
    dut.instr.value = program[0x00000000]
    await Timer(1, unit="ns")

    expected = {
        "reg_write": 1,
        "mem_write": 0,
        "alu_src_a_pc": 0,
        "alu_src_b_imm": 0,
        "alu_control": 0x4,
        "branch_enable": 0,
        "jump": 0,
        "jalr": 0,
        "wb_select": 0x0,
        "m_enable": 0,
    }

    for name, value in expected.items():
        observed = int(getattr(dut, name).value)
        if name in ("alu_control", "wb_select"):
            assert observed == value, (
                f"{name}: expected 0x{value:X}, observed 0x{observed:X}"
            )
        else:
            assert observed == value, (
                f"{name}: expected {value}, observed {observed}"
            )
