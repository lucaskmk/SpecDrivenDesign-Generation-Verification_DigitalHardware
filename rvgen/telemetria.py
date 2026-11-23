#!/usr/bin/env python3
"""Telemetria por fase: `python -m rvgen telemetria <experimentos...>`.

Lê o `sessao.jsonl` de cada experimento e soma, por grupo de fases (o
equivalente da telemetria por estágio do UCAgent, arXiv 2603.25768, Fig. 8):

- chamadas ao modelo, tokens de entrada e saída e tempo de resposta do modelo
  (eventos `llm`);
- tempo de simulação (GHDL/cocotb e `spec-riscv-test`, campo `segundos` dos
  eventos de teste; não é IA);
- falhas: testes de componente e candidatos que falharam na simulação e
  programas reprovados pelo juiz;
- recusas do validador (regras determinísticas do `rvgen`: candidato ou plano
  de teste recusado, plano de evolução inválido) e recusas do revisor
  (contrato reprovado pela IA revisora);
- erros do provedor (`llm_erro`, saída truncada) e repetições de rede (pedido
  HTTP repetido por falha transitória; só registradas desde o campo
  `repeticoes_rede` do evento `llm` -- em sessões antigas sai `-`).

Não chama modelo nem GHDL. O custo, quando pedido, é estimativa: tokens x preço
público do OpenRouter no dia (o mesmo cálculo de `rvgen comparar`).
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import comparar as cmp

__all__ = ["GRUPOS", "FASE_PARA_GRUPO", "Metricas", "Telemetria", "sessoes",
           "telemetria_de", "tabela_texto", "tabela_markdown"]

# Ordem das colunas e das linhas. "linha de base" só existe em evoluções
# (testes antigos e juiz na ISA antiga, sem IA).
GRUPOS = ("planejamento", "linha de base", "contratos", "vhdl", "testes",
          "correcao", "juiz", "outros")

FASE_PARA_GRUPO: dict[str, str] = {
    # planejamento: o que a CPU tem de fazer e como dividir
    "instrucoes": "planejamento",
    "decomposicao": "planejamento",
    "plano_evolucao": "planejamento",
    # contratos por bloco e sua revisão independente
    "especificacao_componente": "contratos",
    "revisao_especificacao": "contratos",
    "revisao_semantica_especificacao": "contratos",
    "evolucao_especificacao": "contratos",
    # VHDL
    "escrita": "vhdl",
    # testbench e expansão de testes de componente
    "testbench": "testes",
    "ampliacao_testbench": "testes",
    "caso_publico_isolado": "testes",
    "caso_interno_isolado": "testes",
    "orquestracao_expansao_testbench": "testes",
    "orquestracao_lote_testbench": "testes",
    "regressao": "testes",
    "teste_interno_componente": "testes",
    "ampliacao_teste_interno": "testes",
    # correção dentro da pilha de componentes (quem errou? conserta)
    "triagem_componente": "correcao",
    "correcao_testbench": "correcao",
    "diagnostico_componente": "correcao",
    "diagnostico_interno_componente": "correcao",
    "planejar_diagnostico_interno": "correcao",
    "hipotese_exploratoria": "correcao",
    "revisao_hipotese": "correcao",
    "revisao_convergencia_componente": "correcao",
    "revisao_correcao_local": "correcao",
    # laço de correção guiado pelo juiz oficial
    "escolha": "juiz",
    "correcao": "juiz",
}

_PLACAR_RE = re.compile(r"(\d+)\s*/\s*(\d+)")


@dataclass
class Metricas:
    chamadas: int = 0
    tokens_entrada: int = 0
    tokens_saida: int = 0
    segundos_modelo: float = 0.0
    segundos_simulacao: float = 0.0
    falhas: int = 0
    recusas_validador: int = 0
    recusas_revisor: int = 0
    erros_provedor: int = 0
    repeticoes_rede: int = 0
    custo_usd: float | None = None

    def somar(self, outra: "Metricas") -> None:
        for nome in ("chamadas", "tokens_entrada", "tokens_saida", "segundos_modelo",
                     "segundos_simulacao", "falhas", "recusas_validador",
                     "recusas_revisor", "erros_provedor", "repeticoes_rede"):
            setattr(self, nome, getattr(self, nome) + getattr(outra, nome))
        if outra.custo_usd is not None:
            self.custo_usd = (self.custo_usd or 0.0) + outra.custo_usd


@dataclass
class Telemetria:
    experimento: str
    sessao: str
    modelo: str
    provedor: str
    placar: str                    # do evento `fim`; "-" se a sessão não terminou
    grupos: dict[str, Metricas]
    fases: dict[str, Metricas]     # só eventos `llm`, por fase fina
    triagem: Counter = field(default_factory=Counter)   # causa -> vezes
    repeticoes_registradas: bool = False   # algum evento llm traz `repeticoes_rede`
    parou_no_teto: bool = False
    execucoes: int = 1             # `inicio` + `retomada`

    @property
    def total(self) -> Metricas:
        t = Metricas()
        for m in self.grupos.values():
            t.somar(m)
        return t


# --------------------------------------------------------------------------
# leitura
# --------------------------------------------------------------------------

def sessoes(alvos: list[Path], *, todas: bool = False) -> list[Path]:
    """Sessões com `sessao.jsonl` (a mais recente de cada experimento, ou
    todas). Diferente do `comparar`, sessões interrompidas entram: a
    telemetria mostra também onde uma geração parou."""
    out: list[Path] = []
    for alvo in alvos:
        for pasta in cmp._pastas_de_experimento(alvo):
            achadas = sorted(p.parent for p in (pasta / ".rvgen").glob("sessao-*/sessao.jsonl"))
            out += achadas if todas else achadas[-1:]
    return out


def _eventos(sessao: Path) -> list[dict]:
    out = []
    for linha in (sessao / "sessao.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(linha)
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict):
            out.append(d)
    return out


def _falhas_do_placar(placar: object) -> int:
    """Programas reprovados de um placar "a/b casos"; 1 se não houve placar
    (não compilou, erro do juiz)."""
    m = _PLACAR_RE.search(str(placar or ""))
    if not m:
        return 1
    return max(0, int(m.group(2)) - int(m.group(1)))


def telemetria_de(sessao: Path, precos: cmp.Precos | None = None) -> Telemetria:
    grupos = {g: Metricas() for g in GRUPOS}
    fases: dict[str, Metricas] = {}
    triagem: Counter = Counter()
    modelo = provedor = ""
    placar = "-"
    registradas = teto = False
    execucoes = 0

    def grupo_da_fase(fase: object) -> str:
        return FASE_PARA_GRUPO.get(str(fase), "outros")

    for d in _eventos(sessao):
        ev = d.get("evento")
        if ev == "llm":
            g = grupo_da_fase(d.get("fase"))
            parcial = Metricas(chamadas=1,
                               tokens_entrada=int(d.get("tokens_entrada") or 0),
                               tokens_saida=int(d.get("tokens_saida") or 0),
                               segundos_modelo=float(d.get("segundos") or 0))
            if "repeticoes_rede" in d:
                registradas = True
                parcial.repeticoes_rede = int(d.get("repeticoes_rede") or 0)
            if precos is not None or d.get("provedor") in ("ollama", "vllm"):
                _, parcial.custo_usd = cmp._custo(d.get("provedor", ""), d.get("modelo", ""),
                                                  parcial.tokens_entrada, parcial.tokens_saida,
                                                  precos)
            grupos[g].somar(parcial)
            fases.setdefault(str(d.get("fase")), Metricas()).somar(parcial)
            modelo = modelo or str(d.get("modelo") or "")
            provedor = provedor or str(d.get("provedor") or "")
        elif ev in ("inicio", "retomada"):
            execucoes += 1
            if ev == "inicio":
                modelo = str(d.get("modelo") or modelo)
                provedor = str(d.get("provedor") or provedor)
        elif ev in ("teste_componente", "candidato_lote_executado"):
            grupos["testes"].segundos_simulacao += float(d.get("segundos") or 0)
            grupos["testes"].falhas += d.get("passou") is False
        elif ev == "hierarquia_inventariada":
            grupos["testes"].falhas += d.get("passou") is False
        elif ev == "linha_de_base_componente":
            grupos["linha de base"].falhas += d.get("passou") is False
        elif ev == "spec-riscv-test":
            g = "linha de base" if d.get("rotulo") == "linha-de-base" else "juiz"
            grupos[g].segundos_simulacao += float(d.get("segundos") or 0)
            grupos[g].falhas += _falhas_do_placar(d.get("placar"))
        elif ev in ("candidato_lote_rejeitado", "plano_teste_rejeitado"):
            grupos["testes"].recusas_validador += 1
        elif ev == "plano_evolucao_invalido":
            grupos["planejamento"].recusas_validador += 1
        elif ev == "especificacao_reprovada":
            grupos["contratos"].recusas_revisor += 1
        elif ev in ("llm_erro", "saida_truncada"):
            grupos[grupo_da_fase(d.get("fase"))].erros_provedor += 1
        elif ev == "limite_atingido":
            teto = True
        elif ev == "triagem_componente":
            triagem[str(d.get("causa") or "?")] += 1
        elif ev == "fim":
            placar = str(d.get("placar") or "-")

    return Telemetria(experimento=sessao.parent.parent.name,
                      sessao=sessao.name.removeprefix("sessao-"),
                      modelo=modelo or "?", provedor=provedor or "?", placar=placar,
                      grupos=grupos, fases=fases, triagem=triagem,
                      repeticoes_registradas=registradas, parou_no_teto=teto,
                      execucoes=max(1, execucoes))


# --------------------------------------------------------------------------
# saída
# --------------------------------------------------------------------------

COLUNAS = ("grupo", "chamadas", "% chamadas", "tokens entrada", "tokens saida",
           "min modelo", "min simulacao", "falhas", "recusas validador",
           "recusas revisor", "erros provedor", "repeticoes rede", "custo")


def _vazio(m: Metricas) -> bool:
    return not any((m.chamadas, m.segundos_simulacao, m.falhas, m.recusas_validador,
                    m.recusas_revisor, m.erros_provedor))


def _custo_txt(m: Metricas) -> str:
    if not m.chamadas:
        return "-"           # grupo sem IA (linha de base, juiz sem correcao)
    return "?" if m.custo_usd is None else f"US$ {m.custo_usd:.3f}"


def _linha(nome: str, m: Metricas, total_chamadas: int, registradas: bool) -> list[str]:
    pct = f"{100 * m.chamadas / total_chamadas:.0f}%" if total_chamadas else "-"
    return [nome, str(m.chamadas), pct, str(m.tokens_entrada), str(m.tokens_saida),
            f"{m.segundos_modelo / 60:.1f}", f"{m.segundos_simulacao / 60:.1f}",
            str(m.falhas), str(m.recusas_validador), str(m.recusas_revisor),
            str(m.erros_provedor), str(m.repeticoes_rede) if registradas else "-",
            _custo_txt(m)]


def _linhas(t: Telemetria, detalhado: bool) -> list[list[str]]:
    total = t.total
    if detalhado:
        # por fase fina so ha metricas de chamadas (eventos llm)
        corpo = [_linha(f, m, total.chamadas, t.repeticoes_registradas)
                 for f, m in sorted(t.fases.items(), key=lambda x: -x[1].chamadas)]
    else:
        corpo = [_linha(g, m, total.chamadas, t.repeticoes_registradas)
                 for g, m in t.grupos.items() if not _vazio(m)]
    return corpo + [_linha("TOTAL", total, total.chamadas, t.repeticoes_registradas)]


def _cabecalho(t: Telemetria) -> str:
    extra = []
    if t.execucoes > 1:
        extra.append(f"{t.execucoes} execucoes (sessao retomada)")
    if t.parou_no_teto:
        extra.append("parou no teto de chamadas/tokens")
    if t.triagem:
        extra.append("triagem: " + ", ".join(f"{c} {n}" for c, n in t.triagem.most_common()))
    return (f"{t.experimento} (sessao {t.sessao}) | {t.modelo} | placar final {t.placar}"
            + (" | " + " | ".join(extra) if extra else ""))


def _grade_texto(grade: list[list[str]]) -> str:
    larguras = [max(len(l[i]) for l in grade) for i in range(len(grade[0]))]
    texto = ["  ".join(c.ljust(w) for c, w in zip(l, larguras)).rstrip() for l in grade]
    texto.insert(1, "  ".join("-" * w for w in larguras))
    return "\n".join(texto)


def _resumo(tels: list[Telemetria]) -> list[list[str]]:
    """Chamadas por grupo, um experimento por linha (a figura por estágio)."""
    usados = [g for g in GRUPOS if any(t.grupos[g].chamadas for t in tels)]
    grade = [["experimento", "modelo", *usados, "total", "custo"]]
    for t in tels:
        total = t.total
        grade.append([t.experimento, t.modelo,
                      *(f"{t.grupos[g].chamadas} ({100 * t.grupos[g].chamadas / total.chamadas:.0f}%)"
                        if total.chamadas else "0" for g in usados),
                      str(total.chamadas), _custo_txt(total)])
    return grade


def _nota(precos_ok: bool) -> str:
    fonte = (f"preco publico do OpenRouter em {date.today():%Y-%m-%d}" if precos_ok
             else "preco indisponivel (sem rede ou --sem-rede)")
    return ("Fonte: eventos do sessao.jsonl. Tempo de modelo = soma das respostas; tempo de "
            "simulacao = GHDL/cocotb e spec-riscv-test. Falhas = testes de componente, "
            "candidatos e programas do juiz reprovados. Recusas do validador = regras "
            "deterministicas do rvgen; recusas do revisor = contrato reprovado pela IA "
            "revisora. Repeticoes de rede: '-' em sessoes gravadas antes do campo "
            f"repeticoes_rede. Custo: ESTIMATIVA = tokens x {fonte}; modelo local = 0.")


def tabela_texto(tels: list[Telemetria], precos_ok: bool, *, detalhado: bool = False) -> str:
    partes = []
    for t in tels:
        partes.append(_cabecalho(t) + "\n" + _grade_texto([list(COLUNAS)] + _linhas(t, detalhado)))
    if len(tels) > 1:
        partes.append("Chamadas por grupo\n" + _grade_texto(_resumo(tels)))
    return "\n\n".join(partes) + "\n\n" + _nota(precos_ok) + "\n"


def _grade_markdown(grade: list[list[str]]) -> str:
    cab, *corpo = grade
    linhas = ["| " + " | ".join(cab) + " |", "|" + "|".join("---" for _ in cab) + "|"]
    linhas += ["| " + " | ".join(c.replace("|", "\\|") for c in l) + " |" for l in corpo]
    return "\n".join(linhas)


def tabela_markdown(tels: list[Telemetria], precos_ok: bool, *, detalhado: bool = False) -> str:
    partes = [f"# Telemetria por fase ({date.today():%Y-%m-%d})"]
    if len(tels) > 1:
        partes.append("## Chamadas por grupo\n\n" + _grade_markdown(_resumo(tels)))
    for t in tels:
        partes.append(f"## {t.experimento}\n\n{_cabecalho(t)}\n\n"
                      + _grade_markdown([list(COLUNAS)] + _linhas(t, detalhado)))
    partes.append(_nota(precos_ok))
    return "\n\n".join(partes) + "\n"
