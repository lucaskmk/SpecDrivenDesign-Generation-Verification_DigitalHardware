"""`rvgen gerar --evoluir-de`: muda uma CPU já aprovada para specs novas.

Exemplo: a CPU RV32I aprovada em ``experimentos/luna6_prof_3`` vira RV32IM.
O fluxo segue a sugestão do professor: primeiro roda tudo e entende as specs,
só depois altera.

0. Entender: copia a CPU aprovada (VHDL, arquitetura, contratos dos blocos,
   testes e registros de aprovação) para uma pasta nova e roda, sem IA, todos
   os testes de componente e o juiz na ISA antiga. Essa é a linha de base.
1. Planejar: uma chamada à IA lê o diff entre o contrato antigo e o novo, as
   instruções novas, a arquitetura, o contrato de cada bloco e a linha de base,
   e devolve a decomposição-alvo inteira. A decomposição é livre: cada bloco é
   mantido, mudado ou novo, e pode vir de um ou mais blocos antigos (renomear,
   dividir, juntar); bloco antigo que não aparece é removido. O topo `cpu` só
   liga blocos. O plano fica em ``evolucao/plano.md``.
2. Contratos: blocos mudados ou novos ganham contrato atualizado a partir dos
   contratos de origem (e passam pelo revisor semântico de sempre).
3. VHDL e testes, na ordem da arquitetura: bloco mudado é reescrito a partir do
   VHDL aprovado de origem; se manteve o nome, os testes antigos dele viram
   casos de regressão, e a IA acrescenta casos novos. Bloco mantido fica como
   estava e só roda de novo os próprios testes (pode quebrar por causa de uma
   dependência que mudou; aí a triagem de sempre corrige).
4. Juiz: o mesmo laço de correção do ``gerar``, com a ISA nova.
"""

from __future__ import annotations

import difflib
import json
import shutil
import time
from pathlib import Path

from . import contrato as ct
from .agente import (Agente, ErroGeracao, ErroIntegridade, ErroLLM, Resultado,
                     extrair_json, placar_de, validar_arquitetura)
from .config import REPO_ROOT

__all__ = ["sessao_aprovada", "aplicar_plano", "evoluir"]

# o que a sessão de origem guarda e a sessão nova herda
_HERDADO = ("component_specs", "testes", "testes_aprovados", "testes_casos",
            "componentes_aprovados", "regressoes", "hierarquia")
ACOES = ("keep", "change", "new")


