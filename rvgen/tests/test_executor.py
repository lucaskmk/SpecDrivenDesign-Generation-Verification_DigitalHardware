#!/usr/bin/env python3
"""Testes do executor do validador -- sem GHDL e sem Docker.

REQ: FR-RV-49 (o veredito vem do --json do rvverify real), NFR-RV-07 (o
validador e chamado como subprocesso).

O que se confere e o comando montado e a leitura do relatorio. Rodar o
rvverify de verdade e papel da execucao ponta a ponta (TRV-9.8).
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from rvgen.executor import (Disponibilidade, ErroExecutor, Executor,
                            ExecutorDocker, ExecutorLocal, IMAGEM_PUBLICADA,
                            checar_docker, checar_local, escolher_executor,
                            ler_relatorio)


class TestComandos(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self._tmp.name).resolve()
        self.pasta = self.raiz / "entregas" / "gerada"
        self.sessao = self.pasta / ".rvgen"

    def tearDown(self):
        self._tmp.cleanup()

    def _args(self):
        return dict(json_saida=self.sessao / "spec-riscv-test" / "it1" / "report.json",
                    workdir=self.sessao / "sim" / "it1",
                    build_root=self.sessao / "build")

    def test_docker_e_recusado_para_o_validador_final(self):
        with self.assertRaisesRegex(ErroExecutor, "executado localmente"):
            ExecutorDocker("spechdl-toolchain", self.raiz).comando(self.pasta, **self._args())

    def test_docker_recusa_pasta_fora_do_repositorio(self):
        with self.assertRaisesRegex(ErroExecutor, "executado localmente"):
            ExecutorDocker("img", self.raiz).comando(self.raiz / "fora", **self._args())

    def test_local_chama_wrapper_oficial_e_selecao_csv(self):
        cmd, env = ExecutorLocal(self.raiz).comando(self.pasta, **self._args())
        self.assertEqual(cmd[1:3], ["--cpu", str(self.pasta)])
        self.assertIn("--riscv-tests", cmd)
        self.assertIn("--out", cmd)
        self.assertEqual(env, {})
        cmd, _ = ExecutorLocal(self.raiz).comando(self.pasta, casos=["rv32i/add"], **self._args())
        self.assertEqual(cmd[-2:], ["--tests", "add"])

    def test_componente_repassa_artefato_vcd_ao_runner(self):
        executor = ExecutorLocal(self.raiz)
        capturado = {}

        def rodar(cmd, json_saida, workdir, build_root, timeout):
            capturado["cmd"] = cmd
            return object()

        executor._rodar_comando = rodar  # type: ignore[method-assign]
        vcd = self.sessao / "vcd" / "lhu.vcd"
        executor.rodar_componente(
            self.pasta, componente="cpu", teste=self.sessao / "test_cpu.py",
            fontes=[], json_saida=self.sessao / "resultado.json",
            workdir=self.sessao / "sim", build_root=self.sessao / "build", vcd=vcd)
        self.assertEqual(capturado["cmd"][-2:], ["--vcd", str(vcd)])

    def test_rodar_le_o_json_e_apaga_o_relatorio_antigo(self):
        relatorio = {"design": "gerada", "veredito": "reprovado", "casos": []}

        class Falso(Executor):
            nome = "falso"

            def comando(self, pasta, *, json_saida, workdir, build_root,
                        casos=None, etapa="ambas"):
                script = (f"import json,sys; json.dump([{relatorio!r}], "
                          f"open(sys.argv[1],'w')); print('saida'); sys.exit(1)")
                return [sys.executable, "-c", script, str(json_saida)], {}

        args = self._args()
        args["json_saida"].parent.mkdir(parents=True)
        args["json_saida"].write_text("[{\"antigo\": true}]", encoding="utf-8")
        ex = Falso(self.raiz).rodar(self.pasta, **args)
        self.assertEqual(ex.codigo, 1)
        self.assertEqual(ex.relatorio, relatorio)
        self.assertIn("saida", ex.saida)
        self.assertTrue(args["workdir"].is_dir() and args["build_root"].is_dir())

    def test_relatorio_ausente_ou_invalido_vira_None(self):
        p = self.raiz / "r.json"
        self.assertIsNone(ler_relatorio(p))
        p.write_text("nao e json", encoding="utf-8")
        self.assertIsNone(ler_relatorio(p))
        p.write_text(json.dumps([{"veredito": "aprovado"}]), encoding="utf-8")
        self.assertEqual(ler_relatorio(p), {"veredito": "aprovado"})


def _run_falso(codigos: dict[str, int]):
    """`subprocess.run` falso: o codigo de saida depende do subcomando."""
    def run(args, **kw):
        return subprocess.CompletedProcess(args, codigos.get(args[1], 0), "", "")
    return run


class TestDisponibilidade(unittest.TestCase):

    def test_local_exige_ghdl_e_toolchain(self):
        d = checar_local(which=lambda n: None, tem_modulo=lambda n: False)
        self.assertFalse(d.pronto)
        self.assertIn("ghdl", d.detalhe)
        self.assertIn("compilador", d.detalhe)

    def test_docker_ausente_parado_sem_imagem_e_pronto(self):
        sem = checar_docker("img", which=lambda n: None)
        self.assertIn("Docker Desktop", sem.como_resolver)
        parado = checar_docker("img", which=lambda n: "docker",
                               run=_run_falso({"info": 1}))
        self.assertIn("daemon", parado.detalhe)
        sem_img = checar_docker("img", which=lambda n: "docker",
                                run=_run_falso({"image": 1}))
        self.assertIn(f"docker pull {IMAGEM_PUBLICADA}", sem_img.como_resolver)
        self.assertIn("docker build -t img docker/spechdl-toolchain", sem_img.como_resolver)
        pronto = checar_docker("img", which=lambda n: "docker", run=_run_falso({}))
        self.assertTrue(pronto.pronto)

    def test_auto_prefere_local_depois_docker_e_explica_quando_nao_ha_nenhum(self):
        sim = lambda: Disponibilidade(True, "ok")                   # noqa: E731
        nao = lambda: Disponibilidade(False, "falta X", "faca Y")   # noqa: E731
        self.assertIsInstance(escolher_executor("auto", local=sim, docker=sim), ExecutorLocal)
        with self.assertRaises(ErroExecutor):
            escolher_executor("auto", local=nao, docker=sim)
        with self.assertRaises(ErroExecutor) as ctx:
            escolher_executor("auto", local=nao, docker=nao)
        self.assertIn("local : falta X -> faca Y", str(ctx.exception))
        with self.assertRaisesRegex(ErroExecutor, "nao esta instalado na imagem Docker"):
            escolher_executor("docker", local=sim, docker=nao)


if __name__ == "__main__":
    unittest.main()
