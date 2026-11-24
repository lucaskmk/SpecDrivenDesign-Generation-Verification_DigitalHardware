import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


def assemble_rv32im(source):
    """Assemble the small RV32IM instruction subset used by this test."""
    lines = []
    labels = {}
    pc = 0

    for raw_line in source.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if ":" in line:
            label, line = line.split(":", 1)
            labels[label.strip()] = pc
            line = line.strip()
            if not line:
                continue
        lines.append((pc, line))
        pc += 4

    def reg(token):
        token = token.strip().lower()
        assert token.startswith("x"), f"Expected register, observed {token}"
        number = int(token[1:], 0)
        assert 0 <= number < 32, f"Register out of range: {token}"
        return number

    words = []
    for instruction_pc, line in lines:
        parts = line.replace(",", " ").split()
        mnemonic = parts[0].lower()

        if mnemonic == "lui":
            rd = reg(parts[1])
            imm = int(parts[2], 0)
            assert 0 <= imm < (1 << 20), f"LUI immediate out of range: {parts[2]}"
            word = (imm << 12) | (rd << 7) | 0x37

        elif mnemonic == "mulhu":
            rd = reg(parts[1])
            rs1 = reg(parts[2])
            rs2 = reg(parts[3])
            word = (0x01 << 25) | (rs2 << 20) | (rs1 << 15) | (0x03 << 12) | (rd << 7) | 0x33

        elif mnemonic == "sw":
            rs2 = reg(parts[1])
            offset, base = parts[2].split("(", 1)
            imm = int(offset, 0)
            rs1 = reg(base.rstrip(")"))
            assert -2048 <= imm <= 2047, f"SW immediate out of range: {imm}"
            encoded_imm = imm & 0xFFF
            word = (
                ((encoded_imm >> 5) << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (0x02 << 12)
                | ((encoded_imm & 0x1F) << 7)
                | 0x23
            )

        elif mnemonic == "jal":
            rd = reg(parts[1])
            target = labels[parts[2]]
            offset = target - instruction_pc
            assert -1048576 <= offset <= 1048574 and offset % 2 == 0
            encoded_imm = offset & 0x1FFFFF
            word = (
                (((encoded_imm >> 20) & 0x1) << 31)
                | (((encoded_imm >> 1) & 0x3FF) << 21)
                | (((encoded_imm >> 11) & 0x1) << 20)
                | (((encoded_imm >> 12) & 0xFF) << 12)
                | (rd << 7)
                | 0x6F
            )

        else:
            raise ValueError(f"Unsupported instruction in test program: {mnemonic}")

        words.append(word)

    return words


@cocotb.test()
async def mulhu_zero_destination_preserves_x0(dut):
    program = assemble_rv32im(
        """
        lui x1, 0x02100
        lui x2, 0x02200
        mulhu x0, x1, x2
        sw x0, 0(x0)
    halt:
        jal x0, halt
        """
    )
    rom = {address: word for address, word in enumerate(program)}
    rom = {address * 4: word for address, word in rom.items()}

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start(start_high=False))
    await Timer(2, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected reset instr_addr=0x00000000, observed 0x{int(dut.instr_addr.value):08X}"
    )
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    dut.rst.value = 0

    expected_pcs = [0x00000000, 0x00000004, 0x00000008, 0x0000000C]
    committed_writes = []

    for expected_pc in expected_pcs:
        observed_pc = int(dut.instr_addr.value)
        assert observed_pc == expected_pc, (
            f"Expected instr_addr=0x{expected_pc:08X}, observed 0x{observed_pc:08X}"
        )
        dut.instr_data.value = rom[expected_pc]
        await Timer(1, unit="ns")

        if expected_pc == 0x0000000C:
            assert int(dut.data_write.value) == 1, "Expected the final SW to assert data_write=1"
            assert int(dut.data_addr.value) == 0x00000000, (
                f"Expected store address 0x00000000, observed 0x{int(dut.data_addr.value):08X}"
            )
            assert int(dut.data_width.value) == 0x2, (
                f"Expected word data_width=0x2, observed 0x{int(dut.data_width.value):X}"
            )
            observed_data = int(dut.data_write_data.value)
            assert observed_data == 0x00000000, (
                f"Expected x0 store data 0x00000000 after MULHU to x0, "
                f"observed 0x{observed_data:08X}"
            )
        else:
            assert int(dut.data_write.value) == 0, (
                f"Expected no store at PC 0x{expected_pc:08X}"
            )

        write_active = int(dut.data_write.value) == 1
        write_addr = int(dut.data_addr.value)
        write_width = int(dut.data_width.value)
        write_data = int(dut.data_write_data.value)

        await RisingEdge(dut.clk)
        if write_active:
            committed_writes.append((write_addr, write_width, write_data))
        await Timer(1, unit="ns")

    assert int(dut.instr_addr.value) == 0x00000010, (
        f"Expected halt-loop PC 0x00000010, observed 0x{int(dut.instr_addr.value):08X}"
    )
    dut.instr_data.value = rom[0x00000010]
    await Timer(1, unit="ns")
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000010, (
        f"Expected JAL x0,0 to hold PC at 0x00000010, "
        f"observed 0x{int(dut.instr_addr.value):08X}"
    )

    assert committed_writes == [(0x00000000, 0x2, 0x00000000)], (
        f"Expected one word store of x0 at 0x00000000, observed {committed_writes}"
    )