def sessao_aprovada(origem: Path) -> Path:
    """A sessão mais recente de ``origem`` cuja CPU foi aprovada pelo juiz."""
    raiz = Path(origem) / ".rvgen"
    candidatas = sorted(raiz.glob("sessao-*"), reverse=True) if raiz.is_dir() else []
    for sessao in candidatas:
        try:
            resultado = json.loads((sessao / "resultado.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if resultado.get("objetivo_atingido"):
            return sessao
    raise ErroGeracao(f"{origem} não tem sessão aprovada em .rvgen/: evoluir parte de uma "
                      "CPU que já passou no juiz")


def _eventos(sessao: Path) -> list[dict]:
    return [json.loads(linha) for linha in
            (sessao / "sessao.jsonl").read_text(encoding="utf-8").splitlines() if linha.strip()]


def _copiar_origem(agente: Agente, origem: Path, sessao_o: Path) -> dict:
    """Copia a CPU aprovada para a pasta nova e devolve a arquitetura antiga."""
    agente._preparar_pasta()
    for fonte in sorted((origem / "src").glob("*.vhd")):
        shutil.copyfile(fonte, agente.pasta / "src" / fonte.name)
    for nome in _HERDADO:
        if (sessao_o / nome).is_dir():
            shutil.copytree(sessao_o / nome, agente.sessao / nome, dirs_exist_ok=True)
    (agente.sessao / "evolucao").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(sessao_o / "contrato.txt", agente.sessao / "evolucao" / "contrato-anterior.txt")
    arq = json.loads((origem / "architecture.json").read_text(encoding="utf-8"))
    blocos, motivo = validar_arquitetura(arq, max(agente.max_blocos, len(arq.get("blocks") or [])))
    if not blocos:
        raise ErroGeracao(f"architecture.json da origem inválido: {motivo}")
    arq["blocks"] = blocos
    return arq


def _testes_do_bloco(agente: Agente, bloco: dict) -> list[Path]:
    testes = [agente._caminho_teste(bloco), *agente._casos_publicos_isolados(bloco),
              *sorted((agente.sessao / "regressoes").glob(f"test_{bloco['name']}*.py"))]
    return [t for t in testes if t.exists()]


def _linha_de_base(agente: Agente, arq: dict, isa_antiga: str) -> dict:
    """Roda, sem IA, todos os testes herdados e o juiz na ISA antiga."""
    agente.relatar("[0] entendendo o projeto: rodando todos os testes da CPU aprovada ...")
    componentes: dict[str, dict] = {}
    for bloco in arq["blocks"]:
        testes = _testes_do_bloco(agente, bloco)
        passaram = 0
        for teste in testes:
            rotulo = f"base-{bloco['name']}-{teste.stem}"
            ex = agente.executor.rodar_componente(
                agente.pasta, componente=bloco["name"], teste=teste,
                json_saida=agente.sessao / "evolucao" / "linha_de_base" / f"{rotulo}.json",
                workdir=agente.sessao / "sim" / rotulo,
                build_root=agente.sessao / "build" / f"componente-{bloco['name']}",
                fontes=agente._fontes_do_bloco(bloco, arq))
            passou = bool((ex.relatorio or {}).get("passed"))
            passaram += passou
            agente._log({"evento": "linha_de_base_componente", "bloco": bloco["name"],
                         "testbench": teste.relative_to(agente.pasta).as_posix(),
                         "passou": passou})
        componentes[bloco["name"]] = {"passaram": passaram, "total": len(testes)}
        agente.relatar(f"  base {bloco['name']:<20} {passaram}/{len(testes)} teste(s) ok")
    oficial = agente._validar("linha-de-base", isa_antiga, None)
    base = {"isa": isa_antiga, "componentes": componentes,
            "spec_riscv_test": placar_de(oficial).texto()}
    agente._log({"evento": "linha_de_base", **base})
    return base


def _diff_contrato(anterior: str, novo: str) -> str:
    linhas = difflib.unified_diff(anterior.splitlines(), novo.splitlines(),
                                  "contrato anterior", "contrato novo", n=1, lineterm="")
    return "\n".join(linhas) or "(no textual change)"


# -- plano -------------------------------------------------------------------

_SCHEMA_PLANO = {
    "type": "object",
    "properties": {
        "understanding": {"type": "string"},
        "blocks": {"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string"},
            "action": {"type": "string", "enum": list(ACOES)},
            "from": {"type": "array", "items": {"type": "string"}},
            "change": {"type": "string"},
            "responsibility": {"type": "string"},
            "ports": {"type": "array", "items": {"type": "string"}},
            "depends_on": {"type": "array", "items": {"type": "string"}},
            "design_rationale": {"type": "string"}},
            "required": ["name", "action"]}},
    },
    "required": ["understanding", "blocks"],
}


def _portas(valor: object) -> list[str] | None:
    """Portas do plano: lista ou um texto só separado por `;` (as duas formas aparecem)."""
    if valor is None:
        return None
    itens = valor.split(";") if isinstance(valor, str) else valor
    if not isinstance(itens, list):
        raise ValueError
    return [" ".join(str(p).split()) for p in itens if str(p).strip()]


def _mesmas_portas(a: list[str], b: list[str]) -> bool:
    normal = lambda portas: [" ".join(p.lower().split()) for p in portas]  # noqa: E731
    return normal(a) == normal(b)


def _lista(valor: object) -> list[str] | None:
    if valor is None:
        return None
    if not isinstance(valor, list):
        raise ValueError
    return [str(v).strip().lower() for v in valor]


