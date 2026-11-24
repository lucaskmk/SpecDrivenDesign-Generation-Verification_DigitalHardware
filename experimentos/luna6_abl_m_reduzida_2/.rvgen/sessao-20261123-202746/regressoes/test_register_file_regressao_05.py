import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer


@cocotb.test()
async def register_file_regressao_05(dut):
    # Drive every input to a known value before checking asynchronous outputs.
    dut.clk.value = 0
    dut.rst.value = 0
    dut.rs1_addr.value = 0
    dut.rs2_addr.value = 0
    dut.rd_addr.value = 0
    dut.rd_data.value = 0x00000000
    dut.rd_write.value = 0

    clock = Clock(dut.clk, 10, unit="ns")
    clock.start()

    async def check_reads(addr1, expected1, addr2, expected2, context):
        dut.rs1_addr.value = addr1
        dut.rs2_addr.value = addr2
        await Timer(1, unit="ns")
        observed1 = int(dut.rs1_data.value)
        observed2 = int(dut.rs2_data.value)
        assert observed1 == expected1, (
            f"{context}: rs1_data expected 0x{expected1:08X}, "
            f"observed 0x{observed1:08X}"
        )
        assert observed2 == expected2, (
            f"{context}: rs2_data expected 0x{expected2:08X}, "
            f"observed 0x{observed2:08X}"
        )

    async def write_register(address, value):
        await FallingEdge(dut.clk)
        dut.rd_addr.value = address
        dut.rd_data.value = value
        dut.rd_write.value = 1
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        dut.rd_write.value = 0

    # Failure-evidence case: asynchronous reset clears reads without waiting
    # for a clock edge. Include x0 and representative nonzero read addresses.
    dut.rst.value = 1
    await Timer(1, unit="ns")
    await check_reads(0, 0x00000000, 1, 0x00000000, "asynchronous reset")
    await check_reads(7, 0x00000000, 31, 0x00000000, "asynchronous reset")

    # Writes attempted while reset is asserted must not survive reset.
    dut.rd_addr.value = 7
    dut.rd_data.value = 0xAAAAAAAA
    dut.rd_write.value = 1
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    await check_reads(7, 0x00000000, 31, 0x00000000, "write during reset")
    dut.rst.value = 0
    dut.rd_write.value = 0
    await Timer(1, unit="ns")
    await check_reads(7, 0x00000000, 31, 0x00000000, "after reset deassertion")

    # x0 ignores writes both outside reset and during reset.
    await write_register(0, 0xFFFFFFFF)
    await check_reads(0, 0x00000000, 0, 0x00000000, "write to x0")
    dut.rst.value = 1
    await Timer(1, unit="ns")
    dut.rd_addr.value = 0
    dut.rd_data.value = 0x55555555
    dut.rd_write.value = 1
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    dut.rst.value = 0
    dut.rd_write.value = 0
    await Timer(1, unit="ns")
    await check_reads(0, 0x00000000, 0, 0x00000000, "x0 during reset")

    # Distinct writes verify destination selection and exact data preservation.
    await write_register(1, 0x12345678)
    await write_register(7, 0xAAAAAAAA)
    await write_register(16, 0x55555555)
    await write_register(31, 0x89ABCDEF)
    await check_reads(1, 0x12345678, 31, 0x89ABCDEF, "distinct destinations")
    await check_reads(7, 0xAAAAAAAA, 16, 0x55555555, "distinct destinations")

    # Both read ports are asynchronous, independently selected, and can read
    # the same register.
    await check_reads(7, 0xAAAAAAAA, 7, 0xAAAAAAAA, "same register on both ports")
    await check_reads(0, 0x00000000, 16, 0x55555555, "independent read ports")
    await check_reads(31, 0x89ABCDEF, 1, 0x12345678, "independent read ports")

    # Representative exact data patterns, including zero and all ones.
    await write_register(7, 0x00000000)
    await check_reads(7, 0x00000000, 16, 0x55555555, "write zero")
    await write_register(7, 0xFFFFFFFF)
    await check_reads(7, 0xFFFFFFFF, 1, 0x12345678, "write all ones")
    await write_register(7, 0x55555555)
    await check_reads(7, 0x55555555, 16, 0x55555555, "write alternating pattern")
    await write_register(7, 0xAAAAAAAA)

    # A permitted write leaves the old value visible before the rising edge,
    # then updates both asynchronous read ports after that edge.
    await FallingEdge(dut.clk)
    dut.rd_addr.value = 7
    dut.rd_data.value = 0x0F0F0F0F
    dut.rd_write.value = 1
    dut.rs1_addr.value = 7
    dut.rs2_addr.value = 7
    await Timer(1, unit="ns")
    observed1 = int(dut.rs1_data.value)
    observed2 = int(dut.rs2_data.value)
    assert observed1 == 0xAAAAAAAA, (
        f"before write edge: rs1_data expected 0xAAAAAAAA, observed 0x{observed1:08X}"
    )
    assert observed2 == 0xAAAAAAAA, (
        f"before write edge: rs2_data expected 0xAAAAAAAA, observed 0x{observed2:08X}"
    )
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    dut.rd_write.value = 0
    await check_reads(7, 0x0F0F0F0F, 16, 0x55555555, "after write edge")

    # With writes disabled, changing the destination and data across a rising
    # edge must retain the previously written values.
    await FallingEdge(dut.clk)
    dut.rd_write.value = 0
    dut.rd_addr.value = 7
    dut.rd_data.value = 0xDEADBEEF
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    dut.rd_addr.value = 16
    dut.rd_data.value = 0x00000000
    await check_reads(7, 0x0F0F0F0F, 16, 0x55555555, "write disabled")

    # A falling edge alone must not commit a write.
    await FallingEdge(dut.clk)
    dut.rd_addr.value = 16
    dut.rd_data.value = 0xCAFEBABE
    dut.rd_write.value = 1
    await Timer(1, unit="ns")
    await check_reads(16, 0x55555555, 7, 0x0F0F0F0F, "before rising edge")
    dut.rd_write.value = 0
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    await check_reads(16, 0x55555555, 7, 0x0F0F0F0F, "falling edge does not write")

    # Rewriting one selected register changes both ports reading it and leaves
    # other registers unchanged.
    await write_register(1, 0xFFFFFFFF)
    await check_reads(1, 0xFFFFFFFF, 31, 0x89ABCDEF, "isolated register update")
    await check_reads(16, 0x55555555, 7, 0x0F0F0F0F, "other registers retained")
