import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


def assemble_rv32im(source):
    """Assemble the RV32IM instructions used by this test's legal source."""
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

        mnemonic, operands_text = line.split(None, 1)
        operands = [item.strip() for item in operands_text.split(",")]
        mnemonic = mnemonic.lower()

        if mnemonic == "lui":
            rd = reg(operands[0])
            immediate = int(operands[1], 0)
            if not 0 <= immediate <= 0xFFFFF:
                raise ValueError("LUI immediate must fit in 20 bits")
            word = (immediate << 12) | (rd << 7) | 0x37

        elif mnemonic in ("addi", "ori"):
            rd = reg(operands[0])
            rs1 = reg(operands[1])
            immediate = int(operands[2], 0)
            if not -2048 <= immediate <= 4095:
                raise ValueError("I-type immediate must fit in 12 bits")
            funct3 = 0x0 if mnemonic == "addi" else 0x6
            word = (
                ((immediate & 0xFFF) << 20)
                | (rs1 << 15)
                | (funct3 << 12)
                | (rd << 7)
                | 0x13
            )

        elif mnemonic == "sw":
            rs2 = reg(operands[0])
            address = operands[1]
            immediate_text, base_text = address.split("(", 1)
            immediate = int(immediate_text.strip(), 0)
            rs1 = reg(base_text.rstrip(")").strip())
            if not -2048 <= immediate <= 2047:
                raise ValueError("S-type immediate must fit in signed 12 bits")
            encoded_imm = immediate & 0xFFF
            word = (
                (((encoded_imm >> 5) & 0x7F) << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (0x2 << 12)
                | ((encoded_imm & 0x1F) << 7)
                | 0x23
            )

        else:
            raise ValueError(f"Unsupported instruction in test source: {mnemonic}")

        words.append(word)

    return words


@cocotb.test()
async def ori_sign_extends_its_immediate_before_the_or(dut):
    program = assemble_rv32im(
        """
        lui  x1, 0xFF010
        addi x1, x1, -256
        ori  x2, x1, 0xF0F
        sw   x2, 0(x0)
        """
    )

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await Timer(2, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected reset instr_addr=0x00000000, "
        f"observed 0x{int(dut.instr_addr.value):08X}"
    )
    dut.rst.value = 0

    committed_stores = []
    for index, instruction in enumerate(program):
        expected_pc = index * 4
        observed_pc = int(dut.instr_addr.value)
        assert observed_pc == expected_pc, (
            f"Expected instr_addr=0x{expected_pc:08X}, "
            f"observed 0x{observed_pc:08X}"
        )

        dut.instr_data.value = instruction
        await Timer(1, unit="ns")

        if index == len(program) - 1:
            assert int(dut.data_write.value) == 1, (
                "Expected the final SW to assert data_write=1, "
                f"observed {int(dut.data_write.value)}"
            )
            assert int(dut.data_addr.value) == 0x00000000, (
                f"Expected store address 0x00000000, "
                f"observed 0x{int(dut.data_addr.value):08X}"
            )
            assert int(dut.data_width.value) == 0x2, (
                f"Expected word width 0x2, "
                f"observed 0x{int(dut.data_width.value):X}"
            )
            store_data = int(dut.data_write_data.value)
            assert store_data == 0xFFFFFFFF, (
                f"Expected ORI result/store data 0xFFFFFFFF, "
                f"observed 0x{store_data:08X}"
            )

        await RisingEdge(dut.clk)
        if index == len(program) - 1:
            committed_stores.append(
                (
                    int(dut.data_addr.value),
                    int(dut.data_width.value),
                    int(dut.data_write_data.value),
                )
            )
        await Timer(1, unit="ns")

    assert committed_stores == [(0x00000000, 0x2, 0xFFFFFFFF)], (
        "Expected exactly one committed word store "
        "(address=0x00000000, width=0x2, data=0xFFFFFFFF), "
        f"observed {committed_stores}"
    )
