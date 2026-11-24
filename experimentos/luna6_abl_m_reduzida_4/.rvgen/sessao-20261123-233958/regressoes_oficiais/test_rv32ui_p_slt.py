import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


def assemble_rv32im(source):
    """Assemble the small RV32I subset used by this test, resolving labels."""
    lines = []
    labels = {}
    address = 0

    for raw_line in source.splitlines():
        line = raw_line.split("#", 1)[0].strip().lower()
        if not line:
            continue
        if ":" in line:
            label, line = line.split(":", 1)
            labels[label.strip()] = address
            line = line.strip()
            if not line:
                continue
        lines.append((address, line))
        address += 4

    def reg_index(token):
        token = token.strip()
        if not token.startswith("x"):
            raise ValueError(f"Expected register, got {token}")
        return int(token[1:])

    program = {}
    for pc, line in lines:
        mnemonic, operands_text = line.split(None, 1)
        operands = [operand.strip() for operand in operands_text.split(",")]

        if mnemonic == "addi":
            rd, rs1, imm = reg_index(operands[0]), reg_index(operands[1]), int(operands[2], 0)
            word = (
                ((imm & 0xFFF) << 20)
                | (rs1 << 15)
                | (0 << 12)
                | (rd << 7)
                | 0x13
            )
        elif mnemonic == "slt":
            rd, rs1, rs2 = map(reg_index, operands)
            word = (
                (rs2 << 20)
                | (rs1 << 15)
                | (2 << 12)
                | (rd << 7)
                | 0x33
            )
        elif mnemonic == "sw":
            rs2 = reg_index(operands[0])
            offset_text, base_text = operands[1].split("(", 1)
            imm = int(offset_text.strip(), 0)
            rs1 = reg_index(base_text.rstrip(")"))
            imm &= 0xFFF
            word = (
                (((imm >> 5) & 0x7F) << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (2 << 12)
                | ((imm & 0x1F) << 7)
                | 0x23
            )
        elif mnemonic == "jal":
            rd = reg_index(operands[0])
            target = labels[operands[1]]
            imm = target - pc
            word = (
                (((imm >> 20) & 1) << 31)
                | (((imm >> 1) & 0x3FF) << 21)
                | (((imm >> 11) & 1) << 20)
                | (((imm >> 12) & 0xFF) << 12)
                | (rd << 7)
                | 0x6F
            )
        else:
            raise ValueError(f"Unsupported instruction: {mnemonic}")

        program[pc] = word & 0xFFFFFFFF

    return program


@cocotb.test()
async def slt_write_to_x0_preserves_zero(dut):
    program = assemble_rv32im(
        """
        addi x16, x0, 16
        addi x30, x0, 30
        slt  x0, x16, x30
        sw   x0, 0(x0)
    halt: jal  x0, halt
        """
    )

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000

    clock = Clock(dut.clk, 10, unit="ns")
    clock.start()
    await Timer(2, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected reset PC 0x00000000, observed 0x{int(dut.instr_addr.value):08X}"
    )
    dut.rst.value = 0

    external_memory = {}
    store_observed = False

    for _ in range(len(program) + 1):
        pc = int(dut.instr_addr.value)
        assert pc in program, f"Expected a program address, observed 0x{pc:08X}"
        dut.instr_data.value = program[pc]
        await Timer(1, unit="ns")

        if int(dut.data_write.value) == 1:
            observed_addr = int(dut.data_addr.value)
            observed_width = int(dut.data_width.value)
            observed_data = int(dut.data_write_data.value)
            assert observed_addr == 0x00000000, (
                f"Expected store address 0x00000000, observed 0x{observed_addr:08X}"
            )
            assert observed_width == 0x2, (
                f"Expected store width 0x2, observed 0x{observed_width:X}"
            )
            assert observed_data == 0x00000000, (
                f"Expected store data 0x00000000, observed 0x{observed_data:08X}"
            )
            store_observed = True

        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")

        if store_observed:
            external_memory[observed_addr] = observed_data
            break

    assert store_observed, "Expected the final SW transaction after SLT to x0"
    assert external_memory[0x00000000] == 0x00000000, (
        f"Expected memory[0x00000000]=0x00000000, "
        f"observed 0x{external_memory[0x00000000]:08X}"
    )
