from pathlib import Path

from spec_riscv_test.contract import validate_top


def test_accepts_the_required_top_level(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    ports = """clk : in std_logic; rst : in std_logic; instr_addr : out std_logic_vector(31 downto 0); instr_data : in std_logic_vector(31 downto 0); data_addr : out std_logic_vector(31 downto 0); data_write : out std_logic; data_width : out std_logic_vector(1 downto 0); data_write_data : out std_logic_vector(31 downto 0); data_read_data : in std_logic_vector(31 downto 0)"""
    top = src / "cpu.vhd"
    top.write_text(f"entity cpu is port({ports}); end cpu;", encoding="utf-8")
    assert validate_top(tmp_path) == top
