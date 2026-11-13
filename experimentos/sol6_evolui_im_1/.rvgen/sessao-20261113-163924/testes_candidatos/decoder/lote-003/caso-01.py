import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_slt_selects_signed_less_than_control(dut):
    program = assemble_rv32im("slt x3, x1, x2")
    dut.instr.value = program[0x00000000]
    await Timer(1, unit="ns")

    expected = {
        "reg_write": 1,
        "mem_write": 0,
        "alu_src_a_pc": 0,
        "alu_src_b_imm": 0,
        "alu_control": 0x3,
        "branch_enable": 0,
        "jump": 0,
        "jalr": 0,
        "wb_select": 0x0,
        "m_enable": 0,
    }

    vector_ports = {"alu_control", "wb_select"}
    for name, value in expected.items():
        observed = int(getattr(dut, name).value)
        if name in vector_ports:
            assert observed == value, (
                f"Expected {name}=0x{value:X}, observed 0x{observed:X}"
            )
        else:
            assert observed == value, (
                f"Expected {name}={value}, observed {observed}"
            )
