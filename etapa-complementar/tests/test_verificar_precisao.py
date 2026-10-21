"""Cópia e subprocesso M8 testados apenas com arquivos e resultados fictícios."""

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
SPEC = importlib.util.spec_from_file_location("verificador_precisao_teste", RAIZ / "scripts/verificar_precisao.py")
m8 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m8)


def resumo(produtos=3):
    return {"verificado": True, "produtos_experimento": produtos, "arquivos_entrega": 3,
            "questoes": 659, "receita": "sintetica", "encoder_executado": False,
            "chamadas_api": 0, "avaliacao559": {"total": 559, "precisao_observada": None}}


class VerificarPrecisaoTests(unittest.TestCase):
    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporario.cleanup)
        self.base = Path(self.temporario.name)
        self.raiz = self.base / "origem"
        self.raiz.mkdir()

    def escrever(self, nome, texto="fictício\n"):
        caminho = self.raiz / nome
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(texto, encoding="utf-8")
        return caminho

    def hash(self, nome):
        return hashlib.sha256((self.raiz / nome).read_bytes()).hexdigest()

    def fontes(self):
        self.escrever("insumo-m7.txt")
        self.escrever("artefatos/checkpoints/modulo7.json", json.dumps({"artefatos_sha256": {
            "insumo-m7.txt": self.hash("insumo-m7.txt")}}))
        for nome in ("classificacao_precisao/__init__.py", "classificacao_precisao/entrega.py",
                     "classificacao_precisao/preparar_large.py", "classificacao_precisao/.gitattributes",
                     "scripts/entregar_precisao.py", "scripts/verificar_precisao.py"):
            self.escrever(nome, "")
        self.escrever("config/modulo8/protocolo.json", "{}")
        self.escrever(m8.CACHE + "/vetores.json", "{}")
        self.escrever(m8.CACHE + "/manifesto.json", json.dumps({
            "fontes_sha256": {"classificacao_precisao/preparar_large.py": self.hash("classificacao_precisao/preparar_large.py")},
            "produtos_sha256": {"vetores.json": self.hash(m8.CACHE + "/vetores.json")},
        }))
        for nome in ("metricas.json", "politica.json"):
            self.escrever(m8.ARTEFATOS + "/" + nome, "{}")
        self.escrever(m8.ARTEFATOS + "/manifesto.json", json.dumps({
            "entradas_implementacao_sha256": {"insumo-m7.txt": self.hash("insumo-m7.txt")},
            "produtos_sha256": {n: self.hash(m8.ARTEFATOS + "/" + n)
                                 for n in ("metricas.json", "politica.json")},
        }))
        for nome in m8.ARQUIVOS_ENTREGA:
            self.escrever(m8.ENTREGA + "/" + nome)
        self.escrever(m8.ENTREGA + "/README.md", "Editorial fictício")
        self.escrever(m8.ENTREGA + "/relatorio.pdf", "PDF fictício; apenas bytes nesta verificação")
        self.escrever("docs/MODULO8_PRECISAO.md", "Fonte editorial fictícia")
        return patch.object(m8.m7, "listar_arquivos", return_value=["insumo-m7.txt"])

    def test_allowlist_soma_m7_cache_entrega_editoriais_e_exclui_segredos(self):
        with self.fontes():
            nomes = m8.listar_arquivos(self.raiz)
            for nome in (".env", ".env.example", ".venv/segredo.py", ".cache-modelos/modelo.onnx",
                         "tmp/antigo.json", "classificacao_precisao/__pycache__/a.pyc",
                         m8.CACHE + "/piloto_memoria/vetores.json"):
                self.escrever(nome, "não copiar")
            self.assertEqual(nomes, m8.listar_arquivos(self.raiz))
            for esperado in ("insumo-m7.txt", "artefatos/checkpoints/modulo7.json",
                             m8.CACHE + "/vetores.json", "scripts/entregar_precisao.py",
                             m8.ENTREGA + "/publicacao.csv", m8.ENTREGA + "/relatorio.pdf",
                             "docs/MODULO8_PRECISAO.md"):
                self.assertIn(esperado, nomes)

    def test_manifestos_nao_podem_introduzir_credenciais_ou_fuga(self):
        with self.fontes():
            original = json.loads((self.raiz / m8.ARTEFATOS / "manifesto.json").read_text(encoding="utf-8"))
            for invasor in ("../fora.json", ".env", ".cache-modelos/modelo.onnx"):
                alterado = {**original, "entradas_implementacao_sha256": {invasor: "a" * 64}}
                self.escrever(m8.ARTEFATOS + "/manifesto.json", json.dumps(alterado))
                with self.subTest(invasor=invasor), self.assertRaises(ValueError):
                    m8.listar_arquivos(self.raiz)
            alterado = {**original, "produtos_sha256": {"../fora.json": "a" * 64}}
            self.escrever(m8.ARTEFATOS + "/manifesto.json", json.dumps(alterado))
            with self.assertRaisesRegex(ValueError, "arquivos diretos"):
                m8.listar_arquivos(self.raiz)

    def test_produto_experimental_extra_ou_entrega_ausente_impede_copia(self):
        with self.fontes():
            extra = self.escrever(m8.ARTEFATOS + "/extra.json", "{}")
            with self.assertRaisesRegex(ValueError, "inesperados"):
                m8.listar_arquivos(self.raiz)
            extra.unlink()
            (self.raiz / m8.ENTREGA / "previsao.txt").unlink()
            with self.assertRaises((ValueError, FileNotFoundError)):
                m8.listar_arquivos(self.raiz)

    def test_interpretacao_exige_isolamento_verificacao_e_contagem_do_manifesto(self):
        isolamento = dict.fromkeys(m8.m6.CAMPOS_ISOLAMENTO, True)
        fim = resumo(7)
        linhas = [m8.MARCADOR + json.dumps(isolamento), "progresso", m8.CONCLUSAO + json.dumps(fim)]
        self.assertEqual(m8.interpretar_saida(linhas, 7), (isolamento, fim))
        for campo, valor in (("verificado", False), ("produtos_experimento", 12), ("arquivos_entrega", 2),
                             ("questoes", 658), ("encoder_executado", True), ("chamadas_api", 1),
                             ("receita", ""), ("avaliacao559", {"total": 559, "precisao_observada": 0.95})):
            alterado = [linhas[0], m8.CONCLUSAO + json.dumps({**fim, campo: valor})]
            with self.subTest(campo=campo), self.assertRaises(ValueError):
                m8.interpretar_saida(alterado, 7)
        for invalidas in ([], ["{}", linhas[-1]], [linhas[0], "{}"],
                          [m8.MARCADOR + json.dumps({**isolamento, "no_site": False}), linhas[-1]]):
            with self.assertRaises(ValueError):
                m8.interpretar_saida(invalidas, 7)
        with self.assertRaises(ValueError):
            m8.interpretar_saida(linhas, True)

    def test_subprocesso_sintetico_limpa_ambiente_bloqueia_rede_env_encoder_e_pesos(self):
        with self.fontes():
            self.escrever("classificacao_decisao/__init__.py", "")
            self.escrever("classificacao_decisao/__main__.py",
                          (RAIZ / "classificacao_decisao/__main__.py").read_text(encoding="utf-8"))
            script = self.escrever("scripts/entregar_precisao.py", '''import json, os, socket, sys
from pathlib import Path
if sys.argv[1:] != ['--verificar']:
    raise RuntimeError('Operação incorreta')
bloqueados = 0
for operacao in (
    lambda: socket.getaddrinfo('example.invalid', 443),
    lambda: __import__('numpy'),
    lambda: Path('.env').read_text(),
    lambda: Path('.cache-modelos/modelo.onnx').read_bytes(),
):
    try:
        operacao()
    except RuntimeError:
        bloqueados += 1
if bloqueados != 4 or 'SENTINELA_API_KEY' in os.environ or 'HOME' in os.environ:
    raise RuntimeError('Isolamento insuficiente')
print('ENTREGA_M8=' + json.dumps({'verificado': True, 'produtos_experimento': 3,
    'arquivos_entrega': 3, 'questoes': 659, 'receita': 'sintetica', 'encoder_executado': False,
    'chamadas_api': 0, 'avaliacao559': {'total': 559, 'precisao_observada': None}, 'bloqueados': bloqueados}))
''')
            ambiente = m8.m6.ambiente_limpo(self.base, {
                **os.environ, "SENTINELA_API_KEY": "não-herdar", "HOME": "não-redefinir",
                "PATH": "externo", "PYTHONPATH": "externo", "HTTPS_PROXY": "externo"})
            self.assertTrue({k.upper() for k in ambiente} <= {"SYSTEMROOT", "WINDIR", "TEMP", "TMP"})
            resultado = m8.executar_comando(self.raiz, ambiente)
            self.assertEqual(resultado["argumentos_python"], ["-E", "-B", "-S", "-X", "utf8", "-c"])
            self.assertEqual(resultado["resumo"]["bloqueados"], 4)
            self.assertEqual(resultado["resumo"]["produtos_experimento"], 3)
            self.assertTrue(all(resultado["isolamento"].values()))
            script.write_text("import time\ntime.sleep(10)\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "excedeu"):
                m8.executar_comando(self.raiz, ambiente, timeout=0.1)

    def test_timeout_invalido_recusado_sem_abrir_subprocesso(self):
        for tempo in (True, float("nan"), 0, -1, 1801):
            with patch.object(m8.subprocess, "Popen") as abrir:
                with self.assertRaises(ValueError):
                    m8.executar_comando(self.raiz, {}, timeout=tempo)
                abrir.assert_not_called()

    def test_reproducao_preserva_fontes_e_nao_sobrescreve_evidencia(self):
        with self.fontes():
            nomes = m8.listar_arquivos(self.raiz)
            inventario = m8.m5.inventario(self.raiz, nomes)
            with patch.object(m8, "executar_comando", return_value={"resumo": resumo()}), \
                    contextlib.redirect_stdout(io.StringIO()):
                resultado = m8.verificar(self.raiz)
            prova = self.raiz / m8.EVIDENCIA_PADRAO
            conteudo = prova.read_bytes()
            self.assertEqual(resultado["status"], "aprovado")
            self.assertEqual(resultado["produtos_m8_reconstruidos_identicos"], 3)
            self.assertEqual(resultado["arquivos_entrega_reconstruidos_identicos"], 3)
            self.assertEqual(json.loads(conteudo)["fontes_sha256_e_bytes"], inventario)
            self.assertEqual(m8.m5.inventario(self.raiz, nomes), inventario)
            self.assertEqual(list((self.raiz / "tmp").iterdir()), [])
            with self.assertRaisesRegex(ValueError, "já existe"):
                m8.verificar(self.raiz)
            self.assertEqual(prova.read_bytes(), conteudo)

    def test_mutacao_da_fonte_ou_copia_impede_evidencia_de_sucesso(self):
        for alvo in ("fonte", "copia"):
            with self.subTest(alvo=alvo), self.fontes():
                def modificar(copia, ambiente):
                    destino = self.raiz if alvo == "fonte" else copia
                    (destino / "insumo-m7.txt").write_text("alterado", encoding="utf-8")
                    return {"resumo": resumo()}
                with patch.object(m8, "executar_comando", side_effect=modificar), \
                        contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises(ValueError):
                        m8.verificar(self.raiz, "tmp/prova.json")
                self.assertFalse((self.raiz / "tmp/prova.json").exists())
                self.assertEqual(list((self.raiz / "tmp").iterdir()), [])

    def test_remocao_restrita_ao_tmp_resolvido_e_prefixo_correto(self):
        (self.raiz / "tmp").mkdir()
        externo = self.base / "reproducao-m8-fora"
        externo.mkdir()
        sentinela = externo / "preservar.txt"
        sentinela.write_text("preservar", encoding="utf-8")
        for alvo in (externo, self.raiz / "tmp", self.raiz / "tmp/reproducao-m7-outro"):
            with self.assertRaisesRegex(ValueError, "Remoção recusada"):
                m8.remover_temporario(self.raiz, alvo)
        self.assertEqual(sentinela.read_text(encoding="utf-8"), "preservar")
        for destino in ("../prova.json", "publicacao.csv", "config/modulo8/prova.json", "/tmp/prova.json"):
            with self.assertRaises(ValueError):
                m8.verificar(self.raiz, destino)

    def test_cli_usa_evidencia_padrao_e_aceita_destino_explicito(self):
        with patch.object(sys, "argv", ["verificar_precisao.py"]), \
                patch.object(m8, "verificar", return_value={"status": "aprovado"}) as chamada, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(m8.main(), 0)
            self.assertEqual(chamada.call_args.args[1], m8.EVIDENCIA_PADRAO)
        with patch.object(sys, "argv", ["verificar_precisao.py", "--evidencia", "tmp/outra.json"]), \
                patch.object(m8, "verificar", return_value={"status": "aprovado"}) as chamada, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(m8.main(), 0)
            self.assertEqual(chamada.call_args.args[1], "tmp/outra.json")


if __name__ == "__main__":
    unittest.main()
