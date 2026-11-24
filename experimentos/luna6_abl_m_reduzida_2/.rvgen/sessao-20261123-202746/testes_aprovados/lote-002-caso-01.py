import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source: str) -> int:
    """Assemble the ADDI source used by this control-unit test."""
    parts = source.replace(",", " ").split()
    if len(parts) != 4 or parts[0].lower() != "addi":
        raise ValueError(f"Unsupported instruction source: {source}")

    def register(token: str) -> int:
        token = token.lower()
        if not token.startswith("x"):
            raise ValueError(f"Expected an integer register, got {token}")
        number = int(token[1:])
        if not 0 <= number < 32:
            raise ValueError(f"Register is out of range: {token}")
        return number

    rd = register(parts[1])
    rs1 = register(parts[2])
    immediate = int(parts[3], 0)
    if not -(1 << 11) <= immediate < (1 << 11):
        raise ValueError("ADDI immediate is out of range")

    return (
        ((immediate & 0xFFF) << 20)
        | (rs1 << 15)
        | (rd << 7)
        | 0x13
    )


@cocotb.test()
async def test_addi_opcode_class_controls(dut):
    instruction = assemble_rv32im("addi x1, x0, 7")
    dut.opcode.value = instruction & 0x7F
    dut.funct3.value = (instruction >> 12) & 0x7

    await Timer(1, unit="ns")

    expected = {
        "rd_write": 1,
        "mem_write": 0,
        "load_enable": 0,
        "data_width": 0x2,
        "load_signed": 0,
        "alu_a_pc": 0,
        "alu_b_imm": 1,
        "wb_sel": 0x0,
        "branch_enable": 0,
        "jal": 0,
        "jalr": 0,
    }

    for port_name, expected_value in expected.items():
        observed = int(getattr(dut, port_name).value)
        assert observed == expected_value, (
            f"Expected {port_name}=0x{expected_value:X}, "
            f"observed 0x{observed:X}"
        )
