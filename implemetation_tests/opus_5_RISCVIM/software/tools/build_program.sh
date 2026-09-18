#!/bin/sh
# =============================================================================
# build_program.sh -- assembly -> ELF -> disassembly -> binary -> .rm -> ROM pkg
# REQ: FR-13 (design) / pipeline:FR-20, pipeline:FR-21
#
# Runs inside the project toolchain image (docker/Dockerfile, NFR-05): no
# hardcoded local toolchain path, no manual step. Every derived artifact comes
# from a tool -- the .rm and the disassembly are never written by hand.
#
# Usage:
#   build_program.sh <src_dir> <out_dir> <march> [mabi]
#
# <src_dir> must contain program.S and linker.ld.
# =============================================================================
set -e

SRC_DIR=$1
OUT_DIR=$2
MARCH=$3
MABI=${4:-ilp32}

if [ -z "$SRC_DIR" ] || [ -z "$OUT_DIR" ] || [ -z "$MARCH" ]; then
    echo "usage: build_program.sh <src_dir> <out_dir> <march> [mabi]" >&2
    exit 2
fi

TOOLS_DIR=$(cd "$(dirname "$0")" && pwd)
AS=riscv64-unknown-elf-as
LD=riscv64-unknown-elf-ld
OBJDUMP=riscv64-unknown-elf-objdump
OBJCOPY=riscv64-unknown-elf-objcopy

mkdir -p "$OUT_DIR/build"

echo "== assembling ($MARCH / $MABI)"
# -mno-relax / --no-relax are mandatory here, not a style choice: RISC-V linker
# relaxation rewrites `auipc/lui + offset` address formation into a single
# gp/x0-relative instruction, deleting the very instruction the coverage
# contract requires the CPU to retire (pipeline:FR-26). With relaxation on, the
# base test silently stops exercising auipc/lui for .rodata access.
$AS -march="$MARCH" -mabi="$MABI" -mno-relax -o "$OUT_DIR/build/program.o" "$SRC_DIR/program.S"

echo "== linking"
$LD -m elf32lriscv --no-relax -T "$SRC_DIR/linker.ld" -o "$OUT_DIR/build/program.elf" "$OUT_DIR/build/program.o"

echo "== disassembling (conference copy)"
$OBJDUMP -d -M no-aliases,numeric "$OUT_DIR/build/program.elf" > "$OUT_DIR/build/program.dasm"

# The symbol table is a separate artifact because `objdump -d` only walks code
# sections: .rodata symbols (the constants the base test must read through
# auipc/lui) have no disassembly line, so the testbench needs -t to locate them.
echo "== symbol table"
$OBJDUMP -t "$OUT_DIR/build/program.elf" > "$OUT_DIR/build/program.sym"

echo "== extracting raw image"
$OBJCOPY -O binary "$OUT_DIR/build/program.elf" "$OUT_DIR/build/program.bin"

echo "== bin -> .rm"
python3 "$TOOLS_DIR/bin_to_rm.py" "$OUT_DIR/build/program.bin" "$OUT_DIR/program.rm" \
    --origin 0x00000000 --source "$(basename "$OUT_DIR")/build/program.elf"

echo "== .rm -> rom_image_pkg.vhd"
python3 "$TOOLS_DIR/rm_to_rom_pkg.py" "$OUT_DIR/program.rm" "$OUT_DIR/rom_image_pkg.vhd" --size 1024

# REQ: pipeline:FR-20 -- record march/mabi/assembler version with the artifacts
{
    echo "march=$MARCH"
    echo "mabi=$MABI"
    echo "assembler=$($AS --version | head -1)"
    echo "linker=$($LD --version | head -1)"
    echo "objdump=$($OBJDUMP --version | head -1)"
    echo "objcopy=$($OBJCOPY --version | head -1)"
} > "$OUT_DIR/build/toolchain.txt"

echo "== done: $OUT_DIR"
