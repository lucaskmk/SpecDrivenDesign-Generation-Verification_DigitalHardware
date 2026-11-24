import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


def assemble_rv32im(source):
    """Assemble the small RV32IM source subset used by this test."""
    labels = {}
    instructions = []
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
        instructions.append((pc, line))
        pc += 4

    program = {}
    for address, line in instructions:
        parts = line.replace(",", " ").split()
        mnemonic = parts[0].lower()

        if mnemonic == "rem":
            rd, rs1, rs2 = (int(register[1:]) for register in parts[1:4])
            word = (
                (0x01 << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (0x06 << 12)
                | (rd << 7)
                | 0x33
            )
        elif mnemonic == "sw":
            rs2 = int(parts[1][1:])
            immediate, base = parts[2].split("(", 1)
            immediate = int(immediate, 0)
            rs1 = int(base.rstrip(")")[1:])
            if not -2048 <= immediate <= 2047:
                raise ValueError("SW immediate is out of range")
            imm = immediate & 0xFFF
            word = (
                ((imm >> 5) << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (0x02 << 12)
                | ((imm & 0x1F) << 7)
                | 0x23
            )
        elif mnemonic == "jal":
            rd = int(parts[1][1:])
            target = labels[parts[2]]
            immediate = target - address
            if immediate & 1 or not -(1 << 20) <= immediate < (1 << 20):
                raise ValueError("JAL target is out of range or unaligned")
            imm = immediate & 0x1FFFFF
            word = (
                (((imm >> 20) & 1) << 31)
                | (((imm >> 1) & 0x3FF) << 21)
                | (((imm >> 11) & 1) << 20)
                | (((imm >> 12) & 0xFF) << 12)
                | (rd << 7)
                | 0x6F
            )
        else:
            raise ValueError(f"Unsupported instruction in test source: {mnemonic}")

        program[address] = word

    return program


@cocotb.test()
async def rem_zero_divisor_stores_zero(dut):
    assembly = """
        rem x3, x0, x0
        sw x3, 0(x0)
    halt:
        jal x0, halt
    """
    program = assemble_rv32im(assembly)

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = program[0]
    dut.data_read_data.value = 0
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    await Timer(2, unit="ns")
    observed_pc = int(dut.instr_addr.value)
    assert observed_pc == 0x00000000, (
        f"Expected reset instr_addr=0x00000000, observed 0x{observed_pc:08X}"
    )

    dut.rst.value = 0
    await Timer(1, unit="ns")

    # Commit REM x3, x0, x0; the following store is the public witness.
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    observed_pc = int(dut.instr_addr.value)
    assert observed_pc == 0x00000004, (
        f"Expected instr_addr=0x00000004 after REM, observed 0x{observed_pc:08X}"
    )

    dut.instr_data.value = program[4]
    await Timer(1, unit="ns")

    observed_write = int(dut.data_write.value)
    observed_addr = int(dut.data_addr.value)
    observed_width = int(dut.data_width.value)
    observed_data = int(dut.data_write_data.value)
    assert observed_write == 1, (
        f"Expected data_write=1 for witness store, observed {observed_write}"
    )
    assert observed_addr == 0x00000000, (
        f"Expected store address=0x00000000, observed 0x{observed_addr:08X}"
    )
    assert observed_width == 0x2, (
        f"Expected data_width=0x2, observed 0x{observed_width:X}"
    )
    assert observed_data == 0x00000000, (
        f"Expected REM result/store data=0x00000000, observed 0x{observed_data:08X}"
    )

    # Minimal external memory model: commit the observed word store at the edge.
    memory = {}
    await RisingEdge(dut.clk)
    if observed_write:
        memory[observed_addr & 0xFFFFFFFC] = observed_data
    await Timer(1, unit="ns")

    observed_pc = int(dut.instr_addr.value)
    assert observed_pc == 0x00000008, (
        f"Expected instr_addr=0x00000008 after store, observed 0x{observed_pc:08X}"
    )
    observed_word = memory.get(0x00000000, 0xFFFFFFFF)
    assert observed_word == 0x00000000, (
        f"Expected memory[0x00000000]=0x00000000, observed 0x{observed_word:08X}"
    )

    dut.instr_data.value = program[8]
    await Timer(1, unit="ns")
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    observed_pc = int(dut.instr_addr.value)
    assert observed_pc == 0x00000008, (
        f"Expected halt loop instr_addr=0x00000008, observed 0x{observed_pc:08X}"
    )
