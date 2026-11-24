import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
from rvgen.assembler import assemble_rv32im


@cocotb.test()
async def divu_zero_divisor_returns_all_ones(dut):
    source = """
        addi x1, x0, 0
        addi x2, x0, 0
        divu x3, x1, x2
        sw x3, 0(x0)
    halt:
        jal x0, halt
    """

    assembled = assemble_rv32im(source)
    if isinstance(assembled, tuple):
        assembled = assembled[0]
    if isinstance(assembled, dict):
        assembled = [assembled[address] for address in sorted(assembled)]
    words = [
        int(word, 2) if isinstance(word, str) and set(word) <= {"0", "1"}
        else int(word, 0) if isinstance(word, str)
        else int(word)
        for word in assembled
    ]
    assert len(words) == 5, f"Expected 5 assembled instructions, observed {len(words)}"

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000

    clock = Clock(dut.clk, 10, unit="ns")
    clock.start()
    await Timer(2, unit="ns")
    dut.rst.value = 0
    await Timer(1, unit="ns")

    stored_words = {}
    store_seen = False

    for index, instruction in enumerate(words):
        expected_pc = index * 4
        observed_pc = int(dut.instr_addr.value)
        assert observed_pc == expected_pc, (
            f"Expected instr_addr=0x{expected_pc:08X}, "
            f"observed 0x{observed_pc:08X}"
        )

        dut.instr_data.value = instruction
        await Timer(1, unit="ns")

        if index == 3:
            observed_write = int(dut.data_write.value)
            observed_addr = int(dut.data_addr.value)
            observed_width = int(dut.data_width.value)
            observed_data = int(dut.data_write_data.value)
            assert observed_write == 1, (
                f"Expected data_write=1, observed {observed_write}"
            )
            assert observed_addr == 0x00000000, (
                f"Expected data_addr=0x00000000, observed 0x{observed_addr:08X}"
            )
            assert observed_width == 0x2, (
                f"Expected data_width=0x2, observed 0x{observed_width:X}"
            )
            assert observed_data == 0xFFFFFFFF, (
                f"Expected data_write_data=0xFFFFFFFF, "
                f"observed 0x{observed_data:08X}"
            )

        await RisingEdge(dut.clk)
        if int(dut.data_write.value):
            address = int(dut.data_addr.value)
            stored_words[address & 0xFFFFFFFC] = int(dut.data_write_data.value)
            store_seen = True
        await Timer(1, unit="ns")

    assert store_seen, "Expected the DIVU result store to commit"
    observed_word = stored_words.get(0x00000000, 0x00000000)
    assert observed_word == 0xFFFFFFFF, (
        f"Expected stored DIVU result 0xFFFFFFFF, observed 0x{observed_word:08X}"
    )
