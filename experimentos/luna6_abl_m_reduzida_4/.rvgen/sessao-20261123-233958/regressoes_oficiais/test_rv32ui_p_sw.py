import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


def assemble_rv32im(source):
    """Assemble the LUI, ADDI, and SW instructions used by this test."""
    registers = {f"x{i}": i for i in range(32)}
    words = []

    for raw_line in source.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue

        parts = line.replace(",", " ").replace("(", " ").replace(")", " ").split()
        mnemonic = parts[0].lower()

        if mnemonic == "lui":
            rd = registers[parts[1].lower()]
            imm = int(parts[2], 0) & 0xFFFFF
            word = (imm << 12) | (rd << 7) | 0x37
        elif mnemonic == "addi":
            rd = registers[parts[1].lower()]
            rs1 = registers[parts[2].lower()]
            imm = int(parts[3], 0) & 0xFFF
            word = (imm << 20) | (rs1 << 15) | (rd << 7) | 0x13
        elif mnemonic == "sw":
            rs2 = registers[parts[1].lower()]
            imm = int(parts[2], 0) & 0xFFF
            rs1 = registers[parts[3].lower()]
            word = (
                ((imm >> 5) << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (0x2 << 12)
                | ((imm & 0x1F) << 7)
                | 0x23
            )
        else:
            raise ValueError(f"Unsupported instruction in test assembly: {mnemonic}")

        words.append(word)

    return words


@cocotb.test()
async def store_uses_unaligned_base_before_applying_offset(dut):
    program_words = assemble_rv32im(
        """
        lui  x5, 0x1
        addi x5, x5, 1
        lui  x3, 0x58213
        addi x3, x3, 0x98
        sw   x3, 3(x5)
        """
    )
    program = {4 * index: word for index, word in enumerate(program_words)}

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start(start_high=False))

    await Timer(11, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected reset instr_addr=0x00000000, observed "
        f"0x{int(dut.instr_addr.value):08X}"
    )
    dut.rst.value = 0
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected instr_addr=0x00000000 after reset release, observed "
        f"0x{int(dut.instr_addr.value):08X}"
    )

    memory_bytes = {}
    focal_transaction = None

    for pc in sorted(program):
        dut.instr_data.value = program[pc]
        await Timer(1, unit="ns")

        observed_pc = int(dut.instr_addr.value)
        assert observed_pc == pc, (
            f"Expected instr_addr=0x{pc:08X}, observed 0x{observed_pc:08X}"
        )

        if pc == 0x00000010:
            expected_data = 0x58213098
            assert int(dut.data_write.value) == 1, (
                "Expected SW to assert data_write=1, observed "
                f"{int(dut.data_write.value)}"
            )
            assert int(dut.data_addr.value) == 0x00001004, (
                f"Expected effective address=0x00001004, observed "
                f"0x{int(dut.data_addr.value):08X}"
            )
            assert int(dut.data_width.value) == 0x2, (
                f"Expected word data_width=0x2, observed "
                f"0x{int(dut.data_width.value):X}"
            )
            assert int(dut.data_write_data.value) == expected_data, (
                f"Expected unshifted store data=0x{expected_data:08X}, observed "
                f"0x{int(dut.data_write_data.value):08X}"
            )
            focal_transaction = (
                int(dut.data_addr.value),
                int(dut.data_width.value),
                int(dut.data_write_data.value),
            )
        else:
            assert int(dut.data_write.value) == 0, (
                f"Expected data_write=0 at PC 0x{pc:08X}, observed "
                f"{int(dut.data_write.value)}"
            )

        transaction = None
        if int(dut.data_write.value) == 1:
            transaction = (
                int(dut.data_addr.value),
                int(dut.data_width.value),
                int(dut.data_write_data.value),
            )

        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")

        if transaction is not None:
            address, width, data = transaction
            byte_count = {0x0: 1, 0x1: 2, 0x2: 4}[width]
            for lane in range(byte_count):
                memory_bytes[address + lane] = (data >> (8 * lane)) & 0xFF

    assert focal_transaction == (0x00001004, 0x2, 0x58213098), (
        "Expected focal SW transaction (address=0x00001004, width=0x2, "
        f"data=0x58213098), observed {focal_transaction}"
    )
    observed_word = sum(
        memory_bytes.get(0x00001004 + lane, 0) << (8 * lane)
        for lane in range(4)
    )
    assert observed_word == 0x58213098, (
        f"Expected committed word=0x58213098, observed 0x{observed_word:08X}"
    )