def aplicar_plano(arq: dict, bruto: object, max_blocos: int = 8
                  ) -> tuple[dict | None, dict[str, dict], list[str], str]:
    """Aplica a decomposição-alvo do plano à arquitetura antiga.

    Devolve (arquitetura nova, ações, removidos, motivo). ``ações`` é
    ``{bloco: {"acao": keep|change|new, "de": [blocos antigos], "mudanca": texto}}``;
    ``removidos`` são os blocos antigos que nenhum bloco novo mantém nem usa
    como origem. ``motivo`` vem vazio quando o plano é válido.
    """
    if not isinstance(bruto, dict) or not isinstance(bruto.get("blocks"), list):
        return None, {}, [], "a resposta não tem a lista `blocks` (a decomposição-alvo inteira)"
    antigos = {b["name"]: b for b in arq["blocks"]}
    alvo: list[dict] = []
    acoes: dict[str, dict] = {}
    try:
        for item in bruto["blocks"]:
            if not isinstance(item, dict):
                return None, {}, [], "um item de `blocks` não é objeto"
            nome = str(item.get("name", "")).strip().lower()
            acao = str(item.get("action", "")).strip().lower()
            if acao not in ACOES:
                return None, {}, [], f"`{nome}`: action precisa ser keep, change ou new"
            de = _lista(item.get("from"))
            portas = _portas(item.get("ports"))
            deps = _lista(item.get("depends_on"))
            antigo = antigos.get(nome)
            if acao == "keep":
                if not antigo:
                    return None, {}, [], f"`{nome}` não existe na CPU de origem; use change ou new"
                if (de not in (None, [nome]) or
                        (portas is not None and not _mesmas_portas(portas, antigo["ports"])) or
                        (deps is not None and sorted(deps) != sorted(antigo["depends_on"]))):
                    return None, {}, [], (f"`{nome}` está como keep, mas muda nome de origem, portas "
                                          "ou dependências; use change")
                bloco = dict(antigo)
            else:
                if acao == "new":
                    de = []
                elif de is None:
                    de = [nome]
                if acao == "change" and not de:
                    return None, {}, [], f"`{nome}`: change precisa dizer de quais blocos vem (`from`)"
                faltam = [d for d in de if d not in antigos]
                if faltam:
                    return None, {}, [], f"`{nome}` vem de bloco inexistente: {', '.join(faltam)}"
                base = antigos.get(de[0]) if de else None
                bloco = {
                    "name": nome,
                    "responsibility": str(item.get("responsibility") or
                                          (base or {}).get("responsibility", "")).strip(),
                    "ports": (portas if portas is not None else
                              list((antigo or base or {}).get("ports", []))),
                    "depends_on": deps if deps is not None else list((antigo or base or {}).get(
                        "depends_on", [])),
                    "design_rationale": str(item.get("design_rationale") or
                                            (base or {}).get("design_rationale", "")).strip(),
                }
            if nome == ct.TOP:
                if acao == "new" or (de not in (None, [ct.TOP])):
                    return None, {}, [], f"`{ct.TOP}` é o topo de sempre: keep ou change, de `{ct.TOP}`"
                bloco["ports"] = list(antigos[ct.TOP]["ports"])   # portas do contrato
            acoes[nome] = {"acao": acao, "de": [nome] if acao == "keep" else de,
                           "mudanca": str(item.get("change", "")).strip() or
                           ("kept" if acao == "keep" else "update for the new specification")}
            alvo.append(bloco)
    except (ValueError, TypeError):
        return None, {}, [], "`from` e `depends_on` precisam ser listas de nomes"
    if ct.TOP not in acoes:
        return None, {}, [], f"falta o topo `{ct.TOP}` na decomposição-alvo"
    if all(a["acao"] == "keep" for a in acoes.values()):
        return None, {}, [], "o plano não muda nenhum bloco"
    usados = {d for a in acoes.values() for d in a["de"]}
    removidos = [n for n in antigos if n not in usados]
    validados, motivo = validar_arquitetura({"blocks": alvo}, max_blocos)
    if not validados:
        return None, {}, [], motivo
    # quem passa a instanciar outro conjunto de blocos precisa mudar
    for bloco in validados:
        a = acoes[bloco["name"]]
        if a["acao"] == "keep":
            deps_antigas = sorted(antigos[bloco["name"]]["depends_on"])
            if sorted(bloco["depends_on"]) != deps_antigas:
                return None, {}, [], f"`{bloco['name']}` muda as dependências; use change"
            if bloco["name"] == ct.TOP and (removidos or any(
                    x["acao"] != "keep" and x["de"] != [n] for n, x in acoes.items())):
                return None, {}, [], (f"blocos foram criados, renomeados ou removidos: o `{ct.TOP}` "
                                      "precisa ser change para instanciar a nova decomposição")
        antigo = antigos.get(bloco["name"], {})
        for chave, valor in antigo.items():
            bloco.setdefault(chave, valor)
    return dict(arq, blocks=validados), acoes, removidos, ""


