import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

from rvgen import assemble_rv32im


@cocotb.test()
async def signed_lb_value_is_stored_by_following_sb(dut):
    program = assemble_rv32im(
        """
        lb x3, 256(x0)
        sb x3, 256(x0)
        """
    )
    assert len(program) == 2, f"Expected 2 assembled instructions, observed {len(program)}"

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = int(program[0])
    dut.data_read_data.value = 0x000000DD

    clock = Clock(dut.clk, 10, unit="ns")
    clock.start()

    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected reset instr_addr=0x00000000, observed 0x{int(dut.instr_addr.value):08X}"
    )
    dut.rst.value = 0

    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected instr_addr=0x00000000 after reset release, observed "
        f"0x{int(dut.instr_addr.value):08X}"
    )
    assert int(dut.data_addr.value) == 0x00000100, (
        f"Expected LB address 0x00000100, observed 0x{int(dut.data_addr.value):08X}"
    )

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000004, (
        f"Expected instr_addr=0x00000004 after LB, observed "
        f"0x{int(dut.instr_addr.value):08X}"
    )

    dut.instr_data.value = int(program[1])
    await Timer(1, unit="ns")

    assert int(dut.data_write.value) == 1, (
        f"Expected data_write=1 for SB, observed {int(dut.data_write.value)}"
    )
    assert int(dut.data_addr.value) == 0x00000100, (
        f"Expected SB address 0x00000100, observed 0x{int(dut.data_addr.value):08X}"
    )
    assert int(dut.data_width.value) == 0x0, (
        f"Expected SB data_width=0x0, observed 0x{int(dut.data_width.value):X}"
    )
    assert int(dut.data_write_data.value) == 0xFFFFFFDD, (
        f"Expected sign-extended LB value 0xFFFFFFDD on the SB bus, "
        f"observed 0x{int(dut.data_write_data.value):08X}"
    )

    memory = {0x00000100: 0xDD}
    await RisingEdge(dut.clk)
    if int(dut.data_write.value) == 1:
        memory[0x00000100] = int(dut.data_write_data.value) & 0xFF
    await Timer(1, unit="ns")

    assert memory[0x00000100] == 0xDD, (
        f"Expected byte at 0x00000100 to be 0xDD after SB, "
        f"observed 0x{memory[0x00000100]:02X}"
    )
