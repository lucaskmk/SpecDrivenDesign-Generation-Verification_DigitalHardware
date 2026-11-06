import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer


def assemble_rv32i(source: str) -> int:
    """Assemble the ADDI source instruction used by this test."""
    parts = source.replace(",", " ").split()
    if len(parts) != 4 or parts[0].lower() != "addi":
        raise ValueError(f"unsupported RV32I source: {source}")

    def register(token: str) -> int:
        token = token.lower()
        if not token.startswith("x"):
            raise ValueError(f"expected a register, got {token}")
        number = int(token[1:])
        if not 0 <= number <= 31:
            raise ValueError(f"register out of range: {token}")
        return number

    rd = register(parts[1])
    rs1 = register(parts[2])
    immediate = int(parts[3], 0)
    if not -2048 <= immediate <= 2047:
        raise ValueError("ADDI immediate is out of range")

    return (
        ((immediate & 0xFFF) << 20)
        | (rs1 << 15)
        | (rd << 7)
        | 0x13
    )


@cocotb.test()
async def test_non_control_instruction_advances_fetch_address(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0
    dut.data_read_data.value = 0

    Clock(dut.clk, 10, unit="ns").start()
    await Timer(1, unit="ns")

    observed = int(dut.instr_addr.value)
    assert observed == 0x00000000, (
        f"expected reset fetch address 0x00000000, observed 0x{observed:08X}"
    )

    # Supply a legal non-control instruction at the reset fetch address.
    dut.instr_data.value = assemble_rv32i("addi x1, x0, 1")

    # Release reset away from the active edge; the fetch address remains zero.
    await FallingEdge(dut.clk)
    dut.rst.value = 0
    await Timer(1, unit="ns")

    observed = int(dut.instr_addr.value)
    assert observed == 0x00000000, (
        f"expected fetch address 0x00000000 before completion, observed 0x{observed:08X}"
    )

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")

    observed = int(dut.instr_addr.value)
    assert observed == 0x00000004, (
        f"expected sequential fetch address 0x00000004 after completion, observed 0x{observed:08X}"
    )
