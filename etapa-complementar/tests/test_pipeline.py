"""Integração: fontes preservadas, execução offline e saídas verificáveis."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from classificacao_topicos.pipeline import (
    executar_preparacao, verificar_fontes, verificar_preparacao,
)


RAIZ = Path(__file__).resolve().parents[1]


class TestPipeline(unittest.TestCase):
    def setUp(self):
        temporarios = RAIZ / "tmp"
        temporarios.mkdir(exist_ok=True)
        self.temporaria = tempfile.TemporaryDirectory(prefix="teste-pipeline-", dir=temporarios)
        self.raiz = Path(self.temporaria.name).resolve()
        self.assertTrue(self.raiz.is_relative_to(temporarios.resolve()))
        referencia = json.loads((RAIZ / "config/fontes_oficiais.json").read_text("utf-8"))
        arquivos = list(referencia["arquivos"])
        arquivos.extend(p.relative_to(RAIZ).as_posix()
                        for pasta in ("config", "classificacao_topicos")
                        for p in (RAIZ / pasta).iterdir() if p.is_file())
        for nome in arquivos:
            destino = self.raiz / nome
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(RAIZ / nome, destino)
        self.saida = self.raiz / "artefatos/preparacao"

    def tearDown(self):
        # A limpeza recursiva fica restrita à pasta temporária criada pelo teste.
        if not self.raiz.is_relative_to((RAIZ / "tmp").resolve()):
            raise AssertionError("Pasta temporária fora da área de testes.")
        self.temporaria.cleanup()

    def test_reproducao_completa_offline_e_idempotente(self):
        with patch.object(socket.socket, "connect", side_effect=AssertionError("rede proibida")):
            contagens = executar_preparacao(self.raiz, self.saida)
            antes = {p.name: p.read_bytes() for p in self.saida.iterdir()}
            self.assertEqual(contagens, executar_preparacao(self.raiz, self.saida))
            self.assertEqual(contagens, verificar_preparacao(self.raiz, self.saida))
        self.assertEqual(contagens["questoes"], 659)
        self.assertEqual(contagens["rotulos"], 100)
        self.assertEqual(contagens["avaliacao_oficial"], 559)
        self.assertEqual(antes, {p.name: p.read_bytes() for p in self.saida.iterdir()})
        manifesto = json.loads(antes["manifesto.json"])
        self.assertFalse(manifesto["modelo_de_linguagem_utilizado"])
        self.assertEqual(len(manifesto["fontes_sha256"]), 7)
        self.assertNotIn(str(self.raiz).encode(), antes["manifesto.json"])
        self.assertFalse((self.raiz / "publicacao.csv").exists())
        linhas = antes["questoes_preparadas.jsonl"].decode("utf-8").splitlines()
        self.assertTrue(all("tema_central_id" not in json.loads(linha) for linha in linhas))

    def test_fonte_modificada_interrompe_sem_saida(self):
        fonte = self.raiz / "anexos/questoes.jsonl"
        fonte.write_bytes(fonte.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "Fonte diferente"):
            executar_preparacao(self.raiz, self.saida)
        self.assertFalse(self.saida.exists())

    def test_produto_corrompido_nao_e_sobrescrito(self):
        executar_preparacao(self.raiz, self.saida)
        produto = self.saida / "diagnostico.json"
        produto.write_bytes(b'{"corrompido": true}\n')
        with self.assertRaisesRegex(ValueError, "Produto divergente"):
            verificar_preparacao(self.raiz, self.saida)
        with self.assertRaisesRegex(ValueError, "Produto divergente"):
            executar_preparacao(self.raiz, self.saida)
        self.assertEqual(produto.read_bytes(), b'{"corrompido": true}\n')

    def test_destinos_protegidos_e_fora_da_raiz(self):
        for relativo in (".", "anexos", ".git/objetos", "../escape", "artefatos"):
            with self.subTest(saida=relativo):
                with self.assertRaises(ValueError):
                    executar_preparacao(self.raiz, Path(relativo))
        self.assertEqual(len(verificar_fontes(self.raiz)["arquivos"]), 7)

    def test_cli_erro_retorna_codigo_um(self):
        resultado = subprocess.run(
            [sys.executable, "-B", "-m", "classificacao_topicos", "preparar",
             "--saida", "anexos"],
            cwd=self.raiz, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30,
        )
        self.assertEqual(resultado.returncode, 1)
        self.assertIn("Erro:", resultado.stderr)
        self.assertFalse((self.raiz / "artefatos").exists())


if __name__ == "__main__":
    unittest.main()
