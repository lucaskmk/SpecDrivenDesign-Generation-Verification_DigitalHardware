"""`rvgen evoluir`: muda uma CPU já aprovada para specs novas, sem gerar do zero.

Exemplo: a CPU RV32I aprovada em ``experimentos/luna6_prof_3`` vira RV32IM.
O fluxo segue a sugestão do professor: primeiro roda tudo e entende as specs,
só depois altera.

0. Entender: copia a CPU aprovada (VHDL, arquitetura, contratos dos blocos,
   testes e registros de aprovação) para uma pasta nova e roda, sem IA, todos
   os testes de componente e o juiz na ISA antiga. Essa é a linha de base.
1. Planejar: uma chamada à IA lê o diff entre o contrato antigo e o novo, as
   instruções novas, a arquitetura, o contrato de cada bloco e a linha de base,
   e responde quais blocos mudam (e se precisa de bloco novo). O plano fica em
   ``evolucao/plano.md`` na sessão.
2. Contratos: só os blocos do plano têm o contrato atualizado (e revisado pelo
   revisor semântico de sempre); bloco novo ganha contrato do zero.
3. VHDL e testes, na ordem da arquitetura: bloco do plano é reescrito a partir
   do VHDL aprovado; os testes antigos dele viram casos de regressão, e a IA
   acrescenta casos novos para o que mudou. Bloco fora do plano fica como
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
from .config import REPO_ROOT
from .agente import (Agente, ErroGeracao, ErroIntegridade, ErroLLM, Resultado,
                     extrair_json, placar_de, validar_arquitetura)

__all__ = ["sessao_aprovada", "evoluir"]

# o que a sessão de origem guarda e a sessão nova herda
_HERDADO = ("component_specs", "testes", "testes_aprovados", "testes_casos",
            "componentes_aprovados", "regressoes", "hierarquia")


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
    blocos, motivo = validar_arquitetura(arq)
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


_SCHEMA_PLANO = {
    "type": "object",
    "properties": {
        "understanding": {"type": "string"},
        "changes": {"type": "array", "items": {"type": "object", "properties": {
            "block": {"type": "string"}, "change": {"type": "string"},
            "ports": {"type": "array", "items": {"type": "string"}},
            "depends_on": {"type": "array", "items": {"type": "string"}}},
            "required": ["block", "change"]}},
        "new_blocks": {"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string"}, "responsibility": {"type": "string"},
            "ports": {"type": "array", "items": {"type": "string"}},
            "depends_on": {"type": "array", "items": {"type": "string"}},
            "design_rationale": {"type": "string"}},
            "required": ["name", "responsibility", "ports"]}},
    },
    "required": ["understanding", "changes"],
}


def aplicar_plano(arq: dict, bruto: object) -> tuple[dict | None, dict[str, str], str]:
    """Arquitetura nova, {bloco: mudança} e motivo (vazio quando o plano é válido)."""
    if not isinstance(bruto, dict) or not isinstance(bruto.get("changes"), list):
        return None, {}, "a resposta não tem a lista `changes`"
    por_nome = {b["name"]: dict(b) for b in arq["blocks"]}
    novos = bruto.get("new_blocks") or []
    if not isinstance(novos, list):
        return None, {}, "`new_blocks` precisa ser uma lista"
    nomes_novos = []
    for novo in novos:
        if not isinstance(novo, dict):
            return None, {}, "um item de `new_blocks` não é objeto"
        nome = str(novo.get("name", "")).strip().lower()
        if nome in por_nome:
            return None, {}, f"bloco novo {nome!r} já existe"
        nomes_novos.append(nome)
    mudancas: dict[str, str] = {}
    for item in bruto["changes"]:
        if not isinstance(item, dict):
            return None, {}, "um item de `changes` não é objeto"
        nome = str(item.get("block", "")).strip().lower()
        if nome not in por_nome and nome not in nomes_novos:
            return None, {}, f"`changes` cita bloco inexistente {nome!r}"
        mudancas[nome] = str(item.get("change", "")).strip() or "update for the new specification"
        if nome in por_nome:
            if item.get("ports"):
                if nome == ct.TOP:
                    return None, {}, f"as portas do `{ct.TOP}` são do contrato e não mudam"
                por_nome[nome]["ports"] = [str(p) for p in item["ports"]]
            if item.get("depends_on") is not None:
                por_nome[nome]["depends_on"] = [str(d).strip().lower() for d in item["depends_on"]]
    if not mudancas and not nomes_novos:
        return None, {}, "o plano não muda nenhum bloco"
    for nome in nomes_novos:
        mudancas.setdefault(nome, "new block")
        # quem instancia um bloco novo também muda
        donos = [b for b in por_nome.values() if nome in b.get("depends_on", [])]
        for dono in donos or [por_nome[ct.TOP]]:
            if nome not in dono["depends_on"]:
                dono["depends_on"] = [*dono["depends_on"], nome]
            mudancas.setdefault(dono["name"], f"instantiate the new block `{nome}`")
    ordem = [b["name"] for b in arq["blocks"] if b["name"] != ct.TOP]
    blocos = [por_nome[n] for n in ordem] + list(novos) + [por_nome[ct.TOP]]
    validados, motivo = validar_arquitetura({"blocks": blocos})
    if not validados:
        return None, {}, motivo
    # validar_arquitetura normaliza; mantém campos extras dos blocos antigos
    for bloco in validados:
        antigo = por_nome.get(bloco["name"])
        if antigo:
            for chave, valor in antigo.items():
                bloco.setdefault(chave, valor)
    return dict(arq, blocks=validados), mudancas, ""


def _planejar_evolucao(agente: Agente, arq: dict, isa_antiga: str, base: dict,
                       diff: str) -> tuple[dict, dict[str, str], str]:
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
            "understand the project and plan the SMALLEST change that satisfies the new "
            "specification; nothing is modified yet.\n\n"
            "Before planning, every existing test was run again on the approved CPU (baseline):\n"
            f"```json\n{json.dumps(base, ensure_ascii=False, indent=1)}\n```\n\n"
            f"Instructions required now that were not required before: {', '.join(novas) or 'none'}\n\n"
            f"Diff of the system contract (previous -> new):\n```diff\n{diff}\n```\n\n"
            f"Current architecture:\n{blocos}\n\n"
            f"Current semantic contract of each block:\n{contratos}\n\n"
            "Answer ONLY with JSON: {\"understanding\": \"what changed in the specification and "
            "what it means for this CPU\", \"changes\": [{\"block\", \"change\", \"ports\" "
            "(optional: the complete new port list), \"depends_on\" (optional)}], "
            "\"new_blocks\": [{\"name\", \"responsibility\", \"ports\", \"depends_on\", "
            "\"design_rationale\"}]}.\n"
            f"Rules: blocks not listed in `changes` stay frozen (VHDL and tests kept); never "
            f"rename or remove a block; the ports of `{ct.TOP}` are fixed by the contract; a new "
            "block must be instantiated by a block listed in `changes` (normally the one that "
            "lists it in `depends_on`); prefer changing existing blocks over adding new ones "
            "unless a separate block is clearly simpler to verify.")},
    ]
    agente.relatar("[1] planejando a mudança a partir do diff das specs ...")
    motivo = ""
    for _ in (1, 2):
        r = agente._chamar("plano_evolucao", "evolucao/plano.json", mensagens,
                           schema=_SCHEMA_PLANO, temperatura=0.0)
        try:
            bruto = extrair_json(r.texto)
        except ErroLLM as e:
            bruto, motivo = None, str(e)
        if bruto is not None:
            novo, mudancas, motivo = aplicar_plano(arq, bruto)
            if novo:
                entendimento = str(bruto.get("understanding", "")).strip()
                return novo, mudancas, entendimento
        mensagens += [{"role": "assistant", "content": r.texto},
                      {"role": "user", "content": f"That plan is invalid: {motivo}. Send the JSON again."}]
    agente._log({"evento": "plano_evolucao_invalido", "motivo": motivo})
    raise ErroGeracao(f"o modelo não produziu um plano de evolução válido: {motivo}")


def _gravar_plano(agente: Agente, origem: Path, isa_antiga: str, base: dict,
                  entendimento: str, mudancas: dict[str, str], arq: dict) -> None:
    pasta = agente.sessao / "evolucao"
    dados = {"origem": origem.as_posix(), "isa_anterior": isa_antiga, "isa_nova": agente.isa,
             "linha_de_base": base, "entendimento": entendimento, "mudancas": mudancas,
             "congelados": [b["name"] for b in arq["blocks"] if b["name"] not in mudancas]}
    (pasta / "plano.json").write_text(json.dumps(dados, indent=2, ensure_ascii=False) + "\n",
                                      encoding="utf-8")
    linhas = [f"# Plano de evolução: {isa_antiga.upper()} -> {agente.isa.upper()}", "",
              f"Origem: `{origem.as_posix()}`", "", "## Linha de base (antes de mudar)", "",
              f"- spec-riscv-test ({isa_antiga}): {base['spec_riscv_test']}"]
    linhas += [f"- {nome}: {v['passaram']}/{v['total']} teste(s) de componente ok"
               for nome, v in base["componentes"].items()]
    linhas += ["", "## Entendimento da IA", "", entendimento or "(vazio)", "", "## Blocos que mudam", ""]
    linhas += [f"- `{nome}`: {texto}" for nome, texto in mudancas.items()]
    linhas += ["", "## Blocos congelados", ""]
    linhas += [f"- `{nome}`" for nome in dados["congelados"]] or ["- (nenhum)"]
    (pasta / "plano.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    agente._log({"evento": "plano_evolucao", **{k: v for k, v in dados.items() if k != "linha_de_base"}})
    agente.relatar(f"  entendimento: {agente._linha_curta(entendimento)}")
    for nome, texto in mudancas.items():
        agente.relatar(f"  muda   {nome:<20} {agente._linha_curta(texto, 160)}")
    for nome in dados["congelados"]:
        agente.relatar(f"  mantém {nome:<20} (VHDL e testes congelados)")


def _evoluir_especificacao(agente: Agente, bloco: dict, arq: dict, mudanca: str, diff: str) -> None:
    anterior = agente._ler_especificacao(bloco)
    mensagens = [
        {"role": "system", "content": agente.contrato},
        {"role": "user", "content": (
            f"Update the semantic contract for component `{bloco['name']}`. The CPU "
            "specification changed and this component must change with it. Return replacement "
            "Markdown with exactly these six level-2 headings: `## Timing`, `## Reset`, "
            "`## Behavior`, `## Operations`, `## Edge cases`, and `## Test strategy`. Do not "
            "include Public interface or Responsibility. Keep every rule of the current "
            "contract that still holds; make every new or changed rule explicit, including "
            "encodings and edge cases, and extend the Test strategy to cover them.\n"
            f"{agente._decomposicao_fixa(bloco, arq)}\n\n"
            f"Required change (from the evolution plan): {mudanca}\n\n"
            f"Diff of the system contract (previous -> new):\n```diff\n{diff}\n```\n\n"
            f"Public interface now:\n```vhdl\n{agente._interface_do_bloco(bloco)}\n```\n\n"
            f"Current contract:\n{anterior}\n\n"
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
                         "anterior": anterior, "mudanca": mudanca,
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
    """Testes do bloco viram casos de regressão; o smoke e a expansão recomeçam."""
    destino = agente.sessao / "testes_casos" / bloco["name"] / "publicos"
    destino.mkdir(parents=True, exist_ok=True)
    smoke = agente._caminho_teste(bloco)
    movidos = 0
    if smoke.exists():
        shutil.move(str(smoke), destino / f"anterior-{smoke.name}")
        movidos += 1
    snapshot = agente._caminho_snapshot_teste(smoke)
    if snapshot.exists():
        snapshot.unlink()
    for caso in sorted(destino.glob("*.py")):
        if not caso.name.startswith("anterior-"):
            caso.rename(destino / f"anterior-{caso.name}")
            movidos += 1
    registro = agente.sessao / "componentes_aprovados" / f"{bloco['name']}.json"
    if registro.exists():
        registro.unlink()
    return len(list(destino.glob("anterior-*.py")))


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
    portas_antigas = {b["name"]: list(b["ports"]) for b in arq["blocks"]}
    agente._log({"evento": "inicio", "modo": "evoluir", "pasta": str(agente.pasta),
                 "evoluido_de": rel_origem, "sessao_origem": sessao_o.name,
                 "isa_anterior": isa_antiga, "isa": agente.isa,
                 "provedor": agente.cliente.provedor, "modelo": agente.cliente.modelo,
                 "executor": agente.executor.nome, "iteracoes": agente.iteracoes,
                 "tentativas_revisao_semantica": agente.tentativas_revisao_semantica,
                 "max_casos_teste": agente.max_casos_teste,
                 "max_casos_internos": agente.max_casos_internos,
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

    # 1. planejar
    arq, mudancas, entendimento = _planejar_evolucao(agente, arq, isa_antiga, base, diff)
    arq.update(isa=agente.isa, evolucao={"de": rel_origem, "sessao": sessao_o.name,
                                         "isa_anterior": isa_antiga})
    _gravar_plano(agente, origem, isa_antiga, base, entendimento, mudancas, arq)
    # a expansão de testes dos blocos congelados já terminou na origem
    for evento in _eventos(sessao_o):
        if evento.get("evento") == "testbench_expansao_concluida" and \
                evento.get("bloco") not in mudancas:
            agente._log({**{k: v for k, v in evento.items() if k not in ("t", "escopo", "pai")},
                         "herdado_de": sessao_o.name})
    arq["instructions"] = agente._inventariar_instrucoes()
    (agente.pasta / "architecture.json").write_text(
        json.dumps(arq, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # 2. contratos dos blocos que mudam
    agente.relatar("[2] contratos dos blocos que mudam ...")
    anteriores: dict[str, str] = {}
    for bloco in arq["blocks"]:
        if bloco["name"] not in mudancas:
            continue
        fonte = agente._destino(bloco["file"])
        if fonte.exists():
            anteriores[bloco["name"]] = fonte.read_text(encoding="utf-8")
            # portas novas: a interface passa a vir da arquitetura, não do VHDL antigo
            if bloco["ports"] != portas_antigas.get(bloco["name"], bloco["ports"]):
                fonte.unlink()
        if agente._caminho_especificacao(bloco).exists():
            _evoluir_especificacao(agente, bloco, arq, mudancas[bloco["name"]], diff)
        else:
            agente._escrever_especificacao(bloco, arq)
        agente._validar_especificacao_por_agente(bloco, arq)

    # 3. VHDL e testes, na ordem da arquitetura
    usados = 0
    base_casos = agente.max_casos_teste
    for k, bloco in enumerate(arq["blocks"], start=1):
        if bloco["name"] in mudancas:
            agente.relatar(f"[3] {k}/{len(arq['blocks'])} {bloco['name']}: muda "
                           "(testes antigos viram regressão) ...")
            antigos = _arquivar_testes(agente, bloco)
            agente._escrever_bloco(bloco, arq, k, len(arq["blocks"]),
                                   anterior=anteriores.get(bloco["name"]))
            # os casos herdados não consomem o orçamento de casos novos
            agente.max_casos_teste = base_casos + antigos
            try:
                usados = agente._testar_componentes(arq, usados, [bloco], reutilizar_testes=True)
            finally:
                agente.max_casos_teste = base_casos
        else:
            agente.relatar(f"[3] {k}/{len(arq['blocks'])} {bloco['name']}: congelado; "
                           "rodando os testes dele de novo ...")
            usados = agente._testar_componentes(arq, usados, [bloco], reutilizar_testes=True)
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
                           "mudaram": sorted(mudancas),
                           "congelados": sorted(b["name"] for b in arq["blocks"]
                                                if b["name"] not in mudancas),
                           "linha_de_base": base},
              "relatorio": final.json_path.relative_to(agente.pasta).as_posix(),
              "sessao": resultado.totais_sessao}
    (agente.sessao / "resultado.json").write_text(
        json.dumps(resumo, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    agente._log({"evento": "fim", **resumo})
    return resultado
