import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_rv32i_op_sll_control_tuple(dut):
    program = assemble_rv32im("sll x3, x1, x2")
    dut.instr.value = program[0x00000000]
    await Timer(1, unit="ns")

    expected_scalars = {
        "reg_write": 1,
        "mem_write": 0,
        "alu_src_a_pc": 0,
        "alu_src_b_imm": 0,
        "branch_enable": 0,
        "jump": 0,
        "jalr": 0,
        "m_enable": 0,
    }
    for name, expected in expected_scalars.items():
        observed = int(getattr(dut, name).value)
        assert observed == expected, (
            f"Expected {name}={expected}, observed {observed}"
        )

    expected_vectors = {
        "alu_control": 0x2,
        "wb_select": 0x0,
    }
    for name, expected in expected_vectors.items():
        observed = int(getattr(dut, name).value)
        assert observed == expected, (
            f"Expected {name}=0x{expected:X}, observed 0x{observed:X}"
        )
