import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_unlisted_fence_opcode_uses_inactive_defaults(dut):
    # FENCE IORW, IORW has opcode 0x0F and funct3 0x0.
    opcode = 0x0F
    funct3 = 0x0

    assert opcode == 0x0F, f"Expected FENCE opcode 0x0F, observed 0x{opcode:02X}"

    dut.opcode.value = opcode
    dut.funct3.value = funct3
    await Timer(1, unit="ns")

    expected = {
        "rd_write": 0x0,
        "mem_write": 0x0,
        "load_enable": 0x0,
        "data_width": 0x2,
        "load_signed": 0x0,
        "alu_a_pc": 0x0,
        "alu_b_imm": 0x0,
        "wb_sel": 0x0,
        "branch_enable": 0x0,
        "jal": 0x0,
        "jalr": 0x0,
    }

    for name, value in expected.items():
        observed = int(getattr(dut, name).value)
        assert observed == value, (
            f"Expected {name}=0x{value:X}, observed 0x{observed:X}"
        )
