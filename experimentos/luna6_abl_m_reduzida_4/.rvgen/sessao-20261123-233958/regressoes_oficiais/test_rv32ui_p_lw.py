import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer


def assemble_rv32im(source):
    """Assemble the small RV32I source program used by this test."""
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

    def reg(text):
        text = text.strip().lower()
        if not text.startswith("x"):
            raise ValueError(f"Expected register, got {text}")
        index = int(text[1:], 0)
        if not 0 <= index < 32:
            raise ValueError(f"Register out of range: {text}")
        return index

    words = {}
    for address, line in lines:
        mnemonic, operands_text = line.split(None, 1)
        operands = [part.strip() for part in operands_text.split(",")]
        mnemonic = mnemonic.lower()

        if mnemonic == "addi":
            rd, rs1 = reg(operands[0]), reg(operands[1])
            imm = int(operands[2], 0) & 0xFFF
            word = (imm << 20) | (rs1 << 15) | (rd << 7) | 0x13
        elif mnemonic in ("lw", "sw"):
            reg_field = reg(operands[0])
            offset_text, base_text = operands[1].split("(", 1)
            imm = int(offset_text.strip(), 0) & 0xFFF
            base = reg(base_text.rstrip(")"))
            if mnemonic == "lw":
                word = (imm << 20) | (base << 15) | (2 << 12) | (reg_field << 7) | 0x03
            else:
                word = (
                    ((imm >> 5) << 25)
                    | (reg_field << 20)
                    | (base << 15)
                    | (2 << 12)
                    | ((imm & 0x1F) << 7)
                    | 0x23
                )
        elif mnemonic == "jal":
            rd = reg(operands[0])
            target = labels[operands[1]]
            imm = (target - address) & 0x1FFFFF
            word = (
                (((imm >> 20) & 1) << 31)
                | (((imm >> 1) & 0x3FF) << 21)
                | (((imm >> 11) & 1) << 20)
                | (((imm >> 12) & 0xFF) << 12)
                | (rd << 7)
                | 0x6F
            )
        else:
            raise ValueError(f"Unsupported instruction in test program: {mnemonic}")

        words[address] = word

    return words


@cocotb.test()
async def lw_preserves_word_value_at_nonzero_base_offset(dut):
    program = assemble_rv32im(
        """
        addi x1, x0, 256
        lw   x2, 4(x1)
        sw   x2, 8(x1)
    halt:
        jal  x0, halt
        """
    )

    source_address = 0x00000104
    result_address = 0x00000108
    expected_word = 0xFF00FF00
    memory = {
        source_address + lane: (expected_word >> (8 * lane)) & 0xFF
        for lane in range(4)
    }

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000
    Clock(dut.clk, 10, unit="ns").start()

    await Timer(1, unit="ns")
    observed_pc = int(dut.instr_addr.value)
    assert observed_pc == 0x00000000, (
        f"Expected reset instr_addr=0x00000000, observed 0x{observed_pc:08X}"
    )

    await FallingEdge(dut.clk)
    dut.rst.value = 0

    saw_load = False
    saw_result_store = False
    store_count = 0

    for _ in range(8):
        await FallingEdge(dut.clk)
        pc = int(dut.instr_addr.value)
        assert pc in program, f"Expected a program instruction at PC=0x{pc:08X}"
        dut.instr_data.value = program[pc]
        await Timer(1, unit="ns")

        address = int(dut.data_addr.value)
        aligned_address = address & 0xFFFFFFFC
        read_word = sum(
            memory.get(aligned_address + lane, 0) << (8 * lane)
            for lane in range(4)
        )
        dut.data_read_data.value = read_word
        await Timer(1, unit="ns")

        if pc == 0x00000004:
            saw_load = True
            observed_address = int(dut.data_addr.value)
            observed_width = int(dut.data_width.value)
            observed_write = int(dut.data_write.value)
            assert observed_address == source_address, (
                f"Expected LW address=0x{source_address:08X}, "
                f"observed 0x{observed_address:08X}"
            )
            assert observed_width == 0x2, (
                f"Expected LW width=0x2, observed 0x{observed_width:X}"
            )
            assert observed_write == 0, (
                f"Expected data_write=0 for LW, observed {observed_write}"
            )

        if pc == 0x00000008:
            observed_write = int(dut.data_write.value)
            observed_address = int(dut.data_addr.value)
            observed_width = int(dut.data_width.value)
            observed_data = int(dut.data_write_data.value)
            assert observed_write == 1, (
                f"Expected data_write=1 for result store, observed {observed_write}"
            )
            assert observed_address == result_address, (
                f"Expected store address=0x{result_address:08X}, "
                f"observed 0x{observed_address:08X}"
            )
            assert observed_width == 0x2, (
                f"Expected store width=0x2, observed 0x{observed_width:X}"
            )
            assert observed_data == expected_word, (
                f"Expected stored LW result=0x{expected_word:08X}, "
                f"observed 0x{observed_data:08X}"
            )
            saw_result_store = True
            store_count += 1

        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")

        if pc == 0x00000008:
            for lane in range(4):
                memory[result_address + lane] = (observed_data >> (8 * lane)) & 0xFF

        if pc == 0x0000000C:
            break

    assert saw_load, "Expected the program to execute the focal LW"
    assert saw_result_store, "Expected the program to store the loaded word"
    assert store_count == 1, f"Expected exactly one result store, observed {store_count}"
    stored_word = sum(
        memory.get(result_address + lane, 0) << (8 * lane)
        for lane in range(4)
    )
    assert stored_word == expected_word, (
        f"Expected memory result=0x{expected_word:08X}, observed 0x{stored_word:08X}"
    )
