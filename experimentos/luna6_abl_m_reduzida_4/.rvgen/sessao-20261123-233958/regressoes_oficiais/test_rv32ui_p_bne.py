import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

try:
    from rvgen.assembler import assemble_rv32im
except ImportError:
    try:
        from rvgen import assemble_rv32im
    except ImportError:
        from assembler import assemble_rv32im


def _to_word(value):
    if isinstance(value, int):
        return value & 0xFFFFFFFF
    text = str(value).strip().replace("_", "")
    if text.startswith("0x"):
        return int(text, 16) & 0xFFFFFFFF
    if len(text) == 32 and set(text) <= {"0", "1"}:
        return int(text, 2)
    return int(text, 0) & 0xFFFFFFFF


def _program_words(assembled):
    if isinstance(assembled, dict):
        return {int(address, 0) if isinstance(address, str) else int(address):
                _to_word(word) for address, word in assembled.items()}

    if isinstance(assembled, tuple) and assembled:
        assembled = assembled[0]

    if isinstance(assembled, (bytes, bytearray)):
        return {
            address: int.from_bytes(assembled[address:address + 4], "little")
            for address in range(0, len(assembled) - 3, 4)
        }

    words = list(assembled)
    return {index * 4: _to_word(word) for index, word in enumerate(words)}


@cocotb.test()
async def bne_takes_branch_for_unequal_operands(dut):
    source = """
        addi x1, x0, 90
        bne  x1, x0, taken
        jal  x0, halt
    taken:
        sw   x1, 0(x0)
    halt:
        jal  x0, halt
    """
    program = _program_words(assemble_rv32im(source))

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000
    Clock(dut.clk, 10, unit="ns").start(start_high=False)

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected reset instr_addr=0x00000000, observed "
        f"0x{int(dut.instr_addr.value):08X}"
    )
    dut.rst.value = 0

    memory = {}
    branch_taken_checked = False
    store_seen = False

    for _ in range(8):
        pc = int(dut.instr_addr.value)
        dut.instr_data.value = program.get(pc, 0x0000006F)
        await Timer(1, unit="ns")

        if int(dut.data_write.value):
            address = int(dut.data_addr.value)
            width = int(dut.data_width.value)
            write_data = int(dut.data_write_data.value)

            assert address == 0x00000000, (
                f"Expected store address 0x00000000, observed 0x{address:08X}"
            )
            assert width == 0x2, (
                f"Expected word-store width 0x2, observed 0x{width:X}"
            )
            assert write_data == 0x0000005A, (
                f"Expected store data 0x0000005A, observed 0x{write_data:08X}"
            )
            store_seen = True

        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")

        if pc == 0x00000004:
            observed_pc = int(dut.instr_addr.value)
            assert observed_pc == 0x0000000C, (
                f"Expected BNE target 0x0000000C, observed 0x{observed_pc:08X}"
            )
            branch_taken_checked = True

        if store_seen:
            size = 1 << width
            for lane in range(size):
                memory[address + lane] = (write_data >> (8 * lane)) & 0xFF
            break

    assert branch_taken_checked, "Expected to execute and take the BNE at 0x00000004"
    assert store_seen, "Expected the taken BNE path to reach the witness store"
    observed_word = sum(memory.get(lane, 0) << (8 * lane) for lane in range(4))
    assert observed_word == 0x0000005A, (
        f"Expected memory word 0x0000005A, observed 0x{observed_word:08X}"
    )
