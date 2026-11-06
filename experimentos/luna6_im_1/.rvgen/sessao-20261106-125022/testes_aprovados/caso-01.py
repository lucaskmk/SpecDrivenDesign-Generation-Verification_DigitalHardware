import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_lw_full_word_result(dut):
    # lw x5, 0(x6)
    dut.instr.value = 0x00032283
    dut.effective_address.value = 0x00001000
    dut.store_data_in.value = 0xA1B2C3D4
    dut.data_read_data.value = 0x93C5E72B

    await Timer(1, unit="ns")

    observed = int(dut.load_result.value)
    assert observed == 0x93C5E72B, (
        f"expected load_result 0x93C5E72B, observed 0x{observed:08X}"
    )
