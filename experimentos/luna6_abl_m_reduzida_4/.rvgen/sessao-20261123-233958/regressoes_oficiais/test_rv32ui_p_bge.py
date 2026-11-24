import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble the small RV32IM subset used by this test, resolving labels."""
    labels = {}
    instructions = []
    pc = 0

    for raw_line in source.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if ":" in line:
            label, line = line.split(":", 1)
            labels[label.strip()] = pc
            line = line.strip()
            if not line:
                continue

        instructions.append((pc, line))
        pc += 4

    def reg_number(token):
        token = token.strip().lower()
        if not token.startswith("x"):
            raise ValueError(f"Expected register name, got {token}")
        number = int(token[1:])
        if not 0 <= number <= 31:
            raise ValueError(f"Register out of range: {token}")
        return number

    program = {}
    for address, line in instructions:
        mnemonic, operands_text = line.split(None, 1)
        operands = [part.strip() for part in operands_text.split(",")]
        mnemonic = mnemonic.lower()

        if mnemonic == "bge":
            rs1 = reg_number(operands[0])
            rs2 = reg_number(operands[1])
            offset = labels[operands[2]] - address
            imm = offset & 0x1FFF
            word = (
                (((imm >> 12) & 0x1) << 31)
                | (((imm >> 5) & 0x3F) << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (0b101 << 12)
                | (((imm >> 1) & 0xF) << 8)
                | (((imm >> 11) & 0x1) << 7)
                | 0x63
            )
        elif mnemonic == "sw":
            rs2 = reg_number(operands[0])
            offset_text, base_text = operands[1].split("(", 1)
            offset = int(offset_text.strip(), 0)
            rs1 = reg_number(base_text.rstrip(")").strip())
            imm = offset & 0xFFF
            word = (
                (((imm >> 5) & 0x7F) << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (0b010 << 12)
                | ((imm & 0x1F) << 7)
                | 0x23
            )
        elif mnemonic == "jal":
            rd = reg_number(operands[0])
            offset = labels[operands[1]] - address
            imm = offset & 0x1FFFFF
            word = (
                (((imm >> 20) & 0x1) << 31)
                | (((imm >> 1) & 0x3FF) << 21)
                | (((imm >> 11) & 0x1) << 20)
                | (((imm >> 12) & 0xFF) << 12)
                | (rd << 7)
                | 0x6F
            )
        else:
            raise ValueError(f"Unsupported instruction in test program: {mnemonic}")

        program[address] = word

    return program


@cocotb.test()
async def bge_takes_branch_for_equal_operands(dut):
    program = assemble_rv32im(
        """
        bge x0, x0, store
        jal x0, halt
    store: sw x0, 0(x0)
    halt: jal x0, halt
        """
    )

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000
    await Timer(1, unit="ns")

    observed_pc = int(dut.instr_addr.value)
    assert observed_pc == 0x00000000, (
        f"Expected reset instr_addr=0x00000000, observed 0x{observed_pc:08X}"
    )
    assert int(dut.data_write.value) == 0, "Expected data_write=0 during reset"

    dut.rst.value = 0
    await Timer(1, unit="ns")

    memory = {}
    store_seen = False

    for _ in range(12):
        pc = int(dut.instr_addr.value)
        assert pc in program, f"Expected a test-program instruction at PC=0x{pc:08X}"
        dut.instr_data.value = program[pc]
        await Timer(1, unit="ns")

        write = int(dut.data_write.value)
        if pc == 0x00000008:
            assert write == 1, (
                f"Expected the BGE-taken path to assert data_write=1 at PC=0x00000008, "
                f"observed {write}"
            )
            observed_addr = int(dut.data_addr.value)
            observed_width = int(dut.data_width.value)
            observed_data = int(dut.data_write_data.value)
            assert observed_addr == 0x00000000, (
                f"Expected store address=0x00000000, observed 0x{observed_addr:08X}"
            )
            assert observed_width == 0x2, (
                f"Expected word data_width=0x2, observed 0x{observed_width:X}"
            )
            assert observed_data == 0x00000000, (
                f"Expected store data=0x00000000, observed 0x{observed_data:08X}"
            )

            dut.clk.value = 1
            await Timer(1, unit="ns")
            memory[observed_addr] = observed_data
            dut.clk.value = 0
            await Timer(1, unit="ns")
            store_seen = True
            break

        assert write == 0, (
            f"Expected data_write=0 at PC=0x{pc:08X}, observed {write}"
        )
        dut.clk.value = 1
        await Timer(1, unit="ns")
        dut.clk.value = 0
        await Timer(1, unit="ns")

    assert store_seen, "Expected BGE with equal operands to take the branch and reach the store"
    observed_memory = memory.get(0x00000000)
    assert observed_memory == 0x00000000, (
        f"Expected committed word at 0x00000000 to be 0x00000000, "
        f"observed {observed_memory!r}"
    )
