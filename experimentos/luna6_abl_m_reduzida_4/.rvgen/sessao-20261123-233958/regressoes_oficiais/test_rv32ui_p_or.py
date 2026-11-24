import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
from rvgen.assembler import assemble_rv32im


def _as_word(value):
    if isinstance(value, str):
        if value.startswith("0x"):
            return int(value, 16)
        if len(value) == 32 and set(value) <= {"0", "1"}:
            return int(value, 2)
        return int(value, 0)
    return int(value)


@cocotb.test()
async def or_result_is_stored_correctly(dut):
    source = """
        lui  x1, 0xff010
        addi x1, x1, -256
        lui  x2, 0x0f0f1
        addi x2, x2, -241
        or   x3, x1, x2
        sw   x3, 0(x0)
    halt:
        jal  x0, halt
    """

    assembled = assemble_rv32im(source)
    if isinstance(assembled, dict):
        program = {int(address): _as_word(word) for address, word in assembled.items()}
    else:
        program = {4 * index: _as_word(word) for index, word in enumerate(assembled)}

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = program[0]
    dut.data_read_data.value = 0x00000000

    clock = Clock(dut.clk, 10, unit="ns")
    clock.start()

    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected instr_addr=0x00000000 during reset, "
        f"observed 0x{int(dut.instr_addr.value):08X}"
    )
    dut.rst.value = 0

    memory = {}
    stores = 0
    expected_result = 0xFF0FFF0F

    for _ in range(len(program) + 2):
        pc = int(dut.instr_addr.value)
        assert pc in program, f"Expected a program instruction at 0x{pc:08X}"
        dut.instr_data.value = program[pc]
        await Timer(1, unit="ns")

        writing = int(dut.data_write.value)
        if writing:
            address = int(dut.data_addr.value)
            width = int(dut.data_width.value)
            data = int(dut.data_write_data.value)

            assert address == 0x00000000, (
                f"Expected store address 0x00000000, observed 0x{address:08X}"
            )
            assert width == 0x2, f"Expected word width 0x2, observed 0x{width:X}"
            assert data == expected_result, (
                f"Expected OR result 0x{expected_result:08X}, observed 0x{data:08X}"
            )

        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")

        if writing:
            stores += 1
            address = int(dut.data_addr.value)
            data = int(dut.data_write_data.value)
            for lane in range(4):
                memory[address + lane] = (data >> (8 * lane)) & 0xFF

        if pc == max(program) and int(dut.instr_addr.value) == pc:
            break

    assert stores == 1, f"Expected exactly one store, observed {stores}"
    observed_word = sum(memory.get(lane, 0) << (8 * lane) for lane in range(4))
    assert observed_word == expected_result, (
        f"Expected stored word 0x{expected_result:08X}, "
        f"observed 0x{observed_word:08X}"
    )
