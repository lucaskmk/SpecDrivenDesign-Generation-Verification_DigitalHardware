import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


@cocotb.test()
async def test_register_file_regressao_05(dut):
    # Initialize every input before observing any output.
    dut.clk.value = 0
    dut.rst.value = 1
    dut.read_addr1.value = 0x0
    dut.read_addr2.value = 0x0
    dut.write_enable.value = 0
    dut.write_addr.value = 0x0
    dut.write_data.value = 0x00000000

    Clock(dut.clk, 10, unit="ns").start()
    await Timer(1, unit="ns")

    def check_read(signal, expected, label):
        observed = int(signal.value)
        assert observed == expected, (
            f"{label}: expected 0x{expected:08X}, observed 0x{observed:08X}"
        )

    async def write_at_edge(address, value):
        dut.write_addr.value = address
        dut.write_data.value = value
        dut.write_enable.value = 1
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        dut.write_enable.value = 0

    # Regression for the reported failure: reading x0 must not index outside
    # the register array, and both read ports must return zero.
    check_read(dut.read_data1, 0x00000000, "x0 read on port 1 during reset")
    check_read(dut.read_data2, 0x00000000, "x0 read on port 2 during reset")

    dut.rst.value = 0
    await Timer(1, unit="ns")

    # Populate distinct registers and check asynchronous, independent reads.
    await write_at_edge(0x7, 0xA55A3CC3)
    await write_at_edge(0x1F, 0x80000000)

    dut.read_addr1.value = 0x7
    dut.read_addr2.value = 0x1F
    await Timer(1, unit="ns")
    check_read(dut.read_data1, 0xA55A3CC3, "asynchronous read of x7")
    check_read(dut.read_data2, 0x80000000, "asynchronous read of x31")

    # Changing one read address must not disturb the other read port.
    dut.read_addr1.value = 0x0
    await Timer(1, unit="ns")
    check_read(dut.read_data1, 0x00000000, "asynchronous read of x0")
    check_read(dut.read_data2, 0x80000000, "port 2 unchanged when port 1 changes")

    dut.read_addr1.value = 0x7
    dut.read_addr2.value = 0x0
    await Timer(1, unit="ns")
    check_read(dut.read_data1, 0xA55A3CC3, "port 1 unchanged when port 2 changes")
    check_read(dut.read_data2, 0x00000000, "asynchronous x0 read on port 2")

    # Writes to x0 are ignored, and must not alter sampled nonzero registers.
    dut.read_addr1.value = 0x0
    dut.read_addr2.value = 0x7
    for value in (0x12345678, 0xFFFFFFFF):
        await write_at_edge(0x0, value)
        check_read(dut.read_data1, 0x00000000, "x0 remains hardwired to zero")
        check_read(dut.read_data2, 0xA55A3CC3, "x0 write preserves x7")

    # A disabled write leaves its destination unchanged.
    dut.read_addr1.value = 0x7
    dut.read_addr2.value = 0x1F
    dut.write_addr.value = 0x7
    dut.write_data.value = 0xFFFFFFFF
    dut.write_enable.value = 0
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    check_read(dut.read_data1, 0xA55A3CC3, "disabled write preserves x7")
    check_read(dut.read_data2, 0x80000000, "disabled write preserves x31")

    # Assert reset between clock edges; selected registers clear immediately.
    dut.rst.value = 1
    await Timer(1, unit="ns")
    check_read(dut.read_data1, 0x00000000, "asynchronous reset clears x7")
    check_read(dut.read_data2, 0x00000000, "asynchronous reset clears x31")

    # Writes during reset, including one on a rising edge, have no effect.
    dut.write_addr.value = 0x7
    dut.write_data.value = 0xDEADBEEF
    dut.write_enable.value = 1
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    check_read(dut.read_data1, 0x00000000, "reset suppresses an enabled write")
    dut.write_enable.value = 0

    # Deasserting reset does not restore or change the cleared register.
    dut.rst.value = 0
    await Timer(1, unit="ns")
    check_read(dut.read_data1, 0x00000000, "x7 remains zero after reset deassertion")

    # A later enabled write takes effect on the rising edge.
    await write_at_edge(0x7, 0xDEADBEEF)
    check_read(dut.read_data1, 0xDEADBEEF, "x7 accepts a write after reset")
