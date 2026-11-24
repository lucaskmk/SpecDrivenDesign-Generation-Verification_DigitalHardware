import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

try:
    from rvgen.assembler import assemble_rv32im
except ImportError:
    from rvgen import assemble_rv32im


def _word(value):
    if isinstance(value, int):
        return value & 0xFFFFFFFF

    text = str(value).strip().replace("_", "")
    try:
        return int(text, 0) & 0xFFFFFFFF
    except ValueError:
        return int(text, 2) & 0xFFFFFFFF


def _program_words(assembled):
    if isinstance(assembled, dict):
        return {int(address): _word(word) for address, word in assembled.items()}

    words = list(assembled)
    if words and all(
        isinstance(item, (tuple, list)) and len(item) == 2 for item in words
    ):
        return {int(address): _word(word) for address, word in words}

    return {4 * index: _word(word) for index, word in enumerate(words)}


@cocotb.test()
async def lb_sign_extends_negative_byte_to_word_store(dut):
    source = """
        lb x1, 0(x0)
        sw x1, 4(x0)
    halt:
        jal x0, halt
    """
    program = _program_words(assemble_rv32im(source))

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected reset instr_addr=0x00000000, "
        f"observed 0x{int(dut.instr_addr.value):08X}"
    )
    dut.rst.value = 0

    data_words = {0x00000000: 0x000000FF}
    saw_lb = False
    saw_result_store = False
    halt_address = 0x00000008

    for _ in range(8):
        pc = int(dut.instr_addr.value)
        assert pc in program, f"Expected a program instruction at 0x{pc:08X}"
        dut.instr_data.value = program[pc]
        await Timer(1, unit="ns")

        address = int(dut.data_addr.value)
        dut.data_read_data.value = data_words.get(address & 0xFFFFFFFC, 0)
        await Timer(1, unit="ns")

        write = int(dut.data_write.value)
        if pc == 0x00000000:
            observed = (address, int(dut.data_width.value))
            expected = (0x00000000, 0x0)
            assert observed == expected, (
                f"Expected LB address/width {expected}, observed {observed}"
            )
            assert int(dut.data_read_data.value) == 0x000000FF, (
                "Expected LB input word 0x000000FF, observed "
                f"0x{int(dut.data_read_data.value):08X}"
            )
            saw_lb = True
        elif pc == 0x00000004:
            observed = (
                write,
                address,
                int(dut.data_width.value),
                int(dut.data_write_data.value),
            )
            expected = (1, 0x00000004, 0x2, 0xFFFFFFFF)
            assert observed == expected, (
                f"Expected result store {expected}, observed {observed}"
            )
            saw_result_store = True

        pending_store = None
        if write:
            pending_store = (
                int(dut.data_addr.value) & 0xFFFFFFFC,
                int(dut.data_width.value),
                int(dut.data_write_data.value),
            )

        await RisingEdge(dut.clk)
        if pending_store is not None:
            store_address, width, store_data = pending_store
            assert width == 0x2, (
                f"Expected word-store width 0x2, observed 0x{width:X}"
            )
            data_words[store_address] = store_data & 0xFFFFFFFF

        await Timer(1, unit="ns")
        if pc == halt_address and int(dut.instr_addr.value) == halt_address:
            break

    assert saw_lb, "Expected to observe the focal LB transaction"
    assert saw_result_store, "Expected to observe the sign-extended result store"
    observed_word = data_words.get(0x00000004, 0)
    assert observed_word == 0xFFFFFFFF, (
        f"Expected stored LB result 0xFFFFFFFF, observed 0x{observed_word:08X}"
    )
