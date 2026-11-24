import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


def assemble_rv32im(source):
    """Assemble the small RV32IM instruction subset used by this test."""
    instructions = []
    labels = {}
    pc = 0

    for raw_line in source.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue

        if ":" in line:
            label, remainder = line.split(":", 1)
            labels[label.strip()] = pc
            line = remainder.strip()
            if not line:
                continue

        instructions.append((pc, line))
        pc += 4

    def reg(text):
        text = text.strip().lower()
        if not text.startswith("x"):
            raise ValueError(f"Expected register, got {text}")
        value = int(text[1:])
        if not 0 <= value <= 31:
            raise ValueError(f"Register out of range: {text}")
        return value

    words = {}
    for address, line in instructions:
        mnemonic, _, operand_text = line.partition(" ")
        operands = [part.strip() for part in operand_text.split(",")]

        if mnemonic == "addi":
            rd, rs1, imm = reg(operands[0]), reg(operands[1]), int(operands[2], 0)
            if not -2048 <= imm <= 2047:
                raise ValueError(f"ADDI immediate out of range: {imm}")
            words[address] = (
                ((imm & 0xFFF) << 20)
                | (rs1 << 15)
                | (rd << 7)
                | 0x13
            )

        elif mnemonic == "div":
            rd, rs1, rs2 = reg(operands[0]), reg(operands[1]), reg(operands[2])
            words[address] = (
                (0x01 << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (0x4 << 12)
                | (rd << 7)
                | 0x33
            )

        elif mnemonic == "sw":
            rs2 = reg(operands[0])
            offset_text, base_text = operands[1].split("(", 1)
            imm = int(offset_text.strip(), 0)
            rs1 = reg(base_text.rstrip(")"))
            if not -2048 <= imm <= 2047:
                raise ValueError(f"SW immediate out of range: {imm}")
            imm &= 0xFFF
            words[address] = (
                (((imm >> 5) & 0x7F) << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (0x2 << 12)
                | ((imm & 0x1F) << 7)
                | 0x23
            )

        elif mnemonic == "jal":
            rd = reg(operands[0])
            target = labels[operands[1]]
            imm = target - address
            if imm & 1 or not -(1 << 20) <= imm < (1 << 20):
                raise ValueError(f"JAL target out of range or unaligned: {target}")
            encoded_imm = imm & 0x1FFFFF
            words[address] = (
                (((encoded_imm >> 20) & 0x1) << 31)
                | (((encoded_imm >> 1) & 0x3FF) << 21)
                | (((encoded_imm >> 11) & 0x1) << 20)
                | (((encoded_imm >> 12) & 0xFF) << 12)
                | (rd << 7)
                | 0x6F
            )

        else:
            raise ValueError(f"Unsupported instruction in test program: {mnemonic}")

    return words


@cocotb.test()
async def div_by_zero_writes_all_ones(dut):
    program_source = """
        addi x1, x0, 0
        addi x2, x0, 0
        div  x3, x1, x2
        sw   x3, 0(x0)
    halt: jal  x0, halt
    """
    program = assemble_rv32im(program_source)

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000
    Clock(dut.clk, 10, unit="ns").start(start_high=False)

    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected reset PC=0x00000000, observed 0x{int(dut.instr_addr.value):08X}"
    )
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    dut.rst.value = 0

    committed_memory = {}
    for _ in range(len(program)):
        pc = int(dut.instr_addr.value)
        assert pc in program, f"Expected a program instruction at PC=0x{pc:08X}"
        dut.instr_data.value = program[pc]
        await Timer(1, unit="ns")

        if pc == 0x0000000C:
            assert int(dut.data_write.value) == 1, (
                f"Expected store enable=1, observed {int(dut.data_write.value)}"
            )
            assert int(dut.data_addr.value) == 0x00000000, (
                f"Expected store address=0x00000000, observed "
                f"0x{int(dut.data_addr.value):08X}"
            )
            assert int(dut.data_width.value) == 0x2, (
                f"Expected store width=0x2, observed 0x{int(dut.data_width.value):X}"
            )
            store_value = int(dut.data_write_data.value)
            assert store_value == 0xFFFFFFFF, (
                f"Expected DIV-by-zero result 0xFFFFFFFF, observed 0x{store_value:08X}"
            )

        await RisingEdge(dut.clk)
        if pc == 0x0000000C:
            committed_memory[0x00000000] = store_value
        await Timer(1, unit="ns")

    observed = committed_memory.get(0x00000000)
    assert observed == 0xFFFFFFFF, (
        f"Expected final stored result 0xFFFFFFFF, observed "
        f"{'no store' if observed is None else f'0x{observed:08X}'}"
    )
