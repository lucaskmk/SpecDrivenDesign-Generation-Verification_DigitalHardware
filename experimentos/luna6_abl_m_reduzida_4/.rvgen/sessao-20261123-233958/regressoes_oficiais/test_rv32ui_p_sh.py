import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

try:
    from rvgen.assembler import assemble_rv32im
except ImportError:
    try:
        from rvgen import assemble_rv32im
    except ImportError:
        try:
            from riscv_assembler import assemble_rv32im
        except ImportError:
            from assembler import assemble_rv32im


@cocotb.test()
async def halfword_store_uses_low_source_bits(dut):
    source = """
        lui  x3, 0xBEEF1
        addi x3, x3, -1376
        sh   x3, 4(x0)
    halt:
        jal  x0, halt
    """

    assembled = assemble_rv32im(source)
    if isinstance(assembled, tuple):
        assembled = assembled[0]

    if isinstance(assembled, dict):
        program = {
            int(address, 0) if isinstance(address, str) else int(address): int(word)
            for address, word in assembled.items()
        }
    else:
        items = list(assembled)
        if items and isinstance(items[0], (tuple, list)) and len(items[0]) == 2:
            program = {int(address): int(word) for address, word in items}
        else:
            program = {4 * index: int(word) for index, word in enumerate(items)}

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000
    clock = Clock(dut.clk, 10, unit="ns")
    clock.start(start_high=False)

    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected reset PC=0x00000000, observed 0x{int(dut.instr_addr.value):08X}"
    )

    dut.rst.value = 0
    memory = {}

    for expected_pc in (0x00000000, 0x00000004, 0x00000008):
        observed_pc = int(dut.instr_addr.value)
        assert observed_pc == expected_pc, (
            f"Expected instruction PC=0x{expected_pc:08X}, "
            f"observed 0x{observed_pc:08X}"
        )

        dut.instr_data.value = program[expected_pc]
        await Timer(1, unit="ns")

        if expected_pc == 0x00000008:
            write = int(dut.data_write.value)
            address = int(dut.data_addr.value)
            width = int(dut.data_width.value)
            write_data = int(dut.data_write_data.value)

            assert write == 1, f"Expected data_write=1, observed {write}"
            assert address == 0x00000004, (
                f"Expected SH byte address=0x00000004, observed 0x{address:08X}"
            )
            assert width == 0x1, f"Expected SH data_width=0x1, observed 0x{width:X}"
            assert write_data == 0xBEEF0AA0, (
                f"Expected unshifted store data=0xBEEF0AA0, "
                f"observed 0x{write_data:08X}"
            )

        await RisingEdge(dut.clk)
        if expected_pc == 0x00000008:
            for lane in range(2):
                memory[address + lane] = (write_data >> (8 * lane)) & 0xFF
        await Timer(1, unit="ns")

    assert memory.get(0x00000004) == 0xA0, (
        f"Expected memory[0x00000004]=0xA0, observed "
        f"0x{memory.get(0x00000004, 0):02X}"
    )
    assert memory.get(0x00000005) == 0x0A, (
        f"Expected memory[0x00000005]=0x0A, observed "
        f"0x{memory.get(0x00000005, 0):02X}"
    )