def _planejar_evolucao(agente: Agente, arq: dict, isa_antiga: str, base: dict, diff: str,
                       max_blocos: int) -> tuple[dict, dict[str, dict], list[str], str]:
    novas = [i for i in ct.instrucoes_da_isa(agente.isa) if i not in ct.instrucoes_da_isa(isa_antiga)]
    blocos = "\n".join(
        f"- {b['name']} ({b['file']}): {b['responsibility']}\n"
        f"  ports: {'; '.join(b['ports']) or '(see contract)'}\n"
        f"  depends on: {', '.join(b.get('depends_on', [])) or 'none'}" for b in arq["blocks"])
    contratos = "\n\n".join(f"## {b['name']}\n{agente._ler_especificacao(b)}"
                            for b in arq["blocks"])
    mensagens = [
        {"role": "system", "content": agente.contrato},
        {"role": "user", "content": (
            f"This project already contains a CPU that was generated and APPROVED by the "
            f"official judge for the PREVIOUS specification ({isa_antiga.upper()}, "
            f"{agente.microarquitetura}). The specification has changed. Your job is to "
            "understand the project and design the target decomposition for the NEW "
            "specification, as a hardware designer would; nothing is modified yet.\n\n"
            "Before planning, every existing test was run again on the approved CPU (baseline):\n"
            f"```json\n{json.dumps(base, ensure_ascii=False, indent=1)}\n```\n\n"
            f"Instructions required now that were not required before: {', '.join(novas) or 'none'}\n\n"
            f"Diff of the system contract (previous -> new):\n```diff\n{diff}\n```\n\n"
            f"Current architecture:\n{blocos}\n\n"
            f"Current semantic contract of each block:\n{contratos}\n\n"
            "Answer ONLY with JSON: {\"understanding\": \"what changed in the specification and "
            "what it means for this CPU\", \"blocks\": [the COMPLETE target decomposition, one "
            "entry per block: {\"name\", \"action\": \"keep\" | \"change\" | \"new\", \"from\": "
            "[previous block names this block is derived from], \"change\": \"what changes and "
            "why\", \"responsibility\", \"ports\", \"depends_on\", \"design_rationale\"}]}.\n"
            "Rules:\n"
            "- The decomposition is free. Keep a block (`keep`) only when it is still correct and "
            "well scoped: it stays frozen with its VHDL and tests. Change, split, merge, rename or "
            "add blocks when that gives a cleaner, more verifiable design: `change` with `from` "
            "naming the previous block(s) it derives from (one previous block in several `from` "
            "lists = split; several previous blocks in one `from` = merge; a different name = "
            "rename), `new` for a block written from scratch. A previous block that appears in no "
            "`name` and no `from` is removed.\n"
            + (f"- The top `{ct.TOP}` only instantiates and connects generated blocks: it must "
               "never contain multiplication, division, remainder or other datapath operations. "
               "New datapath behavior belongs in a generated block that can be tested on its own.\n"
               if agente.topo_sem_conta else "") +
            f"- `{ct.TOP}` is always present and its ports are fixed by the contract; if any block "
            f"is created, renamed or removed, `{ct.TOP}` must be `change`.\n"
            f"- 2 to {max_blocos} blocks; lowercase names; `ports` are VHDL port declarations; "
            "`depends_on` lists the generated blocks a block instantiates.")},
    ]
    agente.relatar("[1] planejando a decomposição-alvo a partir do diff das specs ...")
    motivo = ""
    for _ in (1, 2):
        r = agente._chamar("plano_evolucao", "evolucao/plano.json", mensagens,
                           schema=_SCHEMA_PLANO, temperatura=0.0)
        try:
            bruto = extrair_json(r.texto)
        except ErroLLM as e:
            bruto, motivo = None, str(e)
        if bruto is not None:
            novo, acoes, removidos, motivo = aplicar_plano(arq, bruto, max_blocos)
            if novo:
                return novo, acoes, removidos, str(bruto.get("understanding", "")).strip()
        mensagens += [{"role": "assistant", "content": r.texto},
                      {"role": "user", "content": f"That plan is invalid: {motivo}. Send the JSON again."}]
    agente._log({"evento": "plano_evolucao_invalido", "motivo": motivo})
    raise ErroGeracao(f"o modelo não produziu um plano de evolução válido: {motivo}")


