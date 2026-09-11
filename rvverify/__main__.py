#!/usr/bin/env python3
"""Validador de CPU RISC-V -- ponto de entrada.

REQ: FR-RV-11, FR-RV-16, FR-RV-21, NFR-RV-01, NFR-RV-02

    python -m rvverify                      # valida tudo em entregas/
    python -m rvverify entregas/joao        # valida uma entrega
    python -m rvverify examples/            # valida os exemplos de referencia
    python -m rvverify caminho/cpu.toml     # aponta direto para um manifesto

Descobre qualquer diretorio que contenha um `cpu.toml`, roda a suite de
conformidade em cada um e sai com codigo != 0 se alguma reprovar -- o que o
torna utilizavel em CI sem nenhuma cola extra.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

VERDE = "\033[32m"
VERMELHO = "\033[31m"
AMARELO = "\033[33m"
CINZA = "\033[90m"
FIM = "\033[0m"


def _cor(texto: str, cor: str, usar: bool) -> str:
    return f"{cor}{texto}{FIM}" if usar else texto


def descobrir(alvo: Path) -> list[Path]:
    """Encontra os `cpu.toml` sob `alvo`, em ordem determinista."""
    if alvo.is_file():
        return [alvo]
    if (alvo / "cpu.toml").is_file():
        return [alvo / "cpu.toml"]
    achados = sorted(
        p for p in alvo.rglob("cpu.toml")
        # o template nao e uma entrega: tem TODO no lugar dos caminhos
        if p.parent.name != "_template"
    )
    return achados


def imprimir_relatorio(rel: dict, cor: bool) -> None:
    nome = rel["design"]
    if rel["aprovado"]:
        selo = _cor("APROVADO", VERDE, cor)
    elif rel["pulado"] and not any(not c["passed"] for c in rel["casos"]):
        selo = _cor("INCOMPLETO", AMARELO, cor)
    else:
        selo = _cor("REPROVADO", VERMELHO, cor)

    print(f"\n{'=' * 66}")
    print(f"{nome}   {selo}")
    print(f"{_cor(rel['manifest'], CINZA, cor)}")
    print("=" * 66)

    for etapa, n in rel["por_etapa"].items():
        rotulo = "RV32I (baseline)" if etapa == "rv32i" else "RV32IM (extensao)"
        estado = (_cor("ok", VERDE, cor) if n["falhou"] == 0
                  else _cor(f"{n['falhou']} falhou(ram)", VERMELHO, cor))
        print(f"  {rotulo:<20} {n['passou']:>3}/{n['total']:<3} {estado}")

    falhas = [c for c in rel["casos"] if not c["passed"]]
    if falhas:
        print(f"\n  {_cor('Casos reprovados:', VERMELHO, cor)}")
        for c in falhas:
            reqs = ", ".join(c["requirements"])
            print(f"    - {c['name']}  [{reqs}]")
            if c["detail"]:
                print(f"      {_cor(c['detail'], CINZA, cor)}")

    for nota in rel["pulado"]:
        print(f"\n  {_cor('! ' + nota, AMARELO, cor)}")

    # Metricas so aparecem quando o manifesto permitiu observa-las.
    medidos = [c for c in rel["casos"] if c["passed"] and c["cycles"]]
    if medidos:
        ciclos = sum(c["cycles"] for c in medidos)
        m_instr = sum(c["m_instructions"] or 0 for c in medidos)
        com_cpi = [c for c in medidos if c["cpi"]]
        print(f"\n  {_cor('Medido:', CINZA, cor)} {ciclos} ciclos em "
              f"{len(medidos)} programas", end="")
        if com_cpi:
            cpi = sum(c["cpi"] for c in com_cpi) / len(com_cpi)
            print(f", CPI medio {cpi:.3f}", end="")
        else:
            print(f", {_cor('CPI nao observavel neste manifesto', CINZA, cor)}",
                  end="")
        if m_instr:
            print(f", {m_instr} instrucoes RV32M", end="")
        print()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m rvverify",
        description="Valida uma CPU RISC-V contra a suite de conformidade "
                    "RV32I e RV32IM.",
    )
    ap.add_argument("alvo", nargs="?", default=None,
                    help="pasta com cpu.toml, pasta de entregas, ou o proprio "
                         "cpu.toml (padrao: entregas/)")
    ap.add_argument("--json", metavar="ARQUIVO",
                    help="grava o relatorio completo em JSON")
    ap.add_argument("--etapa", choices=["rv32i", "rv32m", "ambas"],
                    default="ambas", help="qual etapa rodar (padrao: ambas)")
    ap.add_argument("--keep", action="store_true",
                    help="mantem os arquivos intermediarios da simulacao")
    ap.add_argument("--sem-cor", action="store_true", help="saida sem cor ANSI")
    args = ap.parse_args(argv)

    if shutil.which("ghdl") is None:
        print("ERRO: 'ghdl' nao esta no PATH. O validador exige simulador "
              "real -- ele nunca aprova por inferencia (NFR-RV-02).",
              file=sys.stderr)
        return 2

    alvo = Path(args.alvo) if args.alvo else REPO_ROOT / "entregas"
    if not alvo.exists():
        print(f"ERRO: {alvo} nao existe.", file=sys.stderr)
        return 2

    manifestos = descobrir(alvo)
    if not manifestos:
        print(f"Nenhum cpu.toml encontrado em {alvo}.\n"
              f"Uma entrega e uma pasta com um cpu.toml na raiz -- veja "
              f"entregas/README.md.", file=sys.stderr)
        return 2

    cor = not args.sem_cor and sys.stdout.isatty()
    etapas = (("rv32i", "rv32m") if args.etapa == "ambas" else (args.etapa,))

    from .conformance import run_conformance

    print(f"Validando {len(manifestos)} CPU(s). Cada caso e uma execucao real "
          f"de GHDL -- leva alguns minutos.")

    relatorios = []
    work = Path(tempfile.mkdtemp(prefix="rvverify_"))
    try:
        for m in manifestos:
            print(f"\n{_cor('>>> ' + str(m), CINZA, cor)}", flush=True)
            try:
                rel = run_conformance(m, work / m.parent.name, stages=etapas)
            except Exception as e:                       # noqa: BLE001
                rel = {
                    "design": m.parent.name,
                    "manifest": str(m),
                    "aprovado": False,
                    "por_etapa": {},
                    "pulado": [],
                    "casos": [{
                        "name": "carregar manifesto", "stage": "-",
                        "passed": False, "requirements": [],
                        "detail": f"{type(e).__name__}: {e}",
                        "cycles": None, "instructions": None,
                        "cpi": None, "m_instructions": None,
                    }],
                }
            relatorios.append(rel)
            imprimir_relatorio(rel, cor)
    finally:
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)
        else:
            print(f"\nintermediarios em {work}")

    if args.json:
        Path(args.json).write_text(json.dumps(relatorios, indent=2),
                                   encoding="utf-8")
        print(f"\nrelatorio JSON: {args.json}")

    aprovadas = sum(1 for r in relatorios if r["aprovado"])
    print(f"\n{'=' * 66}")
    print(f"{aprovadas}/{len(relatorios)} CPU(s) aprovada(s).")
    return 0 if aprovadas == len(relatorios) else 1


if __name__ == "__main__":
    raise SystemExit(main())
