"""Extrai uma janela causal pequena de um VCD, sem interpretar a ISA."""

from __future__ import annotations

import re
from pathlib import Path

_UNIDADES_FS = {"s": 10**15, "ms": 10**12, "us": 10**9, "ns": 10**6,
                "ps": 10**3, "fs": 1}


def _normalizar(caminho: str) -> str:
    return re.sub(r"\[[^]]*\]", "", caminho.removeprefix("dut."))


def _valor(bits: str, largura: int) -> str:
    bits = bits.lower()
    if set(bits) <= {"0", "1"}:
        return f"0x{int(bits, 2):0{max(1, (largura + 3) // 4)}X}"
    return "0b" + bits


def resumir(vcd: Path, sinais: list[str], *, clock: str = "dut.clk",
            falha_ns: float | None = None, janela_ciclos: int = 2) -> dict:
    """Retorna valores dos sinais selecionados nos flancos de subida do clock.

    O resultado é deliberadamente estrutural: valores desconhecidos são
    preservados e nenhuma semântica de CPU é inferida aqui.
    """
    texto = vcd.read_text(encoding="utf-8", errors="replace").splitlines()
    escopos: list[str] = []
    vars_por_codigo: dict[str, tuple[str, int]] = {}
    escala_fs = 1
    i = 0
    while i < len(texto):
        linha = texto[i].strip()
        if linha.startswith("$timescale"):
            bruto = linha.removeprefix("$timescale").replace("$end", "").strip()
            if not bruto and i + 1 < len(texto):
                i += 1
                bruto = texto[i].strip()
            m = re.match(r"(\d+)\s*(s|ms|us|ns|ps|fs)", bruto)
            if m:
                escala_fs = int(m.group(1)) * _UNIDADES_FS[m.group(2)]
        elif linha.startswith("$scope"):
            partes = linha.split()
            if len(partes) >= 3:
                escopos.append(partes[2])
        elif linha.startswith("$upscope"):
            if escopos:
                escopos.pop()
        elif linha.startswith("$var"):
            partes = linha.split()
            if len(partes) >= 5:
                try:
                    largura = int(partes[2])
                except ValueError:
                    largura = 1
                nome = partes[4]
                vars_por_codigo[partes[3]] = (".".join(escopos + [nome]), largura)
        elif linha == "$enddefinitions $end":
            i += 1
            break
        i += 1

    solicitados = {_normalizar(s): s for s in sinais}

    def solicitado(nome_vcd: str) -> str | None:
        normalizado = _normalizar(nome_vcd)
        return next((original for chave, original in solicitados.items()
                     if normalizado == chave or normalizado.endswith("." + chave)), None)

    por_codigo = {codigo: (original, largura)
                  for codigo, (nome, largura) in vars_por_codigo.items()
                  if (original := solicitado(nome)) is not None}
    clock_normalizado = _normalizar(clock)
    codigo_clock = next((codigo for codigo, (nome, _) in vars_por_codigo.items()
                         if _normalizar(nome) == clock_normalizado or
                         _normalizar(nome).endswith("." + clock_normalizado)), None)
    valores: dict[str, str] = {}
    amostras: list[dict] = []
    tempo = 0
    anterior_clock = "x"

    def aplicar(eventos: list[str], instante: int) -> None:
        nonlocal anterior_clock
        for evento in eventos:
            if evento.startswith("b"):
                partes = evento.split()
                if len(partes) == 2 and partes[1] in por_codigo:
                    nome, largura = por_codigo[partes[1]]
                    valores[nome] = _valor(partes[0][1:], largura)
            elif len(evento) >= 2 and evento[1:] in por_codigo:
                nome, largura = por_codigo[evento[1:]]
                valores[nome] = _valor(evento[0], largura)
        if codigo_clock and codigo_clock in vars_por_codigo:
            nome_clock, largura_clock = vars_por_codigo[codigo_clock]
            atual_clock = valores.get(solicitado(nome_clock) or clock, "0x0")
            if anterior_clock != "0x1" and atual_clock == "0x1":
                amostras.append({"time_ns": instante * escala_fs / 1_000_000,
                                 "values": {s: valores.get(s, "unknown") for s in sinais}})
            anterior_clock = atual_clock

    eventos: list[str] = []
    for linha_bruta in texto[i:]:
        linha = linha_bruta.strip()
        if not linha or linha.startswith("$"):
            continue
        if linha.startswith("#"):
            aplicar(eventos, tempo)
            eventos = []
            try:
                tempo = int(linha[1:])
            except ValueError:
                pass
        else:
            eventos.append(linha)
    aplicar(eventos, tempo)
    if falha_ns is None and amostras:
        falha_ns = amostras[-1]["time_ns"]
    centro = min(range(len(amostras)), key=lambda n: abs(amostras[n]["time_ns"] - falha_ns)) \
        if amostras and falha_ns is not None else 0
    inicio, fim = max(0, centro - janela_ciclos), centro + janela_ciclos + 1
    presentes = set(por_codigo.values())
    presentes = {nome for nome, _ in presentes}
    return {"vcd": str(vcd), "clock": clock, "failure_time_ns": falha_ns,
            "selected": sinais, "missing": [s for s in sinais if s not in presentes],
            "samples": amostras[inicio:fim]}
