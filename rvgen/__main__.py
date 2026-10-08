#!/usr/bin/env python3
"""Gerador de CPUs RISC-V por agente -- ponto de entrada.

REQ: FR-RV-43 a FR-RV-50.

    python -m rvgen preparar              confere Ollama, modelo e executor;
                                          oferece instalar/baixar o que faltar
    python -m rvgen preparar --verificar  so confere, nao muda nada
    python -m rvgen preparar --sim        responde "sim" a toda confirmacao
    python -m rvgen gerar entregas/<nome>
                                          gera, valida e corrige ate o veredito
    python -m rvgen gerar ... --provedor openrouter
                                          o mesmo, com um modelo externo
    python -m rvgen gerar ia_mono ...     so um nome: grava em experimentos/ia_mono
    python -m rvgen comparar              experimentos lado a lado (FR-RV-51)

Codigo de saida: 0 quando tudo esta pronto (preparar) ou a CPU atingiu o
objetivo (gerar), 1 com pendencia ou CPU reprovada, 2 com erro de uso, de
configuracao ou de ambiente.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from . import comparar as cmp
from . import contrato as ct
from . import executor as ex
from . import ollama as ol
from .agente import Agente, ErroGeracao, ErroIntegridade
from .config import GEMINI_URL, PROVEDORES, REPO_ROOT, ErroConfig, ler_config
from .llm import ClienteGemini, ClienteOllama, ClienteOpenAI, ErroLLM

VERDE = "\033[32m"
VERMELHO = "\033[31m"
AMARELO = "\033[33m"
CINZA = "\033[90m"
FIM = "\033[0m"


class Tela:
    """Uma linha por item, no estilo do relatório do validador."""

    def __init__(self, cor: bool) -> None:
        self.cor = cor

    def _c(self, texto: str, tom: str) -> str:
        return f"{tom}{texto}{FIM}" if self.cor else texto

    def ok(self, texto: str) -> None:
        print(f"  {self._c('ok   ', VERDE)}  {texto}", flush=True)

    def falta(self, texto: str, resolver: str | None = None) -> None:
        print(f"  {self._c('FALTA', VERMELHO)}  {texto}", flush=True)
        if resolver:
            print(f"         {self._c('resolver: ' + resolver, CINZA)}", flush=True)

    def info(self, texto: str) -> None:
        print(f"  {self._c('info ', AMARELO)}  {texto}", flush=True)


def _tamanho(n: int) -> str:
    """Bytes na unidade que faz sentido: uma camada de 400 bytes nao e 0.00 GB."""
    if n >= 1e9:
        return f"{n / 1e9:.2f} GB"
    if n >= 1e6:
        return f"{n / 1e6:.1f} MB"
    return f"{max(n, 1) / 1e3:.1f} KB"


def _progresso_download(interativo: bool):
    """Uma linha por etapa do download; no terminal, reescrita no lugar.

    O Ollama anuncia cada camada (`pulling <digest>`) antes de mandar o
    progresso dela, com o MESMO status: por isso a linha so muda quando o
    status muda, e cada camada ocupa uma linha so.
    """
    ultimo: dict = {"status": None, "decil": None}

    def mostrar(status: str, feito: int | None, total: int | None) -> None:
        numeros, decil = "", None
        if feito is not None and total:
            pct = int(100 * feito / total)
            decil = pct // 10
            numeros = f"{pct:3d}%  ({_tamanho(feito)} de {_tamanho(total)})"
        novo = status != ultimo["status"]
        texto = f"         {status[:28]:<28} {numeros}"
        if interativo:
            if novo and ultimo["status"] is not None:
                print()
            print(f"\r{texto:<78}", end="", flush=True)
        elif novo or decil != ultimo["decil"]:
            print(texto.rstrip(), flush=True)
        ultimo["status"], ultimo["decil"] = status, decil
    return mostrar


def _interativo() -> bool:
    """Ha alguem no terminal para responder uma confirmacao?"""
    return sys.stdin is not None and sys.stdin.isatty()


def cmd_preparar(args: argparse.Namespace) -> int:
    try:
        cfg = ler_config()
    except ErroConfig as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 2
    interativo = _interativo()
    tela = Tela(cor=not args.sem_cor and sys.stdout.isatty())

    def confirmar(pergunta: str) -> bool:
        """FR-RV-44: nada e instalado nem baixado sem um sim explicito."""
        if args.verificar:
            return False
        if args.sim:
            return True
        if not interativo:
            tela.info("sem terminal interativo e sem --sim: nada sera instalado")
            return False
        resposta = input(f"         {pergunta} [s/N] ").strip().lower()
        return resposta in ("s", "sim", "y", "yes")

    modo = "so verificacao, nada sera alterado" if args.verificar else \
        "pergunta antes de instalar ou baixar"
    print(f"rvgen preparar -- o que o gerador precisa para rodar local ({modo})\n")
    pendencias = 0
    servidor = None   # base + versao do Ollama; None quando o provedor nao e ollama

    if cfg.provedor == "ollama":
        # -- 1. Ollama: servidor, executavel, instalacao -------------------
        candidatos = ol.hosts_candidatos()
        servidor = ol.localizar_servidor(candidatos)
        binario = ol.localizar_binario()
        if servidor is None and binario is None:
            plano = ol.plano_de_instalacao()
            tela.falta("Ollama nao esta instalado", plano.manual or plano.descricao)
            if plano.manual is None and confirmar(f"Instalar o Ollama agora ({plano.descricao})?"):
                try:
                    codigo = ol.executar_plano(plano)
                except ol.ErroOllama as e:
                    codigo = 1
                    tela.falta(f"a instalacao falhou: {e}")
                binario = ol.localizar_binario()
                if codigo == 0 and binario:
                    tela.ok(f"Ollama instalado em {binario}")
                    servidor = ol.localizar_servidor(candidatos)
                else:
                    tela.falta(f"o instalador terminou com codigo {codigo} e o "
                               f"executavel nao foi encontrado", ol.URL_DOWNLOAD)
                    pendencias += 1
            else:
                pendencias += 1
        elif binario is not None:
            tela.ok(f"Ollama instalado em {binario}")

        if servidor is None and binario is not None:
            # o `ollama serve` escuta em OLLAMA_HOST, se definido -- o primeiro candidato
            base_local = candidatos[0]
            if args.verificar:
                tela.falta("o servidor Ollama nao responde",
                           f'"{binario}" serve   (ou abra o app do Ollama)')
                pendencias += 1
            else:
                log = Path(tempfile.gettempdir()) / "rvgen-ollama-serve.log"
                tela.info(f"iniciando `ollama serve` em segundo plano (log: {log})")
                v = ol.iniciar_servidor(binario, log, base=base_local)
                if v:
                    servidor = (base_local, v)
                else:
                    tela.falta("o servidor nao respondeu em 30 s", f"veja o log {log}")
                    pendencias += 1
        if servidor is not None:
            base, versao = servidor
            tela.ok(f"servidor Ollama {versao} em {base}")

        # -- 2. modelo -----------------------------------------------------
        try:
            modelo, origem = ol.resolver_modelo(args.modelo, args.perfil, cfg.modelo)
        except ol.ErroOllama as e:
            print(f"ERRO: {e}", file=sys.stderr)
            return 2
        if servidor is None:
            tela.falta(f"modelo {modelo} ({origem}): nao verificado, sem servidor Ollama")
            pendencias += 1
        else:
            base = servidor[0]
            try:
                instalados = ol.modelos_instalados(base)
            except ol.ErroOllama as e:
                instalados = []
                tela.falta(str(e))
            if ol.tem_modelo(instalados, modelo):
                tela.ok(f"modelo {modelo} ({origem})")
            else:
                tamanho = ol.tamanho_remoto(modelo)
                txt = f"{tamanho / 1e9:.2f} GB" if tamanho else "tamanho desconhecido"
                tela.falta(f"modelo {modelo} nao esta baixado ({origem})",
                           f"python -m rvgen preparar --modelo {modelo}   ({txt})")
                if confirmar(f"Baixar {modelo} agora ({txt}, de registry.ollama.ai)?"):
                    try:
                        ol.baixar_modelo(base, modelo, _progresso_download(interativo))
                        if interativo:
                            print()
                        tela.ok(f"modelo {modelo} baixado")
                    except ol.ErroOllama as e:
                        print()
                        tela.falta(str(e))
                        pendencias += 1
                else:
                    pendencias += 1

    elif cfg.provedor == "vllm":
        # -- vllm: so verifica se o servidor responde ----------------------
        req = urllib.request.Request(f"{cfg.vllm_url}/models")
        if cfg.vllm_key:
            req.add_header("Authorization", f"Bearer {cfg.vllm_key}")
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                r.read()
            tela.ok(f"vLLM respondendo em {cfg.vllm_url}")
        except urllib.error.HTTPError as e:
            # o servidor respondeu mas recusou: chave ausente ou errada
            if e.code in (401, 403):
                tela.falta(f"vLLM em {cfg.vllm_url} exige autenticacao (HTTP {e.code})",
                           "defina RVGEN_VLLM_API_KEY com a chave do servidor")
            else:
                tela.falta(f"vLLM respondeu HTTP {e.code} em {cfg.vllm_url}",
                           "verifique a URL e a configuracao do vLLM")
            pendencias += 1
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            motivo = e.reason if hasattr(e, "reason") else e
            tela.falta(f"vLLM nao responde em {cfg.vllm_url}",
                       f"verifique se o vLLM esta em execucao ({motivo})")
            pendencias += 1

    # -- 3. onde o spec-riscv-test roda -----------------------------------
    pref = args.executor or cfg.executor
    checagens = []
    if pref in ("auto", "local"):
        checagens.append(("local", ex.checar_local()))
    elif pref == "docker":
        checagens.append(("docker", ex.Disponibilidade(
            False, "spec-riscv-test nao esta instalado na imagem Docker",
            "use --executor local; o veredito final requer o ambiente local")))
    prontos = [(n, d) for n, d in checagens if d.pronto]
    if prontos:
        nome, d = prontos[0]
        tela.ok(f"executor do spec-riscv-test: {nome} -- {d.detalhe}")
    else:
        for nome, d in checagens:
            tela.falta(f"executor {nome} do spec-riscv-test: {d.detalhe}", d.como_resolver)
        pendencias += 1

    # -- 4. provedores alternativos (so informacao) -----------------------
    if cfg.openrouter_key:
        tela.info(f"OPENROUTER_API_KEY definida: --provedor openrouter disponivel "
                  f"(modelo padrao {cfg.modelo_externo})")
    else:
        tela.info("OPENROUTER_API_KEY nao definida: so necessaria com --provedor openrouter")
    if cfg.provedor == "vllm":
        tela.info(f"vLLM em {cfg.vllm_url} "
                  f"(chave: {'definida' if cfg.vllm_key else 'nao definida, ok para uso local'})")

    print()
    if pendencias:
        print(f"{pendencias} pendencia(s). Resolva as linhas FALTA acima e rode de novo.")
        return 1
    print("Tudo pronto. Proximo passo:\n"
          "  python -m rvgen gerar entregas/<nome>")
    return 0


class Relator:
    """A tela do `gerar`: cada linha com o tempo decorrido e, enquanto o
    agente espera (o modelo responder, o spec-riscv-test rodar), um contador vivo.

    O agente marca uma espera terminando a linha em "...". No terminal, um
    relogio de fundo reescreve a linha seguinte a cada segundo com os
    segundos de espera e, quando o modelo ja esta respondendo, os caracteres
    recebidos -- assim da para distinguir "o Ollama ainda nem comecou" (fila,
    modelo carregando) de "esta gerando". Fora de terminal, so as linhas.
    """

    def __init__(self, interativo: bool, relogio=None) -> None:
        import os
        import sys
        import threading
        import time

        self.interativo = interativo
        self.colorido = interativo and sys.stdout.isatty() and not os.environ.get("NO_COLOR")
        self._relogio = relogio or time.monotonic
        self.inicio = self._relogio()
        self._trava = threading.Lock()
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None
        self._espera_desde = 0.0
        self._caracteres = 0
        self._viva = False

    def decorrido(self) -> str:
        s = int(self._relogio() - self.inicio)
        return f"{s // 60:02d}:{s % 60:02d}"

    def progresso(self, caracteres: int) -> None:
        self._caracteres = caracteres

    def _tique(self) -> None:
        while not self._parar.wait(1.0):
            with self._trava:
                s = int(self._relogio() - self._espera_desde)
                estado = (f"{self._caracteres} caracteres recebidos" if self._caracteres
                          else "aguardando")
                print(f"\r           {estado}, {s} s", end="   ", flush=True)
                self._viva = True

    def _parar_relogio(self) -> None:
        if self._thread is not None:
            self._parar.set()
            self._thread.join()
            self._thread = None
        if self._viva:
            print("\r" + " " * 60 + "\r", end="", flush=True)
            self._viva = False

    def linha(self, texto: str) -> None:
        import threading

        self._parar_relogio()
        print(f"[{self.decorrido()}] {self._colorir(texto)}", flush=True)
        if self.interativo and texto.rstrip().endswith("..."):
            self._espera_desde = self._relogio()
            self._caracteres = 0
            self._parar = threading.Event()
            self._thread = threading.Thread(target=self._tique, daemon=True)
            self._thread.start()

    def _colorir(self, texto: str) -> str:
        """Cores apenas para resultados e decisões, nunca para logs não-TTY."""
        if not self.colorido:
            return texto
        if texto.startswith("  fluxo:"):
            return (texto.replace("✓", "\033[32m✓\033[0m")
                    .replace("●", "\033[33m●\033[0m"))
        if any(palavra in texto for palavra in ("FALHOU", "ERRO", "piorou", "reprovado")):
            cor = "\033[31m"       # vermelho: falha observada
        elif any(palavra in texto for palavra in ("triagem", "iteracao ", "revisando contrato",
                                                   "corrigindo ", "reversao")):
            cor = "\033[33m"       # amarelo: precisa de nova interação
        elif any(palavra in texto for palavra in (" ok", "escrito  ", "documentadas",
                                                   "aprovado", "PASSOU")):
            cor = "\033[32m"       # verde: etapa concluída
        else:
            return texto
        return f"{cor}{texto}\033[0m"

    def fechar(self) -> None:
        self._parar_relogio()


def resolver_pasta(texto: str) -> Path:
    """Um nome sem diretório vira `experimentos/<nome>`."""
    p = Path(texto)
    if not p.is_absolute() and len(p.parts) == 1:
        p = cmp.PASTA_PADRAO / p
    return p.resolve()


def cmd_comparar(args: argparse.Namespace) -> int:
    alvos = [Path(a) for a in args.pastas] or [cmp.PASTA_PADRAO]
    sessoes = cmp.sessoes(alvos, todas=args.todas)
    if not sessoes:
        onde = ", ".join(str(a) for a in alvos)
        print(f"Nenhuma sessao com resultado em {onde}. Gere uma CPU com "
               f"`python -m rvgen gerar <nome>`.", file=sys.stderr)
        return 1
    # so vai a rede buscar preco se houver algum experimento com modelo
    # EXTERNO: vllm, como ollama, e local e sai como 0
    externos = any(cmp.provedor_de(s) not in ("ollama", "vllm") for s in sessoes)
    precos = None if (args.sem_rede or not externos) else cmp.precos_openrouter()
    linhas = [cmp.linha_de(s, precos) for s in sessoes]
    precos_ok = precos is not None or not externos
    print(cmp.tabela_texto(linhas, precos_ok), end="")
    if args.markdown:
        destino = Path(args.markdown)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(cmp.tabela_markdown(linhas, precos_ok), encoding="utf-8")
        print(f"\ntabela em Markdown: {destino}")
    return 0


def cmd_gerar(args: argparse.Namespace) -> int:
    def erro(texto: str) -> int:
        print(f"ERRO: {texto}", file=sys.stderr)
        return 2

    if args.max_casos_teste < 1:
        return erro("--max-casos-teste deve ser maior que zero")
    if args.max_casos_internos < 1:
        return erro("--max-casos-internos deve ser maior que zero")
    if args.parallel_testes < 1:
        return erro("--parallel-testes deve ser maior que zero")
    if args.tentativas_revisao_semantica < 1:
        return erro("--tentativas-revisao-semantica deve ser maior que zero")

    try:
        cfg = ler_config()
        cpu = ct.ler_configuracao_cpu()
        ct.validar_isa(cpu["isa"])  # antes de qualquer modelo
    except (ErroConfig, ct.ErroContrato) as e:
        return erro(str(e))
    pasta = resolver_pasta(args.pasta)
    sessao_existente = None
    if args.retomar:
        nome = args.retomar.removeprefix("sessao-")
        sessao_existente = pasta / ".rvgen" / f"sessao-{nome}"
        try:
            eventos = [json.loads(linha) for linha in
                       (sessao_existente / "sessao.jsonl").read_text(encoding="utf-8").splitlines()]
            inicio_sessao = next(e for e in eventos if e.get("evento") == "inicio")
        except (OSError, json.JSONDecodeError, StopIteration) as e:
            return erro(f"--retomar {args.retomar}: sessao invalida ou sem evento inicial: {e}")
        args.testes_componentes = bool(inicio_sessao.get("testes_componentes"))
        args.testes_internos = bool(args.testes_internos or inicio_sessao.get("testes_internos"))
        args.regressoes_componentes = bool(inicio_sessao.get("regressoes_componentes"))
        args.gates_componentes = bool(inicio_sessao.get("gates_componentes"))
        args.exemplo = inicio_sessao.get("exemplo")
        args.forcar = True
    if args.regressoes_componentes and not args.testes_componentes:
        return erro("--regressoes-componentes exige --testes-componentes.")
    if args.gates_componentes and not args.testes_componentes:
        return erro("--gates-componentes exige --testes-componentes.")
    try:
        pasta.relative_to(REPO_ROOT)
    except ValueError:
        return erro(f"{pasta} esta fora do repositorio; use entregas/<nome>.")
    if args.exemplo and not any(Path(args.exemplo).glob("src/*.vhd")):
        return erro(f"--exemplo {args.exemplo}: nenhum src/*.vhd ali.")
    descricao = (inicio_sessao.get("descricao") if sessao_existente else
                 args.descricao if args.descricao is not None else cpu["descricao"])
    if args.descricao_arquivo:
        try:
            descricao = Path(args.descricao_arquivo).read_text(encoding="utf-8-sig")
        except OSError as e:
            return erro(f"--descricao-arquivo {args.descricao_arquivo}: {e}")
    if descricao is not None and not descricao.strip():
        return erro("a descricao esta vazia.")
    try:
        executor = ex.escolher_executor(args.executor or cfg.executor, cfg.imagem_docker)
    except ex.ErroExecutor as e:
        return erro(f"{e}\nRode `python -m rvgen preparar` para ver o que falta.")

    relator = Relator(sys.stdout.isatty())
    provedor = args.provedor or cfg.provedor
    if provedor == "ollama":
        servidor = ol.localizar_servidor(ol.hosts_candidatos())
        if servidor is None:
            return erro("nenhum servidor Ollama respondeu. Rode `python -m rvgen preparar`.")
        try:
            modelo, origem = ol.resolver_modelo(args.modelo, args.perfil, cfg.modelo)
            instalados = ol.modelos_instalados(servidor[0])
        except ol.ErroOllama as e:
            return erro(str(e))
        if not ol.tem_modelo(instalados, modelo):
            return erro(f"o modelo {modelo} ({origem}) nao esta baixado. Rode "
                        f"`python -m rvgen preparar --modelo {modelo}`.")
        cliente = ClienteOllama(servidor[0], modelo, num_ctx=cfg.num_ctx,
                                temperatura=cfg.temperatura, timeout=cfg.timeout_s,
                                ao_progredir=relator.progresso)
        onde = f"ollama {modelo} ({origem}) em {servidor[0]}, num_ctx {cfg.num_ctx}"
    elif provedor == "vllm":
        modelo = args.modelo or cfg.modelo_externo
        cliente = ClienteOpenAI(cfg.vllm_url, cfg.vllm_key, modelo,
                                provedor="vllm",
                                temperatura=cfg.temperatura, timeout=cfg.timeout_s)
        onde = f"vllm {modelo} em {cfg.vllm_url}"
    elif provedor == "google":
        if not cfg.gemini_key:
            return erro("GEMINI_API_KEY nao definida (.env ou ambiente).")
        modelo = args.modelo or cfg.gemini_modelo
        cliente = ClienteGemini(cfg.gemini_key, modelo, temperatura=cfg.temperatura, timeout=cfg.timeout_s)
        onde = f"google Gemini {modelo}"
    else:
        if not cfg.openrouter_key:
            return erro("OPENROUTER_API_KEY nao definida (.env ou ambiente).")
        modelo = args.modelo or cfg.modelo_externo
        cliente = ClienteOpenAI(cfg.openrouter_url, cfg.openrouter_key, modelo,
                                temperatura=cfg.temperatura, timeout=cfg.timeout_s)
        onde = f"openrouter {modelo}"

    rel_pasta = pasta.relative_to(REPO_ROOT).as_posix()
    acao = "retomar" if sessao_existente else "gerar"
    print(f"rvgen {acao} -> {rel_pasta}  ({cpu['microarquitetura']}, {cpu['isa']}, de specs/cpu.md)")
    print(f"  modelo  : {onde}")
    print(f"  executor: {executor.nome}; ate {args.iteracoes} iteracoes de correcao"
          + (f"; exemplo: {args.exemplo}" if args.exemplo else ""))
    print(f"  revisao : ate {args.tentativas_revisao_semantica} tentativas semanticas por componente")
    if args.testes_componentes:
        print(f"  expansao: ate {args.max_casos_teste} casos incrementais por componente")
        if args.parallel_testes > 1:
            print(f"  lote    : ate {args.parallel_testes} candidatos gerados em paralelo; simulacao sequencial")
    if args.testes_componentes:
        print("  testes  : componentes VHDL com cocotb antes do spec-riscv-test")
    if args.testes_internos:
        print("  internos: camada Cocotb de integracao via hierarquia inventariada; "
              f"ate {args.max_casos_internos} casos")
    if args.regressoes_componentes:
        print("  regress.: falhas de componente geram testes de regressao permanentes na sessao")
    if args.gates_componentes:
        print("  portoes : cada bloco compila e passa testes antes do proximo")
    if descricao:
        print(f"  descricao: {len(descricao.strip())} caracteres, orienta o modelo abaixo "
               f"do contrato; NAO verificada pelo spec-riscv-test (vai para descricao.md)")
    print("  fases    : [1/5] decomposicao  [2/5] escrita"
          + ("  [3/5] testbenches" if args.testes_componentes else "")
          + "  [4/5] validacao e correcao  [5/5] veredito")
    if provedor == "ollama":
        # tempos medidos nas execucoes reais (16,9, 17,0 e 18,3 min)
        print("  duracao  : com modelo local de 14B, as execucoes reais levaram de 17 a 18 min;"
              " outro pedido no mesmo Ollama entra na fila")
    elif provedor == "vllm":
        print("  duracao  : depende do modelo servido e da GPU do vLLM; "
              "outros pedidos no mesmo vLLM sao enfileirados por ele")
    elif provedor == "google":
        print("  duracao  : depende do modelo Gemini e da fila da API Google")
    print()
    agente = Agente(cliente=cliente, executor=executor, pasta=pasta,
                       microarquitetura=cpu["microarquitetura"],
                         isa=cpu["isa"], iteracoes=args.iteracoes,
                         tentativas_revisao_semantica=args.tentativas_revisao_semantica,
                         max_casos_teste=args.max_casos_teste,
                        max_casos_internos=args.max_casos_internos,
                        parallel_testes=args.parallel_testes,
                     exemplo=Path(args.exemplo) if args.exemplo else None,
                     descricao=descricao, forcar=args.forcar,
                       testes_componentes=args.testes_componentes,
                       testes_internos=args.testes_internos,
                      regressoes_componentes=args.regressoes_componentes,
                       gates_componentes=args.gates_componentes,
                       sessao_existente=sessao_existente,
                       relatar=relator.linha)
    try:
        r = agente.retomar() if sessao_existente else agente.gerar()
    except KeyboardInterrupt:
        relator.fechar()
        if agente.sessao.exists():
            identificador = agente.sessao.name.removeprefix("sessao-")
            comando = shlex.join(["python", "-m", "rvgen", "retomar", rel_pasta,
                                  identificador, "--provedor", provedor, "--modelo", modelo])
            print("\nInterrompido por Ctrl-C. A sessao foi preservada.", file=sys.stderr)
            print(f"Para retomar: {comando}", file=sys.stderr)
        else:
            print("\nInterrompido por Ctrl-C antes de criar uma sessao.", file=sys.stderr)
        return 130
    except ErroIntegridade as e:
        relator.fechar()
        print(f"\nVEREDITO RECUSADO: {e}", file=sys.stderr)
        return 1
    except (ErroGeracao, ErroLLM, ex.ErroExecutor) as e:
        relator.fechar()
        # a pasta da sessao so existe se a geracao chegou a comecar
        onde = f"\n(sessao em {agente.sessao})" if agente.sessao.exists() else ""
        return erro(f"{e}{onde}")

    relator.fechar()
    selo = "OBJETIVO ATINGIDO" if r.objetivo_atingido else "OBJETIVO NAO ATINGIDO"
    print(f"\n{'=' * 66}")
    print(f"{rel_pasta}   {r.veredito.upper()}   ({selo})")
    print("=" * 66)
    print(f"  placar final   : {r.placar.texto()}")
    print(f"  iteracoes      : {r.iteracoes} de correcao, {r.chamadas} chamadas ao modelo")
    print(f"  tokens         : {r.tokens_entrada} de entrada, {r.tokens_saida} de saida")
    print(f"  tempo          : {r.segundos / 60:.1f} min")
    print(f"  sessao         : {r.sessao.relative_to(REPO_ROOT).as_posix()}")
    print(f"  relatorio JSON : {r.relatorio.relative_to(REPO_ROOT).as_posix()}")
    print(f"  validar de novo: spec-riscv-test --cpu {rel_pasta} --riscv-tests riscv-tests --out out")
    return 0 if r.objetivo_atingido else 1


def cmd_retomar(args: argparse.Namespace) -> int:
    """Alias enxuto para ``gerar --retomar``, sem permitir trocar a sessão."""
    args.retomar = args.sessao
    args.exemplo = None
    args.forcar = True
    args.descricao = None
    args.descricao_arquivo = None
    args.testes_componentes = False
    args.regressoes_componentes = False
    args.gates_componentes = False
    return cmd_gerar(args)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m rvgen",
        description="Gera CPUs RISC-V com um agente de IA local (Ollama) ou "
                     "externo (OpenRouter) e as valida com spec-riscv-test.",
    )
    sub = ap.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("preparar", help="confere e prepara Ollama, modelo e executor")
    p.add_argument("--verificar", action="store_true",
                   help="so confere; nao instala, nao baixa, nao inicia nada")
    p.add_argument("--sim", action="store_true",
                   help="responde sim a toda confirmacao (para scripts)")
    p.add_argument("--modelo", help="modelo do Ollama (padrao: perfil pela VRAM)")
    p.add_argument("--perfil", choices=["auto", *ol.PERFIS], default=None,
                   help="perfil de modelo local (padrao: auto)")
    p.add_argument("--executor", choices=["auto", "local", "docker"], default=None,
                    help="onde rodar o spec-riscv-test (padrao: auto)")
    p.add_argument("--sem-cor", action="store_true", help="saida sem cor ANSI")
    p.set_defaults(func=cmd_preparar)


    g = sub.add_parser("gerar", help="gera uma CPU, valida no spec-riscv-test e corrige")
    g.add_argument("pasta", help="nome do experimento (grava em experimentos/<nome>) "
                                 "ou uma pasta dentro do repositorio")
    g.add_argument("--provedor", choices=list(PROVEDORES), default=None,
                   help="ollama (local), vllm (local, API OpenAI), openrouter ou google (Gemini)")
    g.add_argument("--modelo", help="modelo (padrao: perfil pela VRAM, SPECHDL_LLM_MODEL "
                                    "ou RVGEN_MODELO)")
    g.add_argument("--perfil", choices=["auto", *ol.PERFIS], default=None,
                   help="perfil de modelo local")
    g.add_argument("--iteracoes", type=int, default=12,
                    help="maximo de correcoes antes do veredito (padrao: 12)")
    g.add_argument("--tentativas-revisao-semantica", type=int, default=3,
                   help="maximo de revisoes semanticas por componente (padrao: 3)")
    g.add_argument("--max-casos-teste", type=int, default=32,
                    help="maximo de casos Cocotb incrementais por componente (padrao: 32)")
    g.add_argument("--max-casos-internos", type=int, default=8,
                   help="maximo de diagnósticos Cocotb internos por componente (padrao: 8)")
    g.add_argument("--parallel-testes", type=int, default=1,
                   help="candidatos incrementais independentes por lote (padrao: 1)")
    g.add_argument("--testes-componentes", action="store_true",
                     help="gera e roda um testbench cocotb por VHDL antes do spec-riscv-test")
    g.add_argument("--testes-internos", action="store_true",
                    help="para blocos com dependencias, executa camada interna antes da publica")
    g.add_argument("--regressoes-componentes", action="store_true",
                    help="ao corrigir falha de componente, cria casos de regressao e similares "
                          "(exige --testes-componentes)")
    g.add_argument("--gates-componentes", action="store_true",
                   help="gera, compila e testa cada bloco antes do proximo "
                        "(exige --testes-componentes)")
    g.add_argument("--executor", choices=["auto", "local", "docker"], default=None,
                    help="onde rodar o spec-riscv-test (padrao: auto)")
    g.add_argument("--exemplo", metavar="DIR",
                   help="CPU de referencia cujo src/*.vhd entra no prompt "
                        "(ex.: cpus/rv32i_monociclo); fica registrado na sessao")
    g.add_argument("--forcar", action="store_true",
                    help="sobrescreve os arquivos gerados numa pasta que ja existe")
    g.add_argument("--retomar", metavar="SESSAO",
                   help="retoma sessao interrompida (ex.: 20261002-152036); reutiliza blocos aprovados")
    d = g.add_mutually_exclusive_group()
    d.add_argument("--descricao", metavar="TEXTO",
                   help="descricao da CPU em texto livre; orienta o modelo abaixo do "
                         "contrato e NAO e verificada pelo spec-riscv-test (FR-RV-52)")
    d.add_argument("--descricao-arquivo", metavar="ARQUIVO",
                   help="o mesmo, lido de um arquivo de texto (UTF-8)")
    g.set_defaults(func=cmd_gerar)

    r = sub.add_parser("retomar", help="retoma uma sessao interrompida com checkpoints de componentes")
    r.add_argument("pasta", help="pasta do experimento dentro do repositorio")
    r.add_argument("sessao", help="id da sessao, com ou sem o prefixo sessao-")
    r.add_argument("--provedor", choices=list(PROVEDORES), default=None)
    r.add_argument("--modelo", help="modelo a usar nas novas chamadas")
    r.add_argument("--perfil", choices=["auto", *ol.PERFIS], default=None)
    r.add_argument("--iteracoes", type=int, default=12,
                    help="maximo de correcoes restantes (padrao: 12)")
    r.add_argument("--tentativas-revisao-semantica", type=int, default=3,
                   help="maximo de revisoes semanticas por componente (padrao: 3)")
    r.add_argument("--testes-internos", action="store_true",
                   help="executa camada interna para blocos com dependencias")
    r.add_argument("--max-casos-teste", type=int, default=32,
                    help="maximo de casos Cocotb incrementais por componente (padrao: 32)")
    r.add_argument("--max-casos-internos", type=int, default=8,
                   help="maximo de diagnósticos Cocotb internos por componente (padrao: 8)")
    r.add_argument("--parallel-testes", type=int, default=1,
                   help="candidatos incrementais independentes por lote (padrao: 1)")
    r.add_argument("--executor", choices=["auto", "local", "docker"], default=None)
    r.set_defaults(func=cmd_retomar)

    c = sub.add_parser("comparar", help="experimentos lado a lado: veredito, custo, tokens")
    c.add_argument("pastas", nargs="*",
                   help="experimentos ou pastas de experimentos (padrao: experimentos/)")
    c.add_argument("--todas", action="store_true",
                   help="todas as sessoes de cada experimento, nao so a mais recente")
    c.add_argument("--markdown", metavar="ARQUIVO",
                   help="grava a mesma tabela em Markdown (ex.: experimentos/COMPARACAO.md)")
    c.add_argument("--sem-rede", action="store_true",
                   help="nao busca precos no OpenRouter; custo externo sai como ?")
    c.set_defaults(func=cmd_comparar)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
