from pathlib import Path
import struct

from spec_riscv_test.elf import load


def test_loads_a_minimal_riscv_elf(tmp_path: Path):
    path = tmp_path / "test.elf"
    header = struct.pack("<16sHHIIIIIHHHHHH", b"\x7fELF\x01\x01" + b"\0" * 10, 2, 243, 1, 0, 52, 0, 0, 52, 32, 1, 40, 0, 0)
    segment = struct.pack("<IIIIIIII", 1, 84, 0, 0, 4, 4, 5, 4)
    path.write_bytes(header + segment + b"\0" * (84 - 52 - 32) + b"\x13\0\0\0")
    image = load(path)
    assert image.entry == 0
    assert image.memory == {0: 0x13, 1: 0, 2: 0, 3: 0}
