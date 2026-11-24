import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


def assemble_rv32im(source):
    """Assemble the instruction subset used by this directed RV32I program."""
    instructions = []
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
        instructions.append((pc, line))
        pc += 4

    def register(token):
        token = token.strip().lower()
        if not token.startswith("x"):
            raise ValueError(f"Expected a register, got {token}")
        number = int(token[1:])
        if not 0 <= number <= 31:
            raise ValueError(f"Register index out of range: {token}")
        return number

    program = {}
    for address, line in instructions:
        parts = line.replace(",", " ").split()
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
        elif mnemonic == "bgeu":
            rs1, rs2 = register(parts[1]), register(parts[2])
            offset = labels[parts[3]] - address
            if offset & 1 or not -(1 << 12) <= offset < (1 << 12):
                raise ValueError(f"BGEU target out of range: {parts[3]}")
            immediate = offset & 0x1FFF
            word = (
                (((immediate >> 12) & 1) << 31)
                | (((immediate >> 5) & 0x3F) << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (0b111 << 12)
                | (((immediate >> 1) & 0xF) << 8)
                | (((immediate >> 11) & 1) << 7)
                | 0x63
            )
        elif mnemonic == "jal":
            rd = register(parts[1])
            offset = labels[parts[2]] - address
            if offset & 1 or not -(1 << 20) <= offset < (1 << 20):
                raise ValueError(f"JAL target out of range: {parts[2]}")
            immediate = offset & 0x1FFFFF
            word = (
                (((immediate >> 20) & 1) << 31)
                | (((immediate >> 1) & 0x3FF) << 21)
                | (((immediate >> 11) & 1) << 20)
                | (((immediate >> 12) & 0xFF) << 12)
                | (rd << 7)
                | 0x6F
            )
        elif mnemonic == "sw":
            rs2, rs1 = register(parts[1]), None
            offset_and_base = parts[2]
            offset_text, base_text = offset_and_base.split("(", 1)
            immediate = int(offset_text, 0) & 0xFFF
            rs1 = register(base_text.rstrip(")"))
            word = (
                (((immediate >> 5) & 0x7F) << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (0b010 << 12)
                | ((immediate & 0x1F) << 7)
                | 0x23
            )
        else:
            raise ValueError(f"Unsupported instruction in test program: {mnemonic}")

        program[address] = word

    return program


@cocotb.test()
async def bgeu_unsigned_comparison_reaches_success_store(dut):
    program = assemble_rv32im(
        """
        addi x1, x0, -1
        addi x2, x0, 1
        bgeu x1, x2, success
    halt:
        jal x0, halt
    success:
        addi x3, x0, 42
        sw x3, 0(x0)
    done:
        jal x0, done
        """
    )

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0
    dut.data_read_data.value = 0

    Clock(dut.clk, 10, unit="ns").start()
    await Timer(2, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected reset instr_addr=0x00000000, observed "
        f"0x{int(dut.instr_addr.value):08X}"
    )
    dut.rst.value = 0

    committed_store = False
    for _ in range(12):
        address = int(dut.instr_addr.value)
        assert address in program, (
            f"Expected a program instruction at 0x{address:08X}"
        )
        dut.instr_data.value = program[address]
        await Timer(1, unit="ns")

        if int(dut.data_write.value):
            observed_address = int(dut.data_addr.value)
            observed_width = int(dut.data_width.value)
            observed_data = int(dut.data_write_data.value)
            assert observed_address == 0x00000000, (
                f"Expected store address 0x00000000, observed "
                f"0x{observed_address:08X}"
            )
            assert observed_width == 0x2, (
                f"Expected word-store width 0x2, observed 0x{observed_width:X}"
            )
            assert observed_data == 0x0000002A, (
                f"Expected store data 0x0000002A, observed 0x{observed_data:08X}"
            )

            await RisingEdge(dut.clk)
            await Timer(1, unit="ns")
            committed_store = True
            break

        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")

    assert committed_store, (
        "Expected the unsigned BGEU comparison to reach the success store "
        "with address 0x00000000, width 0x2, and data 0x0000002A"
    )
