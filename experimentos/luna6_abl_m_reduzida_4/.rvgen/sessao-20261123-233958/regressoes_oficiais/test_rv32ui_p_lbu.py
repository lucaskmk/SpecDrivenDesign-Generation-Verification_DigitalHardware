import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


def assemble_rv32im(source):
    """Assemble the small legal RV32IM subset used by this test."""
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
        if not token.startswith("x"):
            raise ValueError(f"Expected an integer register, got {token}")
        index = int(token[1:])
        if not 0 <= index <= 31:
            raise ValueError(f"Register index out of range: {index}")
        return index

    words = {}
    for pc, line in lines:
        mnemonic, operands = line.split(None, 1)
        args = [arg.strip() for arg in operands.split(",")]

        if mnemonic == "addi":
            rd, rs1 = reg(args[0]), reg(args[1])
            imm = int(args[2], 0) & 0xFFF
            word = (imm << 20) | (rs1 << 15) | (0 << 12) | (rd << 7) | 0x13

        elif mnemonic == "lbu":
            rd = reg(args[0])
            imm_text, base_text = args[1].split("(", 1)
            imm = int(imm_text.strip(), 0) & 0xFFF
            rs1 = reg(base_text.rstrip(")").strip())
            word = (imm << 20) | (rs1 << 15) | (4 << 12) | (rd << 7) | 0x03

        elif mnemonic == "sw":
            rs2 = reg(args[0])
            imm_text, base_text = args[1].split("(", 1)
            imm = int(imm_text.strip(), 0) & 0xFFF
            rs1 = reg(base_text.rstrip(")").strip())
            word = (
                ((imm >> 5) << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (2 << 12)
                | ((imm & 0x1F) << 7)
                | 0x23
            )

        elif mnemonic == "jal":
            rd = reg(args[0])
            target = labels[args[1]]
            offset = (target - pc) & 0x1FFFFF
            word = (
                (((offset >> 20) & 1) << 31)
                | (((offset >> 1) & 0x3FF) << 21)
                | (((offset >> 11) & 1) << 20)
                | (((offset >> 12) & 0xFF) << 12)
                | (rd << 7)
                | 0x6F
            )

        else:
            raise ValueError(f"Unsupported instruction in test source: {mnemonic}")

        words[pc] = word

    return words


@cocotb.test()
async def lbu_zero_extends_the_selected_high_bit_byte(dut):
    program = assemble_rv32im(
        """
        addi x5, x0, 259
        lbu x2, 0(x5)
        addi x6, x0, 512
        sw x2, 0(x6)
    halt: jal x0, halt
        """
    )

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000
    Clock(dut.clk, 10, unit="ns").start(start_high=False)

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected reset instr_addr=0x00000000, "
        f"observed 0x{int(dut.instr_addr.value):08X}"
    )
    assert int(dut.data_write.value) == 0, (
        f"Expected data_write=0 during reset, observed {int(dut.data_write.value)}"
    )
    dut.rst.value = 0

    data_words = {0x00000100: 0xD36A91E7}
    committed_store = None

    for _ in range(5):
        pc = int(dut.instr_addr.value)
        assert pc in program, f"Expected a program instruction at PC 0x{pc:08X}"
        dut.instr_data.value = program[pc]
        dut.data_read_data.value = 0x00000000
        await Timer(1, unit="ns")

        address = int(dut.data_addr.value)
        if int(dut.data_write.value) == 0:
            dut.data_read_data.value = data_words.get(address & 0xFFFFFFFC, 0)
        await Timer(1, unit="ns")

        if pc == 0x00000004:
            assert address == 0x00000103, (
                f"Expected LBU byte address 0x00000103, observed 0x{address:08X}"
            )
            assert int(dut.data_width.value) == 0x0, (
                f"Expected LBU data_width=0x0, observed 0x{int(dut.data_width.value):X}"
            )
            assert int(dut.data_write.value) == 0, (
                f"Expected data_write=0 for LBU, observed {int(dut.data_write.value)}"
            )

        write = int(dut.data_write.value)
        store_address = int(dut.data_addr.value)
        store_width = int(dut.data_width.value)
        store_data = int(dut.data_write_data.value)

        await RisingEdge(dut.clk)
        if write:
            committed_store = (store_address, store_width, store_data)
            if store_width == 0x2:
                data_words[store_address & 0xFFFFFFFC] = store_data
        await Timer(1, unit="ns")

        if pc == 0x0000000C:
            assert committed_store == (0x00000200, 0x2, 0x000000D3), (
                "Expected final SW transaction "
                "(address=0x00000200, width=0x2, data=0x000000D3), "
                f"observed {committed_store}"
            )
            assert data_words.get(0x00000200) == 0x000000D3, (
                "Expected memory word at 0x00000200 to be 0x000000D3, "
                f"observed 0x{data_words.get(0x00000200, 0):08X}"
            )
            break
    else:
        assert False, "Expected the LBU result to reach the final store"
