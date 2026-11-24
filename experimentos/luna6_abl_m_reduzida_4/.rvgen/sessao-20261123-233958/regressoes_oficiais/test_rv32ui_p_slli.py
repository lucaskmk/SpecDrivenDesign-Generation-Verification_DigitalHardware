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

    def register(token):
        token = token.strip().lower()
        if not token.startswith("x"):
            raise ValueError(f"Expected integer register, got {token}")
        number = int(token[1:])
        if not 0 <= number < 32:
            raise ValueError(f"Register out of range: {token}")
        return number

    program = {}
    for address, line in instructions:
        parts = line.replace(",", " ").replace("(", " ").replace(")", " ").split()
        mnemonic = parts[0].lower()

        if mnemonic == "addi":
            rd, rs1 = register(parts[1]), register(parts[2])
            immediate = int(parts[3], 0) & 0xFFF
            word = (
                (immediate << 20)
                | (rs1 << 15)
                | (rd << 7)
                | 0x13
            )
        elif mnemonic == "slli":
            rd, rs1 = register(parts[1]), register(parts[2])
            shamt = int(parts[3], 0)
            if not 0 <= shamt < 32:
                raise ValueError(f"Invalid SLLI shift amount: {shamt}")
            word = (rs1 << 15) | (0x1 << 12) | (shamt << 20) | (rd << 7) | 0x13
        elif mnemonic == "sw":
            rs2, rs1 = register(parts[1]), register(parts[3])
            immediate = int(parts[2], 0) & 0xFFF
            word = (
                ((immediate >> 5) << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (0x2 << 12)
                | ((immediate & 0x1F) << 7)
                | 0x23
            )
        elif mnemonic == "jal":
            rd = register(parts[1])
            target = labels[parts[2]]
            immediate = (target - address) & 0x1FFFFF
            word = (
                (((immediate >> 20) & 0x1) << 31)
                | (((immediate >> 1) & 0x3FF) << 21)
                | (((immediate >> 11) & 0x1) << 20)
                | (((immediate >> 12) & 0xFF) << 12)
                | (rd << 7)
                | 0x6F
            )
        else:
            raise ValueError(f"Unsupported instruction in test source: {mnemonic}")

        program[address] = word

    return program


@cocotb.test()
async def slli_zero_shift_preserves_all_ones(dut):
    source = """
        addi x1, x0, -1
        slli x2, x1, 0
        sw x2, 0(x0)
    halt:
        jal x0, halt
    """
    program = assemble_rv32im(source)

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await Timer(2, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected reset instr_addr=0x00000000, observed 0x{int(dut.instr_addr.value):08X}"
    )

    dut.rst.value = 0
    memory = {}

    for expected_pc in (0x00000000, 0x00000004, 0x00000008):
        observed_pc = int(dut.instr_addr.value)
        assert observed_pc == expected_pc, (
            f"Expected instr_addr=0x{expected_pc:08X}, observed 0x{observed_pc:08X}"
        )

        dut.instr_data.value = program[observed_pc]
        await Timer(1, unit="ns")

        write = int(dut.data_write.value)
        if expected_pc == 0x00000008:
            assert write == 1, f"Expected store data_write=1, observed {write}"
            observed_addr = int(dut.data_addr.value)
            assert observed_addr == 0x00000000, (
                f"Expected store data_addr=0x00000000, observed 0x{observed_addr:08X}"
            )
            observed_width = int(dut.data_width.value)
            assert observed_width == 0x2, (
                f"Expected store data_width=0x2, observed 0x{observed_width:X}"
            )
            observed_data = int(dut.data_write_data.value)
            assert observed_data == 0xFFFFFFFF, (
                f"Expected store data=0xFFFFFFFF, observed 0x{observed_data:08X}"
            )

        write_addr = int(dut.data_addr.value)
        write_width = int(dut.data_width.value)
        write_data = int(dut.data_write_data.value)

        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")

        if write and not int(dut.rst.value):
            if write_width == 0x2:
                memory[write_addr] = write_data
            elif write_width == 0x1:
                memory[write_addr] = write_data & 0xFFFF
            else:
                memory[write_addr] = write_data & 0xFF

    assert memory.get(0x00000000) == 0xFFFFFFFF, (
        f"Expected memory[0x00000000]=0xFFFFFFFF, "
        f"observed 0x{memory.get(0x00000000, 0):08X}"
    )
