import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def auipc_selects_pc_as_alu_operand_a(dut):
    # AUIPC x7, 0x12345
    instruction = 0x12345397

    dut.instr.value = instruction
    await Timer(1, unit="ns")

    assert int(dut.alu_src_a_pc.value) == 1, (
        f"Expected alu_src_a_pc=1 for AUIPC, observed {dut.alu_src_a_pc.value}"
    )
