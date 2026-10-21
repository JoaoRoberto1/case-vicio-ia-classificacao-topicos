"""Reprodução M6: cópia, isolamento e preservação usando arquivos fictícios."""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


RAIZ = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("verificador_refinamento_teste", RAIZ / "scripts/verificar_refinamento.py")
m6 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m6)


class VerificadorRefinamentoTests(unittest.TestCase):
    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporario.cleanup)
        self.base = Path(self.temporario.name)
        self.raiz = self.base / "origem"
        self.raiz.mkdir()

    def escrever(self, nome, texto="fictício\n"):
        arquivo = self.raiz / nome
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text(texto, encoding="utf-8")
        return arquivo

    def fontes(self):
        self.escrever("insumo-m5.txt")
        self.escrever("relatorio.md")
        self.escrever("scripts/verificar_refinamento.py")
        self.escrever("classificacao_refinamento/__init__.py", "")
        self.escrever("classificacao_refinamento/__main__.py", "")
        self.escrever("config/modulo6/protocolo.json", "{}")
        self.escrever("config/modulo6/fontes.json", json.dumps({"sha256": {
            "relatorio.md": hashlib.sha256((self.raiz / "relatorio.md").read_bytes()).hexdigest()}}))
        self.escrever("artefatos/refinamento-v1/manifesto.json", "{}")
        self.escrever("artefatos/refinamento-v1/metricas.json", "{}")
        return patch.object(m6.m5, "listar_arquivos", return_value=["insumo-m5.txt"])

    def test_allowlist_uniao_exclui_segredos_e_recusa_manifesto_com_fuga(self):
        with self.fontes():
            nomes = m6.listar_arquivos(self.raiz)
            for nome in (".env", ".env.example", ".venv/segredo.py", ".cache-modelos/encoder.onnx",
                         "tmp/antigo.json", "classificacao_refinamento/__pycache__/a.pyc"):
                self.escrever(nome, "não copiar")
            self.assertEqual(nomes, m6.listar_arquivos(self.raiz))
            self.assertIn("insumo-m5.txt", nomes)
            self.assertIn("relatorio.md", nomes)
            self.assertIn("scripts/verificar_refinamento.py", nomes)
            for invasor in ("../fora.json", ".env", ".cache-modelos/encoder.onnx"):
                self.escrever("config/modulo6/fontes.json", json.dumps({"sha256": {invasor: "a" * 64}}))
                with self.subTest(invasor=invasor), self.assertRaises(ValueError):
                    m6.listar_arquivos(self.raiz)

    def test_subprocesso_real_sintetico_bloqueia_operacoes_e_limpa_ambiente(self):
        self.escrever("classificacao_decisao/__init__.py", "")
        self.escrever("classificacao_decisao/__main__.py",
                      (RAIZ / "classificacao_decisao/__main__.py").read_text(encoding="utf-8"))
        self.escrever("classificacao_refinamento/__init__.py", "")
        modulo = self.escrever("classificacao_refinamento/__main__.py", '''import json, os, socket
from pathlib import Path
bloqueados = 0
for operacao in (
    lambda: socket.getaddrinfo("example.invalid", 443),
    lambda: __import__("numpy"),
    lambda: Path(".env").read_text(),
    lambda: Path(".cache-modelos/modelo.onnx").read_bytes(),
):
    try:
        operacao()
    except RuntimeError:
        bloqueados += 1
if bloqueados != 4 or "SENTINELA_API_KEY" in os.environ or "HOME" in os.environ:
    raise RuntimeError("Isolamento insuficiente")
print(json.dumps({"comando": "verificar", "sugestoes_experimentais": 559,
                  "receita_selecionada": "sintetica", "bloqueados": bloqueados}))
''')
        ambiente = m6.ambiente_limpo(self.base, {
            **os.environ, "SENTINELA_API_KEY": "não-herdar", "HOME": "não-redefinir",
            "PATH": "externo", "PYTHONPATH": "externo", "HTTPS_PROXY": "externo"})
        self.assertTrue({k.upper() for k in ambiente} <= {"SYSTEMROOT", "WINDIR", "TEMP", "TMP"})
        resultado = m6.executar_comando(self.raiz, ambiente)
        self.assertEqual(resultado["argumentos_python"], ["-B", "-S", "-E", "-X", "utf8", "-c"])
        self.assertEqual(resultado["resumo"]["bloqueados"], 4)
        self.assertTrue(all(resultado["isolamento"].values()))
        modulo.write_text("import time\ntime.sleep(10)\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "excedeu"):
            m6.executar_comando(self.raiz, ambiente, timeout=0.1)

    def test_isolamento_e_resumo_incompletos_nao_aprovam(self):
        isolamento = dict.fromkeys(m6.CAMPOS_ISOLAMENTO, True)
        resumo = {"comando": "verificar", "sugestoes_experimentais": 559, "receita_selecionada": "sintetica"}
        self.assertEqual(m6.interpretar_saida([m6.MARCADOR + json.dumps(isolamento), json.dumps(resumo)]),
                         (isolamento, resumo))
        casos = [[], ["{}", json.dumps(resumo)],
                 [m6.MARCADOR + json.dumps({**isolamento, "no_site": False}), json.dumps(resumo)],
                 [m6.MARCADOR + json.dumps(isolamento), json.dumps({**resumo, "comando": "executar"})],
                 [m6.MARCADOR + json.dumps(isolamento), json.dumps({**resumo, "sugestoes_experimentais": 558})]]
        for linhas in casos:
            with self.subTest(linhas=linhas), self.assertRaises(ValueError):
                m6.interpretar_saida(linhas)

    def test_reproducao_preserva_fontes_e_evidencia_e_cli_gera_nomes_unicos(self):
        with self.fontes():
            nomes = m6.listar_arquivos(self.raiz)
            inventario = m6.m5.inventario(self.raiz, nomes)
            with patch.object(m6, "executar_comando", return_value={"resultado": "sintético"}), contextlib.redirect_stdout(io.StringIO()):
                resultado = m6.verificar(self.raiz, "artefatos/checkpoints/prova.json")
            prova = self.raiz / "artefatos/checkpoints/prova.json"
            conteudo = prova.read_bytes()
            self.assertEqual(resultado["status"], "aprovado")
            self.assertEqual(resultado["produtos_m6_reconstruidos_identicos"], 2)
            self.assertEqual(json.loads(conteudo)["fontes_sha256_e_bytes"], inventario)
            self.assertEqual(inventario, m6.m5.inventario(self.raiz, nomes))
            self.assertEqual(list((self.raiz / "tmp").iterdir()), [])
            with self.assertRaisesRegex(ValueError, "já existe"):
                m6.verificar(self.raiz, "artefatos/checkpoints/prova.json")
            self.assertEqual(prova.read_bytes(), conteudo)
        with patch.object(sys, "argv", ["verificar_refinamento.py"]), patch.object(
                m6, "verificar", return_value={"status": "aprovado"}) as chamada, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(m6.main(), 0)
            self.assertEqual(m6.main(), 0)
        destinos = [c.args[1] for c in chamada.call_args_list]
        self.assertNotEqual(destinos[0], destinos[1])
        self.assertTrue(all(n.startswith("tmp/reproducao-modulo6-") and n.endswith(".json") for n in destinos))

    def test_alteracao_da_fonte_ou_copia_impede_evidencia_de_sucesso(self):
        for alvo in ("fonte", "copia"):
            with self.subTest(alvo=alvo), self.fontes():
                def modificar(copia, ambiente):
                    destino = self.raiz if alvo == "fonte" else copia
                    (destino / "insumo-m5.txt").write_text("alterado", encoding="utf-8")
                    return {}
                with patch.object(m6, "executar_comando", side_effect=modificar), contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises(ValueError):
                        m6.verificar(self.raiz, "tmp/prova.json")
                self.assertFalse((self.raiz / "tmp/prova.json").exists())
                self.assertEqual(list((self.raiz / "tmp").iterdir()), [])

    def test_remocao_so_no_tmp_resolvido_e_destinos_fora_sao_recusados(self):
        (self.raiz / "tmp").mkdir()
        externo = self.base / "reproducao-m6-fora"
        externo.mkdir()
        sentinela = externo / "preservar.txt"
        sentinela.write_text("preservar", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Remoção recusada"):
            m6.remover_temporario(self.raiz, externo)
        self.assertEqual(sentinela.read_text(encoding="utf-8"), "preservar")
        with self.assertRaisesRegex(ValueError, "Remoção recusada"):
            m6.remover_temporario(self.raiz, self.raiz / "tmp")
        for destino in ("../prova.json", "publicacao.csv", "config/modulo6/prova.json", "/tmp/prova.json"):
            with self.subTest(destino=destino), self.assertRaises(ValueError):
                m6.verificar(self.raiz, destino)


if __name__ == "__main__":
    unittest.main()
