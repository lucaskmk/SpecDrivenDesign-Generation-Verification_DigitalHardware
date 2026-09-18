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

from . import feedback

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
        # o modelo nao e uma entrega: tem TODO no lugar dos caminhos
        if p.parent.name not in {"_template", "_modelo"}
    )
    return achados


SELOS = {
    "aprovado": ("APROVADO", VERDE),
    "reprovado": ("REPROVADO", VERMELHO),
    "incompleto": ("INCOMPLETO", AMARELO),
    "parcial": ("PARCIAL", AMARELO),
}


def progresso(cor: bool):
    """Uma linha por caso: sem ela a tela fica muda por um minuto.

    A saida do GHDL vai para o `sim.log` de cada caso (ADR-011); aqui so
    aparece o que o aluno precisa acompanhar.
    """
    def on_event(ev: dict) -> None:
        tipo = ev.get("tipo")
        if tipo == "compilacao" and ev["estado"] == "inicio":
            print(_cor("  compilando as fontes com o GHDL...", CINZA, cor), flush=True)
        elif tipo == "compilacao" and ev["estado"] == "erro":
            print(_cor("  a compilacao falhou:", VERMELHO, cor), flush=True)
            for e in ev.get("erros", [])[:5]:
                print(f"    {e['arquivo']}:{e['linha']}:{e['coluna']}: {e['mensagem']}")
        elif tipo == "item" and ev["estado"] in ("passou", "falhou"):
            r = ev.get("resultado") or {}
            ok = ev["estado"] == "passou"
            marca = _cor("ok  ", VERDE, cor) if ok else _cor("FALHOU", VERMELHO, cor)
            extra = []
            if r.get("cycles"):
                extra.append(f"{r['cycles']} ciclos")
            if ev.get("duracao_s") is not None:
                extra.append(f"{ev['duracao_s']:.1f} s")
            info = _cor(f"({', '.join(extra)})", CINZA, cor) if extra else ""
            print(f"  {marca}  {ev['id']:<28} {info}", flush=True)
            if not ok and r.get("diagnostico"):
                resumo = r["diagnostico"]["resumo"]
                print(f"          {_cor(resumo, VERMELHO, cor)}", flush=True)
        elif tipo == "etapa_pulada":
            print(_cor(f"  {ev['motivo']}", AMARELO, cor), flush=True)
    return on_event


