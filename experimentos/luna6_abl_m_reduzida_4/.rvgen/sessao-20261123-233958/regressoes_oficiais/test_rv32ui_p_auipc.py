import cocotb
from cocotb.triggers import Timer


def _reg(token):
    token = token.strip().lower()
    if not token.startswith("x"):
        raise ValueError(f"Expected an integer register, got {token}")
    return int(token[1:])


def assemble_rv32im(source):
    """Assemble the ADDI, AUIPC, and SW instructions used by this program."""
    words = []

    for line in source.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue

        mnemonic, operands = line.split(None, 1)
        args = [part.strip() for part in operands.split(",")]

        if mnemonic == "addi":
            rd, rs1 = _reg(args[0]), _reg(args[1])
            imm = int(args[2], 0)
            words.append(
                ((imm & 0xFFF) << 20)
                | (rs1 << 15)
                | (rd << 7)
                | 0x13
            )
        elif mnemonic == "auipc":
            rd = _reg(args[0])
            imm20 = int(args[1], 0)
            if not 0 <= imm20 <= 0xFFFFF:
                raise ValueError("AUIPC immediate must fit in 20 bits")
            words.append((imm20 << 12) | (rd << 7) | 0x17)
        elif mnemonic == "sw":
            rs2 = _reg(args[0])
            offset, base = args[1].split("(", 1)
            imm = int(offset.strip(), 0)
            rs1 = _reg(base.rstrip(")"))
            words.append(
                (((imm >> 5) & 0x7F) << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (0x2 << 12)
                | ((imm & 0x1F) << 7)
                | 0x23
            )
        else:
            raise ValueError(f"Unsupported instruction in test program: {mnemonic}")

    return words


@cocotb.test()
async def auipc_adds_its_current_pc_before_store(dut):
    program_words = assemble_rv32im(
        """
        addi x0, x0, 0
        auipc x3, 0x12345
        sw x3, 0(x0)
        """
    )
    program = {4 * index: word for index, word in enumerate(program_words)}

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = program[0]
    dut.data_read_data.value = 0x00000000
    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected reset instr_addr=0x00000000, "
        f"observed 0x{int(dut.instr_addr.value):08X}"
    )

    dut.clk.value = 1
    await Timer(1, unit="ns")
    dut.clk.value = 0
    await Timer(1, unit="ns")
    dut.rst.value = 0
    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected instr_addr=0x00000000 after reset release, "
        f"observed 0x{int(dut.instr_addr.value):08X}"
    )

    committed_memory = {}

    for pc in (0x00000000, 0x00000004, 0x00000008):
        assert int(dut.instr_addr.value) == pc, (
            f"Expected instr_addr=0x{pc:08X}, "
            f"observed 0x{int(dut.instr_addr.value):08X}"
        )
        dut.instr_data.value = program[pc]
        await Timer(1, unit="ns")

        if pc == 0x00000008:
            observed_write = int(dut.data_write.value)
            observed_addr = int(dut.data_addr.value)
            observed_width = int(dut.data_width.value)
            observed_data = int(dut.data_write_data.value)
            assert observed_write == 1, (
                f"Expected data_write=1, observed {observed_write}"
            )
            assert observed_addr == 0x00000000, (
                f"Expected store address=0x00000000, "
                f"observed 0x{observed_addr:08X}"
            )
            assert observed_width == 0x2, (
                f"Expected data_width=0x2, observed 0x{observed_width:X}"
            )
            assert observed_data == 0x12345004, (
                f"Expected AUIPC store data=0x12345004, "
                f"observed 0x{observed_data:08X}"
            )
        else:
            observed_write = int(dut.data_write.value)
            assert observed_write == 0, (
                f"Expected data_write=0 at PC 0x{pc:08X}, "
                f"observed {observed_write}"
            )

        dut.clk.value = 1
        await Timer(1, unit="ns")
        if pc == 0x00000008 and observed_write:
            committed_memory[observed_addr] = observed_data
        dut.clk.value = 0
        await Timer(1, unit="ns")

    assert committed_memory.get(0x00000000) == 0x12345004, (
        f"Expected memory[0x00000000]=0x12345004, "
        f"observed 0x{committed_memory.get(0x00000000, 0):08X}"
    )
