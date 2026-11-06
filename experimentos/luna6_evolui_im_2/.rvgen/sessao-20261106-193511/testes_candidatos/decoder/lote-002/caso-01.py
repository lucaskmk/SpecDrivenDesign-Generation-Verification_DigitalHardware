import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_op_xor_decode(dut):
    program = assemble_rv32im("xor x3, x1, x2\n")
    dut.instr.value = program[0]
    await Timer(1, unit="ns")

    expected = {
        "reg_write": 0x1,
        "mem_write": 0x0,
        "alu_src_a_pc": 0x0,
        "alu_src_b_imm": 0x0,
        "alu_control": 0x5,
        "branch_enable": 0x0,
        "jump": 0x0,
        "jalr": 0x0,
        "wb_select": 0x0,
    }

    for port, value in expected.items():
        observed = int(getattr(dut, port).value)
        assert observed == value, (
            f"{port}: expected 0x{value:X}, observed 0x{observed:X}"
        )