def imprimir_relatorio(rel: dict, cor: bool) -> None:
    nome = rel["design"]
    rotulo, tom = SELOS.get(rel.get("veredito", ""), ("REPROVADO", VERMELHO))
    selo = _cor(rotulo, tom, cor)

    print(f"\n{'=' * 66}")
    print(f"{nome}   {selo}")
    print(f"{_cor(rel['manifest'], CINZA, cor)}")
    print("=" * 66)

    for etapa, n in rel["por_etapa"].items():
        rotulo = "RV32I (baseline)" if etapa == "rv32i" else "RV32IM (extensao)"
        estado = (_cor("ok", VERDE, cor) if n["falhou"] == 0
                  else _cor(f"{n['falhou']} falhou(ram)", VERMELHO, cor))
        print(f"  {rotulo:<20} {n['passou']:>3}/{n['total']:<3} {estado}")

    # Veredito por REQUISITO -- e o que o aluno precisa ler para saber o que
    # corrigir. "3 casos falharam" nao diz nada; "FR-RV-14 nao atendido" diz.
    # Requisito atendido some da lista: so o que falta aparece.
    por_req = rel.get("por_requisito", {})
    if por_req:
        pendentes = {r: e for r, e in por_req.items() if not e["atendido"]}
        atendidos = len(por_req) - len(pendentes)
        rotulo = _cor("Requisitos:", CINZA, cor)
        print(f"\n  {rotulo} {atendidos}/{len(por_req)} atendidos")
        for r, e in pendentes.items():
            casos = ", ".join(e["casos_falhos"])
            marca = _cor("X", VERMELHO, cor)
            contagem = _cor(f"({e['passou']}/{e['total']} casos)", CINZA, cor)
            print(f"    {marca} {r}  {contagem}  -> {casos}")

    falhas = [c for c in rel["casos"] if not c["passed"]]
    if falhas:
        print(f"\n  {_cor('Casos reprovados:', VERMELHO, cor)}")
        for c in falhas:
            reqs = ", ".join(c["requirements"])
            print(f"    - {c['name']}  [{reqs}]")
            diag = c.get("diagnostico")
            linhas = (feedback.resumo_em_texto(diag) if diag
                      else [c["detail"]] if c["detail"] else [])
            for linha in linhas:
                print(f"      {_cor(linha, CINZA, cor)}")
            if c.get("log"):
                print(f"      {_cor('log: ' + c['log'], CINZA, cor)}")

    escopo = rel.get("escopo") or {}
    if escopo and not escopo.get("completo"):
        fora = escopo["casos_na_suite"] - escopo["casos_selecionados"]
        print(f"\n  {_cor('! execucao parcial:', AMARELO, cor)} "
              f"{escopo['casos_selecionados']} de {escopo['casos_na_suite']} "
              f"casos selecionados ({fora} fora); nao vale como aprovacao")

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
    ap.add_argument("--casos", metavar="NOMES",
                    help="lista separada por virgulas de nomes ou ids de casos")
    ap.add_argument("--listar", action="store_true",
                    help="lista os casos da suite e termina sem usar GHDL")
    ap.add_argument("--eventos", action="store_true",
                    help="emite eventos JSON Lines, um por linha, para automacao")
    ap.add_argument("--workdir", metavar="DIRETORIO",
                    help="preserva logs e artefatos nesse diretorio")
    ap.add_argument("--keep", action="store_true",
                    help="mantem os arquivos intermediarios da simulacao")
    ap.add_argument("--sem-cor", action="store_true", help="saida sem cor ANSI")
    args = ap.parse_args(argv)

    from .conformance import (SelectionError, catalog, exit_code_for,
                              resolve_selection, run_conformance)

    if args.listar:
        for item in catalog():
            reqs = ", ".join(item["requisitos"])
            print(f"{item['id']:<24} {reqs:<30} {item['descricao']}")
        return 0

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

    try:
        only = resolve_selection(args.casos.split(",") if args.casos else None)
    except SelectionError as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 2

    # Valida o contrato inteiro antes de consultar o simulador. Assim uma
    # entrega malformada recebe o erro do campo correto, mesmo num ambiente
    # sem GHDL.
    from .manifest import ManifestError, load_manifest
    for path in manifestos:
        try:
            load_manifest(path).source_paths()
        except ManifestError as e:
            print(f"ERRO no manifesto {path}: {e}", file=sys.stderr)
            return 2

    if shutil.which("ghdl") is None:
        print("ERRO: 'ghdl' nao esta no PATH. O validador exige simulador "
              "real -- ele nunca aprova por inferencia (NFR-RV-02).",
              file=sys.stderr)
        return 2

    print(f"Validando {len(manifestos)} CPU(s). Cada caso e uma execucao real "
          f"de GHDL; a saida do simulador fica no sim.log de cada caso.")

    relatorios = []
    work = (Path(args.workdir).resolve() if args.workdir
            else Path(tempfile.mkdtemp(prefix="rvverify_")))
    work.mkdir(parents=True, exist_ok=True)

    def emitir(evento: dict) -> None:
        if args.eventos:
            print("@rvverify " + json.dumps(evento, ensure_ascii=False), flush=True)

    try:
        emitir({"tipo": "inicio", "cpus": len(manifestos),
                "etapas": list(etapas), "casos": args.casos})
        for m in manifestos:
            print(f"\n{_cor('>>> ' + str(m), CINZA, cor)}", flush=True)
            try:
                rel = run_conformance(m, work / m.parent.name, stages=etapas,
                                      only=only,
                                      on_event=lambda e: (emitir(e), progresso(cor)(e)))
            except Exception as e:                       # noqa: BLE001
                rel = relatorio_de_erro(m, e)
            relatorios.append(rel)
            imprimir_relatorio(rel, cor)
            emitir({"tipo": "relatorio", **rel})
    finally:
        if not args.keep and not args.workdir:
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
    codigo = max(exit_code_for(r["veredito"]) for r in relatorios)
    emitir({"tipo": "fim", "aprovadas": aprovadas,
            "total": len(relatorios), "codigo": codigo})
    return codigo


def relatorio_de_erro(manifest: Path, e: Exception) -> dict:
    """Relatorio de uma CPU que nem chegou a rodar (manifesto invalido)."""
    diag = feedback.diagnosticar(
        nome="manifesto", relatorio=None, tipo_forcado="manifesto",
        mensagem_forcada=f"{type(e).__name__}: {e}")
    return {
        "design": manifest.parent.name,
        "manifest": str(manifest),
        "veredito": "reprovado",
        "aprovado": False,
        "codigo_saida": 1,
        "escopo": {},
        "compilacao": {"ok": None, "erros": []},
        "por_etapa": {},
        "por_requisito": {},
        "pulado": [],
        "casos": [{
            "name": "carregar manifesto", "stage": "-", "id": "-/manifesto",
            "passed": False, "requirements": [],
            "detail": f"{type(e).__name__}: {e}",
            "cycles": None, "instructions": None,
            "cpi": None, "m_instructions": None,
            "diagnostico": diag, "log": None,
        }],
    }


if __name__ == "__main__":
    raise SystemExit(main())
