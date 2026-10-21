"""Contratos de isolamento e preservação do verificador M5; dados fictícios."""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


RAIZ = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("verificar_entrega_m5", RAIZ / "scripts/verificar_entrega.py")
m5 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m5)


class TestEntregaM5(unittest.TestCase):
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

    def fontes_ficticias(self):
        for nome in m5.FIXOS:
            self.escrever(nome)
        for pacote in m5.PACOTES:
            self.escrever(f"{pacote}/__init__.py", "")
        for diretorio, nomes in m5.PRODUTOS.items():
            for nome in nomes:
                self.escrever(f"artefatos/{diretorio}/{nome}")
        nomes = m5.listar_arquivos(self.raiz)
        return m5.inventario(self.raiz, nomes)

    @staticmethod
    def retorno_subprocesso(modulo, **isolamento):
        ambiente = dict.fromkeys(("no_site", "ignore_environment", "dont_write_bytecode",
                                  "site_packages_no_path", "rede_env_encoder_pesos_bloqueados"), True)
        ambiente.update(isolamento)
        resultado = ({"status": "ok", "operacao": "verificar", "contagens": {"questoes": 2}}
                     if modulo == "classificacao_topicos" else {
                         "comando": "verificar", "produtos_reconstruidos_identicos": 15,
                         "entregas_raiz_identicas": 2})
        return subprocess.CompletedProcess([], 0, m5.MARCADOR + json.dumps(ambiente)
                                           + "\n" + json.dumps(resultado) + "\n", "")

    def test_ambiente_elimina_chaves_proxies_e_pythonpath(self):
        resultado = m5.ambiente_limpo(self.base, {
            "GEMINI_API_KEY": "sentinela", "PYTHONPATH": "externo", "PYTHONHOME": "externo",
            "HTTP_PROXY": "externo", "PATH": "externo", "SystemRoot": "C:/Windows",
            "USERPROFILE": "perfil-original", "HF_HOME": "cache-original",
        })
        self.assertEqual(resultado, {"SystemRoot": "C:/Windows", **dict.fromkeys(
            ("TEMP", "TMP", "HOME", "USERPROFILE"), str(self.base))})

    def test_caminhos_absolutos_e_fuga_recusados(self):
        for nome in ("../a", "tmp/../a", "/tmp/a", "C:/a", "tmp\\a", "tmp/./a", ""):
            with self.subTest(nome=nome), self.assertRaises(ValueError):
                m5.caminho_local(self.raiz, nome, arquivo=False)

    def test_arquivo_obrigatorio_ausente_recusado(self):
        with self.assertRaisesRegex(ValueError, "ausente"):
            m5.caminho_local(self.raiz, "faltante.json")

    def test_link_em_arquivo_ou_ancestral_recusado(self):
        self.escrever("pasta/arquivo.json")
        for link in (self.raiz, self.raiz / "pasta", self.raiz / "pasta/arquivo.json"):
            with self.subTest(link=link), patch.object(m5, "_link", side_effect=lambda p: p == link):
                with self.assertRaisesRegex(ValueError, "[Ll]ink"):
                    m5.caminho_local(self.raiz, "pasta/arquivo.json")

    def test_reparse_point_windows_recusado(self):
        arquivo = self.escrever("arquivo.json")
        estatistica = type("Stat", (), {"st_file_attributes": 1024})()
        with patch.object(Path, "is_symlink", return_value=False), patch.object(
                Path, "exists", return_value=True), patch.object(Path, "lstat", return_value=estatistica):
            self.assertTrue(m5._link(arquivo))

    def test_copia_nao_inclui_ambientes_pesos_contexto_docs_ou_historico(self):
        registros = self.fontes_ficticias()
        for nome in (".env", ".venv/segredo.py", ".cache-modelos/modelo.onnx", "tmp/cache.json",
                     "docs/relatorio.md", "README.md", "config/modulo5/adicional.json",
                     "artefatos/checkpoints/anterior.json", "classificacao_topicos/__pycache__/x.pyc"):
            self.escrever(nome, "não copiar")
        (self.base / "historico.json").write_text("não copiar", encoding="utf-8")
        self.assertEqual(set(registros), set(m5.listar_arquivos(self.raiz)))
        destino = self.base / "copia"
        m5.materializar(self.raiz, destino, registros)
        self.assertEqual(registros, m5.inventario(destino, sorted(registros)))
        self.assertFalse((destino / ".env").exists())
        self.assertFalse((destino / ".cache-modelos").exists())

    def test_copia_recusa_destino_existente(self):
        with self.assertRaisesRegex(ValueError, "novo"):
            m5.materializar(self.raiz, self.raiz, {})

    def test_copia_detecta_fonte_modificada(self):
        self.escrever("arquivo.txt", "antes")
        registros = m5.inventario(self.raiz, ["arquivo.txt"])
        self.escrever("arquivo.txt", "depois")
        with self.assertRaisesRegex(ValueError, "mudou"):
            m5.materializar(self.raiz, self.base / "copia", registros)

    def test_copia_detecta_extra_e_bytes_divergentes(self):
        self.escrever("arquivo.txt", "antes")
        registros = m5.inventario(self.raiz, ["arquivo.txt"])
        self.escrever("extra.txt")
        with self.assertRaisesRegex(ValueError, "diverge"):
            m5.conferir_copia(self.raiz, registros)
        (self.raiz / "extra.txt").unlink()
        self.escrever("arquivo.txt", "depois")
        with self.assertRaisesRegex(ValueError, "diverge"):
            m5.conferir_copia(self.raiz, registros)

    def test_saida_restrita_e_evidencia_existente_preservada(self):
        for nome in ("publicacao.csv", "artefatos/preparacao/manifesto.json", "tmp/evidencia.txt",
                     "../evidencia.json", "artefatos/checkpoints/sub/a.json"):
            with self.subTest(nome=nome), self.assertRaises(ValueError):
                m5.destino_evidencia(self.raiz, nome)
        self.escrever("artefatos/checkpoints/prova.json", "preservar")
        with self.assertRaisesRegex(ValueError, "já existe"):
            m5.verificar(self.raiz, "artefatos/checkpoints/prova.json")
        self.assertEqual((self.raiz / "artefatos/checkpoints/prova.json").read_text(encoding="utf-8"), "preservar")
        self.assertEqual(m5.destino_evidencia(self.raiz, "tmp/nova/prova.json"), self.raiz / "tmp/nova/prova.json")

    def test_subprocesso_usa_flags_cwd_ambiente_e_sem_shell(self):
        for modulo in ("classificacao_topicos", "classificacao_decisao"):
            with self.subTest(modulo=modulo), patch.object(m5.subprocess, "run", return_value=self.retorno_subprocesso(modulo)) as chamada:
                resultado = m5.executar_comando(self.raiz, modulo, {"TEMP": "isolado"})
            args, kwargs = chamada.call_args
            self.assertEqual(args[0][1:7], ["-B", "-S", "-E", "-X", "utf8", "-c"])
            self.assertEqual(kwargs["cwd"], self.raiz)
            self.assertEqual(kwargs["env"], {"TEMP": "isolado"})
            self.assertNotIn("shell", kwargs)
            self.assertEqual(resultado["exit_code"], 0)

    def test_subprocesso_propagacao_falha_timeout_e_modulo_invalido(self):
        with patch.object(m5.subprocess, "run", return_value=subprocess.CompletedProcess([], 9, "", "falha fictícia")):
            with self.assertRaisesRegex(RuntimeError, "falhou.*9"):
                m5.executar_comando(self.raiz, "classificacao_topicos", {})
        with patch.object(m5.subprocess, "run", side_effect=subprocess.TimeoutExpired([], 1)):
            with self.assertRaisesRegex(RuntimeError, "excedeu"):
                m5.executar_comando(self.raiz, "classificacao_topicos", {}, timeout=1)
        with self.assertRaisesRegex(ValueError, "lista permitida"):
            m5.executar_comando(self.raiz, "outro", {})

    def test_subprocesso_exige_prova_de_isolamento(self):
        retornos = [subprocess.CompletedProcess([], 0, "{}", ""),
                    self.retorno_subprocesso("classificacao_topicos", no_site=False)]
        for retorno in retornos:
            with self.subTest(retorno=retorno), patch.object(m5.subprocess, "run", return_value=retorno):
                with self.assertRaises(ValueError):
                    m5.executar_comando(self.raiz, "classificacao_topicos", {})

    def test_subprocesso_m4_exige_todos_produtos(self):
        retorno = self.retorno_subprocesso("classificacao_decisao")
        retorno.stdout = retorno.stdout.replace('"produtos_reconstruidos_identicos": 15', '"produtos_reconstruidos_identicos": 14')
        with patch.object(m5.subprocess, "run", return_value=retorno), self.assertRaisesRegex(ValueError, "todos os produtos"):
            m5.executar_comando(self.raiz, "classificacao_decisao", {})

    def test_execucao_publica_evidencia_e_preserva_fontes(self):
        fontes = self.fontes_ficticias()
        with patch.object(m5, "executar_comando", return_value={"resultado": "fictício"}), contextlib.redirect_stdout(io.StringIO()):
            resultado = m5.verificar(self.raiz, "tmp/prova.json")
        prova = json.loads((self.raiz / "tmp/prova.json").read_text(encoding="utf-8"))
        self.assertEqual(resultado["status"], "aprovado")
        self.assertEqual(prova["fontes_sha256_e_bytes"], fontes)
        self.assertEqual(fontes, m5.inventario(self.raiz, sorted(fontes)))
        self.assertIn("não é clone Git", prova["materializacao"])
        self.assertEqual(len(prova["execucoes"]), 2)

    def test_falha_nao_publica_evidencia_de_sucesso(self):
        self.fontes_ficticias()
        with patch.object(m5, "executar_comando", side_effect=RuntimeError("falha fictícia")), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, "falha fictícia"):
                m5.verificar(self.raiz, "tmp/prova.json")
        self.assertFalse((self.raiz / "tmp/prova.json").exists())

    def test_mudanca_da_origem_durante_verificacao_detectada(self):
        self.fontes_ficticias()
        def modificar(*args, **kwargs):
            self.escrever("publicacao.csv", "alterada")
            return {}
        with patch.object(m5, "executar_comando", side_effect=modificar), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, "originais mudaram"):
                m5.verificar(self.raiz, "tmp/prova.json")
        self.assertFalse((self.raiz / "tmp/prova.json").exists())

    def test_bootstrap_real_m1_bloqueia_rede_encoder_env_e_pesos(self):
        self.escrever("classificacao_decisao/__init__.py", "")
        self.escrever("classificacao_decisao/__main__.py", (RAIZ / "classificacao_decisao/__main__.py").read_text(encoding="utf-8"))
        self.escrever("classificacao_topicos/__init__.py", "")
        self.escrever("classificacao_topicos/__main__.py", '''import json, os, socket
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
if bloqueados != 4 or "SENTINELA_API_KEY" in os.environ:
    raise RuntimeError("Isolamento insuficiente")
print(json.dumps({"status": "ok", "operacao": "verificar", "contagens": {"bloqueados": bloqueados}}))
''')
        ambiente = m5.ambiente_limpo(self.base, {**os.environ, "SENTINELA_API_KEY": "não herdar"})
        resultado = m5.executar_comando(self.raiz, "classificacao_topicos", ambiente)
        self.assertEqual(resultado["resumo"]["contagens"]["bloqueados"], 4)
        self.assertEqual(resultado["exit_code"], 0)

    def test_cli_sem_argumentos_gera_destinos_unicos_em_tmp(self):
        with patch.object(sys, "argv", ["verificar_entrega.py"]), patch.object(
                m5, "verificar", return_value={"status": "aprovado"}) as chamada, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(m5.main(), 0)
            self.assertEqual(m5.main(), 0)
        nomes = [c.args[1] for c in chamada.call_args_list]
        self.assertNotEqual(nomes[0], nomes[1])
        for nome in nomes:
            self.assertTrue(nome.startswith("tmp/reproducao-modulo5-"))
            self.assertTrue(nome.endswith(".json"))

    def test_cli_evidencia_explicita_preserva_destino_escolhido(self):
        nome = "artefatos/checkpoints/prova.json"
        with patch.object(sys, "argv", ["verificar_entrega.py", "--evidencia", nome]), patch.object(
                m5, "verificar", return_value={"status": "aprovado"}) as chamada, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(m5.main(), 0)
        self.assertEqual(chamada.call_args.args[1], nome)


if __name__ == "__main__":
    unittest.main()
