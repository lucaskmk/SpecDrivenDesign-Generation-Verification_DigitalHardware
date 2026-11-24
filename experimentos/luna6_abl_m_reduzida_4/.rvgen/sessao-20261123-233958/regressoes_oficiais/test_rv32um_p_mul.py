import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


def assemble_rv32im(source):
    """Assemble the small RV32IM subset used by this program."""
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

    def register(text):
        text = text.strip().lower()
        if not text.startswith("x"):
            raise ValueError(f"Expected register, got {text}")
        value = int(text[1:])
        if not 0 <= value <= 31:
            raise ValueError(f"Register out of range: {text}")
        return value

    words = []
    for instruction_pc, line in lines:
        mnemonic, _, operands_text = line.partition(" ")
        operands = [part.strip() for part in operands_text.split(",")]

        if mnemonic == "addi":
            rd, rs1 = register(operands[0]), register(operands[1])
            imm = int(operands[2], 0)
            if not -2048 <= imm <= 2047:
                raise ValueError("ADDI immediate out of range")
            word = (
                ((imm & 0xFFF) << 20)
                | (rs1 << 15)
                | (rd << 7)
                | 0x13
            )
        elif mnemonic == "mul":
            rd = register(operands[0])
            rs1 = register(operands[1])
            rs2 = register(operands[2])
            word = (0x01 << 25) | (rs2 << 20) | (rs1 << 15) | (rd << 7) | 0x33
        elif mnemonic == "sw":
            rs2 = register(operands[0])
            offset_text, base_text = operands[1].split("(", 1)
            imm = int(offset_text, 0)
            rs1 = register(base_text.rstrip(")"))
            if not -2048 <= imm <= 2047:
                raise ValueError("SW immediate out of range")
            encoded_imm = imm & 0xFFF
            word = (
                ((encoded_imm >> 5) << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (0x2 << 12)
                | ((encoded_imm & 0x1F) << 7)
                | 0x23
            )
        elif mnemonic == "jal":
            rd = register(operands[0])
            target = labels[operands[1]]
            offset = target - instruction_pc
            if offset & 1 or not -(1 << 20) <= offset < (1 << 20):
                raise ValueError("JAL target out of range")
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
            raise ValueError(f"Unsupported instruction: {mnemonic}")

        words.append(word & 0xFFFFFFFF)

    return words


@cocotb.test()
async def rv32um_mul_case_36_stores_expected_result(dut):
    program = assemble_rv32im(
        """
        addi x1, x0, -1
        addi x2, x0, 1
        mul x3, x1, x2
        sw x3, 0(x0)
    halt: jal x0, halt
        """
    )
    rom = {address: word for address, word in enumerate(program) for address in [address * 4]}

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000

    clock = Clock(dut.clk, 10, unit="ns")
    cocotb.start_soon(clock.start())

    await Timer(1, unit="ns")
    reset_pc = int(dut.instr_addr.value)
    assert reset_pc == 0x00000000, (
        f"Expected reset instr_addr=0x00000000, observed 0x{reset_pc:08X}"
    )
    dut.rst.value = 0

    memory = {}
    for expected_pc in (0x00000000, 0x00000004, 0x00000008, 0x0000000C):
        observed_pc = int(dut.instr_addr.value)
        assert observed_pc == expected_pc, (
            f"Expected instr_addr=0x{expected_pc:08X}, observed 0x{observed_pc:08X}"
        )
        dut.instr_data.value = rom[expected_pc]
        await Timer(1, unit="ns")

        is_store = expected_pc == 0x0000000C
        if is_store:
            write = int(dut.data_write.value)
            address = int(dut.data_addr.value)
            width = int(dut.data_width.value)
            write_data = int(dut.data_write_data.value)
            assert write == 1, f"Expected data_write=1, observed {write}"
            assert address == 0x00000000, (
                f"Expected store address=0x00000000, observed 0x{address:08X}"
            )
            assert width == 0x2, f"Expected data_width=0x2, observed 0x{width:X}"
            assert write_data == 0xFFFFFFFF, (
                f"Expected store data=0xFFFFFFFF, observed 0x{write_data:08X}"
            )

        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")

        if is_store:
            memory[address & 0xFFFFFFFC] = write_data
            committed = memory[0x00000000]
            assert committed == 0xFFFFFFFF, (
                f"Expected committed word=0xFFFFFFFF, observed 0x{committed:08X}"
            )
