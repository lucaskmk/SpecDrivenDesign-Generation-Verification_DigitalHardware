#!/usr/bin/env python3
"""
check_dasm_coverage.py -- static check of a program disassembly against the
mnemonic list the program is contracted to cover.

REQ: pipeline:FR-18 (acceptance of T3b.1)

This is a *static* check on the objdump output: it only proves the mnemonic is
present in the image. It is NOT the coverage gate of phase 4b -- that one is
dynamic, measured from what the CPU actually retired (dbg_valid + dbg_instr),
because assembly text can contain dead code (pipeline:FR-26, principle 10).

Usage:
    check_dasm_coverage.py <program.dasm> <instructions.json>
"""
import json
import re
import sys

# objdump -d -M no-aliases,numeric lines look like:
#    2c:\t0031a023          \tsw\tx3,0(x3)
LINE_RE = re.compile(r"^\s*[0-9a-f]+:\s+[0-9a-f]+\s+(\S+)")


def mnemonics_in_dasm(path):
    found = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            match = LINE_RE.match(line)
            if match:
                found.setdefault(match.group(1), 0)
                found[match.group(1)] += 1
    return found


def main(argv):
    if len(argv) != 3:
        print(__doc__.strip(), file=sys.stderr)
        return 2

    dasm_path, contract_path = argv[1], argv[2]
    found = mnemonics_in_dasm(dasm_path)
    with open(contract_path, encoding="utf-8") as handle:
        contract = json.load(handle)

    required = [entry["mnemonic"] for entry in contract["must_cover"]]
    missing = [m for m in required if m not in found]
    extra = sorted(set(found) - set(required))

    print(f"program        : {contract['program']}")
    print(f"dasm           : {dasm_path}")
    print(f"required       : {len(required)} mnemonics")
    print(f"present        : {len(required) - len(missing)}")
    for mnemonic in required:
        count = found.get(mnemonic, 0)
        flag = "ok  " if count else "MISS"
        print(f"  [{flag}] {mnemonic:<7} x{count}")

    if extra:
        print(f"not in contract: {', '.join(extra)}")

    out_of_scope = {e["mnemonic"] for e in contract.get("out_of_scope", [])}
    leaked = sorted(out_of_scope & set(found))
    if leaked:
        print(f"FAIL: out-of-scope instruction present in image: {leaked}")
        return 1

    if missing:
        print(f"FAIL: declared in {contract_path} but absent from the image: {missing}")
        return 1

    print("PASS: every contracted mnemonic is present in the built image")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