def _gravar_plano(agente: Agente, origem: str, isa_antiga: str, base: dict, entendimento: str,
                  acoes: dict[str, dict], removidos: list[str]) -> None:
    pasta = agente.sessao / "evolucao"
    dados = {"origem": origem, "isa_anterior": isa_antiga, "isa_nova": agente.isa,
             "linha_de_base": base, "entendimento": entendimento, "blocos": acoes,
             "removidos": removidos}
    (pasta / "plano.json").write_text(json.dumps(dados, indent=2, ensure_ascii=False) + "\n",
                                      encoding="utf-8")
    nomes = {"keep": "mantido (congelado)", "change": "muda", "new": "novo"}
    linhas = [f"# Plano de evolução: {isa_antiga.upper()} -> {agente.isa.upper()}", "",
              f"Origem: `{origem}`", "", "## Linha de base (antes de mudar)", "",
              f"- spec-riscv-test ({isa_antiga}): {base['spec_riscv_test']}"]
    linhas += [f"- {nome}: {v['passaram']}/{v['total']} teste(s) de componente ok"
               for nome, v in base["componentes"].items()]
    linhas += ["", "## Entendimento da IA", "", entendimento or "(vazio)", "",
               "## Decomposição-alvo", "", "| Bloco | Ação | De | O que muda |", "|---|---|---|---|"]
    for nome, a in acoes.items():
        texto = a["mudanca"].replace("|", "/").replace("\n", " ")
        linhas.append(f"| `{nome}` | {nomes[a['acao']]} | {', '.join(a['de']) or '-'} | {texto} |")
    linhas += ["", "## Removidos", ""] + ([f"- `{n}`" for n in removidos] or ["- (nenhum)"])
    (pasta / "plano.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    agente._log({"evento": "plano_evolucao", **{k: v for k, v in dados.items() if k != "linha_de_base"}})
    agente.relatar(f"  entendimento: {agente._linha_curta(entendimento)}")
    for nome, a in acoes.items():
        origem_txt = "" if a["de"] in ([nome], []) else f" (de {', '.join(a['de'])})"
        agente.relatar(f"  {nomes[a['acao']]:<20} {nome}{origem_txt}: "
                       f"{agente._linha_curta(a['mudanca'], 140)}")
    for nome in removidos:
        agente.relatar(f"  {'removido':<20} {nome}")


# -- execução ----------------------------------------------------------------

def _evoluir_especificacao(agente: Agente, bloco: dict, arq: dict, mudanca: str, diff: str,
                           anterior: str, anteriores_txt: str) -> None:
    """Contrato novo a partir do(s) contrato(s) de origem."""
    mensagens = [
        {"role": "system", "content": agente.contrato},
        {"role": "user", "content": (
            f"Update the semantic contract for component `{bloco['name']}`. The CPU "
            "specification changed and this component must change with it. Return replacement "
            "Markdown with exactly these six level-2 headings: `## Timing`, `## Reset`, "
            "`## Behavior`, `## Operations`, `## Edge cases`, and `## Test strategy`. Do not "
            "include Public interface or Responsibility. Keep every rule of the previous "
            "contract(s) that still applies to this component; make every new or changed rule "
            "explicit, including encodings and edge cases, and extend the Test strategy to "
            "cover them.\n"
            f"Responsibility now: {bloco['responsibility']}\n"
            f"{agente._decomposicao_fixa(bloco, arq)}\n\n"
            f"Required change (from the evolution plan): {mudanca}\n\n"
            f"Diff of the system contract (previous -> new):\n```diff\n{diff}\n```\n\n"
            f"Public interface now:\n```vhdl\n{agente._interface_do_bloco(bloco)}\n```\n\n"
            f"Previous contract(s) this component derives from:\n{anteriores_txt}\n\n"
            "Semantic contracts of direct dependencies:\n"
            f"{agente._especificacoes_dependencias(bloco, arq)}")},
    ]
    agente.relatar(f"  atualizando contrato semantico de {bloco['file']} ...")
    for _ in (1, 2):
        r = agente._chamar("evolucao_especificacao",
                           agente._caminho_especificacao(bloco).relative_to(agente.pasta).as_posix(),
                           mensagens)
        try:
            corpo, preservadas = agente._completar_revisao_de_spec(r.texto, anterior)
            agente._salvar_especificacao(bloco, corpo)
            agente._log({"evento": "especificacao_evoluida", "bloco": bloco["name"],
                         "anterior": anteriores_txt, "mudanca": mudanca,
                         "secoes_preservadas": list(preservadas)})
            return
        except (ErroLLM, KeyError, AttributeError, TypeError, ValueError):
            pass
        mensagens += [{"role": "assistant", "content": r.texto},
                      {"role": "user", "content":
                       "Return only Markdown with exactly these headings: ## Timing, ## Reset, "
                       "## Behavior, ## Operations, ## Edge cases, and ## Test strategy."}]
    raise ErroGeracao(f"o modelo não atualizou o contrato de {bloco['file']}")


def _arquivar_testes(agente: Agente, bloco: dict) -> int:
    """Testes do bloco (mesmo nome) viram casos de regressão; smoke e expansão recomeçam."""
    destino = agente.sessao / "testes_casos" / bloco["name"] / "publicos"
    destino.mkdir(parents=True, exist_ok=True)
    smoke = agente._caminho_teste(bloco)
    if smoke.exists():
        shutil.move(str(smoke), destino / f"anterior-{smoke.name}")
    snapshot = agente._caminho_snapshot_teste(smoke)
    if snapshot.exists():
        snapshot.unlink()
    for caso in sorted(destino.glob("*.py")):
        if not caso.name.startswith("anterior-"):
            caso.rename(destino / f"anterior-{caso.name}")
    return len(list(destino.glob("anterior-*.py")))


def _retirar_bloco_antigo(agente: Agente, nome: str) -> None:
    """Bloco antigo sem lugar na decomposição nova: sai de src/ e da sessão ativa."""
    destino = agente.sessao / "evolucao" / "removidos" / nome
    destino.mkdir(parents=True, exist_ok=True)
    origens = [agente.pasta / "src" / f"{nome}.vhd",
               agente.sessao / "component_specs" / f"{nome}.comp_spec.txt",
               agente.sessao / "componentes_aprovados" / f"{nome}.json",
               agente.sessao / "hierarquia" / f"{nome}.json",
               *(agente.sessao / "testes").glob(f"test_{nome}.py"),
               *(agente.sessao / "testes_aprovados").glob(f"test_{nome}.py"),
               agente.sessao / "testes_casos" / nome]
    for caminho in origens:
        if caminho.exists():
            shutil.move(str(caminho), destino / caminho.name)


def evoluir(agente: Agente, origem: Path) -> Resultado:
    """Evolui a CPU aprovada em ``origem`` para as specs atuais do agente."""
    inicio = time.monotonic()
    if not agente.testes_componentes or not agente.gates_componentes:
        raise ErroGeracao("evoluir exige --testes-componentes e --gates-componentes: são os "
                          "testes e as aprovações por bloco que permitem mudar só o necessário")
    origem = Path(origem).resolve()
    sessao_o = sessao_aprovada(origem)
    inicio_o = next(e for e in _eventos(sessao_o) if e.get("evento") == "inicio")
    isa_antiga = str(inicio_o.get("isa", "rv32i"))
    try:
        rel_origem = origem.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        rel_origem = origem.as_posix()
    selo = agente.protegidos()
    arq = _copiar_origem(agente, origem, sessao_o)
    antigos = {b["name"]: dict(b) for b in arq["blocks"]}
    max_blocos = max(agente.max_blocos, len(arq["blocks"]))
    agente._log({"evento": "inicio", "modo": "evoluir", "pasta": str(agente.pasta),
                 "evoluido_de": rel_origem, "sessao_origem": sessao_o.name,
                 "isa_anterior": isa_antiga, "isa": agente.isa,
                 "provedor": agente.cliente.provedor, "modelo": agente.cliente.modelo,
                 "executor": agente.executor.nome, "iteracoes": agente.iteracoes,
                 "tentativas_revisao_semantica": agente.tentativas_revisao_semantica,
                 "max_casos_teste": agente.max_casos_teste,
                 "max_casos_internos": agente.max_casos_internos, "max_blocos": max_blocos,
                 "topo_sem_conta": agente.topo_sem_conta,
                 "microarquitetura": agente.microarquitetura,
                 "testes_componentes": True, "testes_internos": agente.testes_internos,
                 "regressoes_componentes": agente.regressoes_componentes,
                 "gates_componentes": True, "specs": ct.descrever_pasta_specs()})
    agente.relatar(f"evoluindo {rel_origem} ({isa_antiga.upper()}, sessão {sessao_o.name}) "
                   f"para {agente.isa.upper()}")

    # 0. entender: tudo roda antes de qualquer mudança
    base = _linha_de_base(agente, arq, isa_antiga)
    diff = _diff_contrato(
        (agente.sessao / "evolucao" / "contrato-anterior.txt").read_text(encoding="utf-8"),
        agente.contrato)
    (agente.sessao / "evolucao" / "diff-contrato.diff").write_text(diff + "\n", encoding="utf-8")

    # 1. planejar a decomposição-alvo
    arq, acoes, removidos, entendimento = _planejar_evolucao(
        agente, arq, isa_antiga, base, diff, max_blocos)
    arq.update(isa=agente.isa, evolucao={"de": rel_origem, "sessao": sessao_o.name,
                                         "isa_anterior": isa_antiga})
    _gravar_plano(agente, rel_origem, isa_antiga, base, entendimento, acoes, removidos)
    mantidos = {n for n, a in acoes.items() if a["acao"] == "keep"}
    # a expansão de testes dos blocos mantidos já terminou na origem
    for evento in _eventos(sessao_o):
        if evento.get("evento") == "testbench_expansao_concluida" and evento.get("bloco") in mantidos:
            agente._log({**{k: v for k, v in evento.items() if k not in ("t", "escopo", "pai")},
                         "herdado_de": sessao_o.name})

    # o que os blocos de origem eram, lido antes de qualquer remoção
    vhdl_antigo = {n: (agente.pasta / b["file"]).read_text(encoding="utf-8")
                   for n, b in antigos.items() if (agente.pasta / b["file"]).exists()}
    spec_antiga = {n: agente._ler_especificacao(b) for n, b in antigos.items()
                   if agente._caminho_especificacao(b).exists()}
    alvo = {b["name"] for b in arq["blocks"]}
    for nome in antigos:
        if nome not in alvo:
            _retirar_bloco_antigo(agente, nome)
    for bloco in arq["blocks"]:
        a = acoes[bloco["name"]]
        if a["acao"] == "keep":
            continue
        # interface nova ou bloco que mudou de origem: a declaração vem da arquitetura
        fonte = agente._destino(bloco["file"])
        no_lugar = a["de"] == [bloco["name"]]
        if fonte.exists() and not (no_lugar and bloco["ports"] == antigos[bloco["name"]]["ports"]):
            fonte.unlink()
        for velho in (agente.sessao / "componentes_aprovados" / f"{bloco['name']}.json",
                      agente.sessao / "hierarquia" / f"{bloco['name']}.json"):
            if velho.exists():
                velho.unlink()
    arq["instructions"] = agente._inventariar_instrucoes()
    (agente.pasta / "architecture.json").write_text(
        json.dumps(arq, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # 2. contratos dos blocos que mudam ou nascem
    agente.relatar("[2] contratos dos blocos que mudam ...")
    for bloco in arq["blocks"]:
        a = acoes[bloco["name"]]
        if a["acao"] == "keep":
            continue
        if a["acao"] == "new":
            agente._escrever_especificacao(bloco, arq)
        else:
            anteriores_txt = "\n\n".join(f"### {d}\n{spec_antiga.get(d, '(none)')}" for d in a["de"])
            _evoluir_especificacao(agente, bloco, arq, a["mudanca"], diff,
                                   spec_antiga.get(a["de"][0], ""), anteriores_txt)
        agente._validar_especificacao_por_agente(bloco, arq)

    # 3. VHDL e testes, na ordem da arquitetura
    usados = 0
    base_casos = agente.max_casos_teste
    for k, bloco in enumerate(arq["blocks"], start=1):
        a = acoes[bloco["name"]]
        if a["acao"] == "keep":
            agente.relatar(f"[3] {k}/{len(arq['blocks'])} {bloco['name']}: mantido; "
                           "rodando os testes dele de novo ...")
            usados = agente._testar_componentes(arq, usados, [bloco], reutilizar_testes=True)
        else:
            herdados = 0
            if a["de"] == [bloco["name"]]:
                herdados = _arquivar_testes(agente, bloco)
            origem_vhdl = "\n\n".join(f"-- previous {d}.vhd\n{vhdl_antigo[d]}"
                                      for d in a["de"] if d in vhdl_antigo) or None
            agente.relatar(f"[3] {k}/{len(arq['blocks'])} {bloco['name']}: {a['acao']}"
                           + (f" (de {', '.join(a['de'])})" if a["de"] not in ([bloco['name']], [])
                              else "")
                           + (f"; {herdados} teste(s) antigo(s) viram regressão" if herdados else "")
                           + " ...")
            agente._escrever_bloco(bloco, arq, k, len(arq["blocks"]), anterior=origem_vhdl)
            # os casos herdados não consomem o orçamento de casos novos
            agente.max_casos_teste = base_casos + herdados
            try:
                usados = agente._testar_componentes(arq, usados, [bloco], reutilizar_testes=True)
            finally:
                agente.max_casos_teste = base_casos
        agente._congelar_bloco(bloco)

    # 4. juiz na ISA nova, com o laço de correção de sempre
    ultima, etapa, iteracoes = agente._corrigir(arq, usados)
    if agente.protegidos() != selo:
        agente._log({"evento": "integridade", "ok": False})
        raise ErroIntegridade("um arquivo protegido mudou durante a evolução; o veredito foi recusado")
    final = ultima if etapa == "suite" else agente._validar("final", agente.isa, None)
    p = placar_de(final)
    atingido = p.veredito == "aprovado"
    resultado = Resultado(
        veredito=p.veredito or "desconhecido", objetivo_atingido=atingido, placar=p,
        iteracoes=iteracoes, chamadas=agente._chamadas, tokens_entrada=agente._tokens[0],
        tokens_saida=agente._tokens[1], segundos=round(time.monotonic() - inicio, 1),
        sessao=agente.sessao, relatorio=final.json_path, totais_sessao=agente._totais_da_sessao())
    resumo = {"veredito": resultado.veredito, "objetivo_atingido": atingido, "placar": p.texto(),
              "iteracoes": iteracoes, "chamadas": resultado.chamadas,
              "tokens_entrada": resultado.tokens_entrada, "tokens_saida": resultado.tokens_saida,
              "segundos": resultado.segundos, "provedor": agente.cliente.provedor,
              "modelo": agente.cliente.modelo, "microarquitetura": agente.microarquitetura,
              "isa": agente.isa, "testes_componentes": True,
              "regressoes_componentes": agente.regressoes_componentes, "gates_componentes": True,
              "evolucao": {"de": rel_origem, "sessao": sessao_o.name, "isa_anterior": isa_antiga,
                           "blocos": acoes, "removidos": removidos,
                           "mudaram": sorted(n for n, a in acoes.items() if a["acao"] != "keep"),
                           "congelados": sorted(mantidos), "linha_de_base": base},
              "relatorio": final.json_path.relative_to(agente.pasta).as_posix(),
              "sessao": resultado.totais_sessao}
    (agente.sessao / "resultado.json").write_text(
        json.dumps(resumo, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    agente._log({"evento": "fim", **resumo})
    return resultado
