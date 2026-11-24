import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


def assemble_rv32im(source):
    """Assemble the RV32IM instructions used by this focused test."""
    words = []

    def reg(token):
        token = token.strip().lower()
        if not token.startswith("x"):
            raise ValueError(f"Expected an integer register, got {token}")
        index = int(token[1:], 10)
        if not 0 <= index < 32:
            raise ValueError(f"Register index out of range: {token}")
        return index

    for raw_line in source.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue

        fields = line.replace(",", " ").split()
        operation = fields[0].lower()

        if operation == "lui":
            rd = reg(fields[1])
            immediate = int(fields[2], 0)
            words.append(((immediate & 0xFFFFF) << 12) | (rd << 7) | 0x37)

        elif operation == "addi":
            rd = reg(fields[1])
            rs1 = reg(fields[2])
            immediate = int(fields[3], 0)
            words.append(
                ((immediate & 0xFFF) << 20)
                | (rs1 << 15)
                | (rd << 7)
                | 0x13
            )

        elif operation == "xor":
            rd = reg(fields[1])
            rs1 = reg(fields[2])
            rs2 = reg(fields[3])
            words.append(
                (rs2 << 20)
                | (rs1 << 15)
                | (4 << 12)
                | (rd << 7)
                | 0x33
            )

        elif operation == "sw":
            rs2 = reg(fields[1])
            offset_and_base = fields[2]
            left_paren = offset_and_base.index("(")
            offset = int(offset_and_base[:left_paren], 0)
            rs1 = reg(offset_and_base[left_paren + 1 : -1])
            immediate = offset & 0xFFF
            words.append(
                (((immediate >> 5) & 0x7F) << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (2 << 12)
                | ((immediate & 0x1F) << 7)
                | 0x23
            )

        else:
            raise ValueError(f"Unsupported instruction in test source: {operation}")

    return words


@cocotb.test()
async def xor_write_to_x0_is_ignored(dut):
    source = """
        lui  x1, 0x11111
        addi x1, x1, 273
        lui  x2, 0x22222
        addi x2, x2, 546
        xor  x0, x1, x2
        sw   x0, 0(x0)
    """
    program = assemble_rv32im(source)
    rom = {4 * index: word for index, word in enumerate(program)}

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = rom[0]
    dut.data_read_data.value = 0x00000000

    clock = Clock(dut.clk, 10, unit="ns")
    clock.start(start_high=False)

    await Timer(6, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected reset PC=0x00000000, observed "
        f"0x{int(dut.instr_addr.value):08X}"
    )

    dut.rst.value = 0
    writes = []
    memory = {}

    for index, instruction in enumerate(program):
        expected_pc = 4 * index
        dut.instr_data.value = rom[expected_pc]
        await Timer(1, unit="ns")

        observed_pc = int(dut.instr_addr.value)
        assert observed_pc == expected_pc, (
            f"Expected instr_addr=0x{expected_pc:08X}, "
            f"observed 0x{observed_pc:08X}"
        )
        assert int(dut.instr_data.value) == instruction, (
            f"Expected instruction=0x{instruction:08X}, "
            f"observed 0x{int(dut.instr_data.value):08X}"
        )

        is_focal_store = index == len(program) - 1
        observed_write = int(dut.data_write.value)

        if is_focal_store:
            assert observed_write == 1, (
                f"Expected the final SW to assert data_write=1, "
                f"observed {observed_write}"
            )
            observed_addr = int(dut.data_addr.value)
            observed_width = int(dut.data_width.value)
            observed_data = int(dut.data_write_data.value)
            assert observed_addr == 0x00000000, (
                f"Expected store address=0x00000000, "
                f"observed 0x{observed_addr:08X}"
            )
            assert observed_width == 0x2, (
                f"Expected word-store data_width=0x2, "
                f"observed 0x{observed_width:X}"
            )
            assert observed_data == 0x00000000, (
                f"Expected x0 store data=0x00000000 after XOR to x0, "
                f"observed 0x{observed_data:08X}"
            )
            pending_write = (observed_addr, observed_width, observed_data)
        else:
            assert observed_write == 0, (
                f"Expected data_write=0 before the focal store, "
                f"observed {observed_write}"
            )
            pending_write = None

        await RisingEdge(dut.clk)

        if pending_write is not None:
            address, width, data = pending_write
            writes.append((address, width, data))
            if width == 0x2:
                memory[address & 0xFFFFFFFC] = data & 0xFFFFFFFF

        await Timer(1, unit="ns")

    assert writes == [(0x00000000, 0x2, 0x00000000)], (
        f"Expected one word store of 0x00000000 to 0x00000000, "
        f"observed {writes}"
    )
    assert memory.get(0x00000000) == 0x00000000, (
        f"Expected memory[0x00000000]=0x00000000, "
        f"observed 0x{memory.get(0x00000000, 0):08X}"
    )

    clock.stop()
