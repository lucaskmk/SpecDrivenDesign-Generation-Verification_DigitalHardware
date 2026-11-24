import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer


def encode_addi(rd, rs1, imm):
    return (
        (((imm & 0xFFF) << 20)
         | ((rs1 & 0x1F) << 15)
         | ((rd & 0x1F) << 7)
         | 0x13)
        & 0xFFFFFFFF
    )


def encode_load(rd, rs1, imm, funct3):
    return (
        (((imm & 0xFFF) << 20)
         | ((rs1 & 0x1F) << 15)
         | ((funct3 & 0x7) << 12)
         | ((rd & 0x1F) << 7)
         | 0x03)
        & 0xFFFFFFFF
    )


def encode_store(rs2, rs1, imm, funct3):
    imm &= 0xFFF
    return (
        ((((imm >> 5) & 0x7F) << 25)
         | ((rs2 & 0x1F) << 20)
         | ((rs1 & 0x1F) << 15)
         | ((funct3 & 0x7) << 12)
         | ((imm & 0x1F) << 7)
         | 0x23)
        & 0xFFFFFFFF
    )


@cocotb.test()
async def test_load_data_extraction_and_sign_extension_regression(dut):
    """Check load extraction, sign/zero extension, widths, and byte offsets."""
    memory = {}
    # At 0x100, the little-endian bytes are 0x01, 0x7F, 0xFF, and 0x80.
    for offset, byte in enumerate((0x01, 0x7F, 0xFF, 0x80)):
        memory[(0x100 + offset) & 0xFFFFFFFF] = byte

    program = [
        encode_addi(1, 0, 0x100),  # Base address.
        encode_addi(3, 0, 0x200),  # Result buffer.
        encode_addi(4, 1, 4),      # Base for a negative-offset load.
        encode_load(5, 1, 0, 0),   # LB  offset 0
        encode_load(6, 1, 1, 0),   # LB  offset 1
        encode_load(7, 1, 2, 0),   # LB  offset 2
        encode_load(8, 1, 3, 0),   # LB  offset 3
        encode_load(9, 1, 2, 4),   # LBU offset 2
        encode_load(10, 1, 3, 4),  # LBU offset 3
        encode_load(11, 1, 0, 1),  # LH  offset 0
        encode_load(12, 1, 2, 1),  # LH  offset 2
        encode_load(13, 1, 2, 5),  # LHU offset 2
        encode_load(14, 1, 0, 2),  # LW
        encode_load(15, 4, -4, 0), # LB with a negative immediate.
    ]

    expected_values = [
        0x00000001,
        0x0000007F,
        0xFFFFFFFF,
        0xFFFFFF80,
        0x000000FF,
        0x00000080,
        0x00007F01,
        0xFFFF80FF,
        0x000080FF,
        0x80FF7F01,
        0x00000001,
    ]

    # Keys are instruction indices, not byte-addressed PCs.
    load_specs = {
        3: (0x100, 0x00),
        4: (0x101, 0x00),
        5: (0x102, 0x00),
        6: (0x103, 0x00),
        7: (0x102, 0x00),
        8: (0x103, 0x00),
        9: (0x100, 0x01),
        10: (0x102, 0x01),
        11: (0x102, 0x01),
        12: (0x100, 0x02),
        13: (0x100, 0x00),
    }

    # Export each loaded register through SW so architectural results can be
    # checked using only the public data-memory interface.
    result_registers = list(range(5, 16))
    for index, reg in enumerate(result_registers):
        program.append(encode_store(reg, 3, index * 4, 2))

    halt_pc = len(program) * 4
    program.append(0x0000006F)  # JAL x0, 0

    instructions = {
        (index * 4) & 0xFFFFFFFF: word & 0xFFFFFFFF
        for index, word in enumerate(program)
    }

    def read_word(aligned_address):
        aligned_address &= 0xFFFFFFFC
        return sum(
            (memory.get((aligned_address + lane) & 0xFFFFFFFF, 0) & 0xFF)
            << (8 * lane)
            for lane in range(4)
        ) & 0xFFFFFFFF

    def write_store(address, width, value):
        byte_count = {0: 1, 1: 2, 2: 4}[width]
        for lane in range(byte_count):
            memory[(address + lane) & 0xFFFFFFFF] = (
                (value >> (8 * lane)) & 0xFF
            )

    Clock(dut.clk, 10, unit="ns").start()
    dut.rst.value = 1
    dut.instr_data.value = instructions[0] & 0xFFFFFFFF
    dut.data_read_data.value = 0x00000000

    # Keep reset asserted through a rising edge, then release it on a falling
    # edge after presenting the first instruction.
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"expected reset PC 0x00000000, observed "
        f"0x{int(dut.instr_addr.value):08X}"
    )

    await FallingEdge(dut.clk)
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"expected instruction address 0x00000000, observed "
        f"0x{int(dut.instr_addr.value):08X}"
    )
    dut.instr_data.value = instructions[0] & 0xFFFFFFFF
    await Timer(1, unit="ns")
    dut.rst.value = 0

    for pc in range(0, len(program) * 4, 4):
        if pc != 0:
            await FallingEdge(dut.clk)

        observed_pc = int(dut.instr_addr.value)
        assert observed_pc == pc, (
            f"expected instruction address 0x{pc:08X}, "
            f"observed 0x{observed_pc:08X}"
        )

        instruction = instructions[pc] & 0xFFFFFFFF
        dut.instr_data.value = instruction
        await Timer(1, unit="ns")

        address = int(dut.data_addr.value) & 0xFFFFFFFF
        dut.data_read_data.value = read_word(address) & 0xFFFFFFFF
        await Timer(1, unit="ns")

        instruction_index = pc // 4
        if instruction_index in load_specs:
            expected_address, expected_width = load_specs[instruction_index]
            observed_address = int(dut.data_addr.value)
            observed_width = int(dut.data_width.value)
            observed_write = int(dut.data_write.value)
            assert observed_address == expected_address, (
                f"expected load address 0x{expected_address:08X}, "
                f"observed 0x{observed_address:08X}"
            )
            assert observed_width == expected_width, (
                f"expected load width 0x{expected_width:X}, "
                f"observed 0x{observed_width:X}"
            )
            assert observed_write == 0, (
                f"expected data_write 0, observed {observed_write}"
            )

        opcode = instruction & 0x7F
        pending_store = None
        if opcode == 0x23:
            store_address = int(dut.data_addr.value) & 0xFFFFFFFF
            store_width = int(dut.data_width.value)
            store_value = int(dut.data_write_data.value) & 0xFFFFFFFF
            assert int(dut.data_write.value) == 1, (
                "expected data_write 1 for result-buffer store, observed 0"
            )
            assert store_width == 0x2, (
                f"expected store width 0x2, observed 0x{store_width:X}"
            )
            pending_store = (store_address, store_width, store_value)
        else:
            assert int(dut.data_write.value) == 0, (
                f"expected data_write 0 at PC 0x{pc:08X}, "
                f"observed {int(dut.data_write.value)}"
            )

        await RisingEdge(dut.clk)
        if pending_store is not None:
            write_store(*pending_store)
        await Timer(1, unit="ns")

    for index, expected in enumerate(expected_values):
        address = (0x200 + index * 4) & 0xFFFFFFFF
        observed = read_word(address)
        assert observed == expected, (
            f"expected load result 0x{expected:08X} at 0x{address:08X}, "
            f"observed 0x{observed:08X}"
        )

    for _ in range(2):
        await FallingEdge(dut.clk)
        observed_pc = int(dut.instr_addr.value)
        assert observed_pc == halt_pc, (
            f"expected halt PC 0x{halt_pc:08X}, observed 0x{observed_pc:08X}"
        )
        dut.instr_data.value = instructions[halt_pc] & 0xFFFFFFFF
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        observed_pc = int(dut.instr_addr.value)
        assert observed_pc == halt_pc, (
            f"expected halt loop to hold PC at 0x{halt_pc:08X}, "
            f"observed 0x{observed_pc:08X}"
        )
