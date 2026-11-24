import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
from rvgen.assembler import assemble_rv32im


@cocotb.test()
async def lhu_case_at_word_offset_four(dut):
    source = """
        lhu  x2, 4(x0)
        sw   x2, 0(x0)
    halt:
        jal  x0, halt
    """

    assembled = assemble_rv32im(source)
    if isinstance(assembled, dict):
        rom = {int(address): int(word) for address, word in assembled.items()}
    else:
        words = list(assembled)
        rom = {
            4 * index: (
                int(word, 0) if isinstance(word, str) else int(word)
            )
            for index, word in enumerate(words)
        }

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000FF0

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected reset instr_addr=0x00000000, "
        f"observed 0x{int(dut.instr_addr.value):08X}"
    )

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected instr_addr=0x00000000 during reset, "
        f"observed 0x{int(dut.instr_addr.value):08X}"
    )

    dut.rst.value = 0
    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected instr_addr=0x00000000 after reset, "
        f"observed 0x{int(dut.instr_addr.value):08X}"
    )

    committed_store = None

    for expected_pc in (0x00000000, 0x00000004, 0x00000008):
        assert expected_pc in rom, (
            f"Expected assembled instruction at 0x{expected_pc:08X}"
        )
        dut.instr_data.value = rom[expected_pc]
        dut.data_read_data.value = 0x00000FF0
        await Timer(1, unit="ns")

        observed_pc = int(dut.instr_addr.value)
        assert observed_pc == expected_pc, (
            f"Expected instr_addr=0x{expected_pc:08X}, "
            f"observed 0x{observed_pc:08X}"
        )

        if expected_pc == 0x00000000:
            observed_addr = int(dut.data_addr.value)
            observed_width = int(dut.data_width.value)
            observed_write = int(dut.data_write.value)
            assert observed_addr == 0x00000004, (
                f"Expected LHU data_addr=0x00000004, "
                f"observed 0x{observed_addr:08X}"
            )
            assert observed_width == 0x1, (
                f"Expected LHU data_width=0x1, observed 0x{observed_width:X}"
            )
            assert observed_write == 0, (
                f"Expected LHU data_write=0, observed {observed_write}"
            )

        elif expected_pc == 0x00000004:
            observed_write = int(dut.data_write.value)
            observed_addr = int(dut.data_addr.value)
            observed_width = int(dut.data_width.value)
            observed_data = int(dut.data_write_data.value)
            assert observed_write == 1, (
                f"Expected result store data_write=1, observed {observed_write}"
            )
            assert observed_addr == 0x00000000, (
                f"Expected result store data_addr=0x00000000, "
                f"observed 0x{observed_addr:08X}"
            )
            assert observed_width == 0x2, (
                f"Expected result store data_width=0x2, "
                f"observed 0x{observed_width:X}"
            )
            assert observed_data == 0x00000FF0, (
                f"Expected LHU result store data=0x00000FF0, "
                f"observed 0x{observed_data:08X}"
            )
            committed_store = (observed_addr, observed_width, observed_data)

        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")

        if expected_pc == 0x00000000:
            observed_pc = int(dut.instr_addr.value)
            assert observed_pc == 0x00000004, (
                f"Expected next PC=0x00000004 after LHU, "
                f"observed 0x{observed_pc:08X}"
            )
        elif expected_pc == 0x00000004:
            assert committed_store == (
                0x00000000,
                0x2,
                0x00000FF0,
            ), f"Expected committed LHU result store, observed {committed_store}"
            observed_pc = int(dut.instr_addr.value)
            assert observed_pc == 0x00000008, (
                f"Expected next PC=0x00000008 after result store, "
                f"observed 0x{observed_pc:08X}"
            )
        else:
            observed_pc = int(dut.instr_addr.value)
            assert observed_pc == 0x00000008, (
                f"Expected halt loop PC=0x00000008, "
                f"observed 0x{observed_pc:08X}"
            )
