import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from classificacao_topicos.preparacao import carregar_questoes, executar_preparacao, preparar_questao, sha256


RAIZ = Path(__file__).resolve().parents[1]


class PreparacaoTests(unittest.TestCase):
    def test_preparacao_real_preserva_fontes_e_reproduz_produtos(self):
        fontes = [RAIZ / nome for nome in ("questoes.jsonl", "temas.csv", "LEIA-ME.md", "entrega_modelo.csv")]
        hashes = {p.name: sha256(p) for p in fontes}
        with tempfile.TemporaryDirectory() as pasta:
            saida = Path(pasta) / "preparados"
            diagnostico = executar_preparacao(RAIZ, saida)
            self.assertEqual(diagnostico["questoes"]["total"], 359)
            self.assertEqual(diagnostico["taxonomia"]["total"], 377)
            primeira = {p.name: p.read_bytes() for p in saida.iterdir()}
            executar_preparacao(RAIZ, saida)
            self.assertEqual(primeira, {p.name: p.read_bytes() for p in saida.iterdir()})
            preparados = [json.loads(linha) for linha in (saida / "questoes_preparadas.jsonl").read_text(encoding="utf-8").splitlines()]
            originais = carregar_questoes(RAIZ / "questoes.jsonl")
            self.assertEqual([q["id"] for q in preparados], [q["id"] for q in originais])
            for original, preparado in zip(originais, preparados):
                self.assertEqual(list(original["alternativas"]), list(preparado["alternativas"]))
                self.assertEqual(original["disciplina_origem"], preparado["disciplina_origem"])
                self.assertEqual(original["assunto_origem"], preparado["assunto_origem"])
                self.assertNotIn("decisao", preparado)
            manifesto = json.loads((saida / "manifesto.json").read_text(encoding="utf-8"))
            for nome, digest in manifesto["produtos_sha256"].items():
                self.assertEqual(digest, sha256(saida / nome))
        self.assertEqual(hashes, {p.name: sha256(p) for p in fontes})

    def test_questao_generica_mantem_alternativas_e_comando(self):
        dados = carregar_questoes(RAIZ / "questoes.jsonl")
        questao = preparar_questao(next(q for q in dados if q["id"] == "Q0239"), 239)
        self.assertIn("ALTERNATIVAS", questao["texto_completo"])
        for alternativa in questao["alternativas"].values():
            self.assertIn(alternativa, questao["texto_completo"])
        comando = preparar_questao(next(q for q in dados if q["id"] == "Q0107"), 107)
        self.assertTrue(comando["comando"])
        self.assertIn(comando["comando"], comando["texto_completo"])

    def test_id_duplicado_e_json_invalido_falham(self):
        original = carregar_questoes(RAIZ / "questoes.jsonl")[0]
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "questoes.jsonl"
            arquivo.write_text((json.dumps(original) + "\n") * 2, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicado"):
                carregar_questoes(arquivo)
            arquivo.write_text("{malformado\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "JSON inválido"):
                carregar_questoes(arquivo)

    def test_saida_na_raiz_e_rejeitada(self):
        with self.assertRaisesRegex(ValueError, "pasta distinta"):
            executar_preparacao(RAIZ, RAIZ)

    def test_destinos_protegidos_sao_rejeitados(self):
        for pasta in (".git", "contexto_local", "docs"):
            with self.subTest(pasta=pasta), self.assertRaisesRegex(ValueError, "protegida"):
                executar_preparacao(RAIZ, RAIZ / pasta / "preparacao")

    def test_separador_unicode_na_string_nao_divide_registro(self):
        registro = carregar_questoes(RAIZ / "questoes.jsonl")[0]
        registro["enunciado_html"] = "Primeira parte\u2028Segunda parte"
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "questoes.jsonl"
            arquivo.write_text(json.dumps(registro, ensure_ascii=False) + "\n", encoding="utf-8")
            self.assertEqual(carregar_questoes(arquivo), [registro])

    def test_chave_json_duplicada_e_rejeitada(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "questoes.jsonl"
            arquivo.write_text('{"id":"Q0001","id":"Q0002"}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Chave JSON duplicada"):
                carregar_questoes(arquivo)

    def test_gravacao_interrompida_nao_deixa_manifesto_de_sucesso(self):
        with tempfile.TemporaryDirectory() as pasta:
            saida = Path(pasta) / "preparados"
            executar_preparacao(RAIZ, saida)
            substituir = os.replace
            contador = 0

            def interromper(origem, destino):
                nonlocal contador
                contador += 1
                if contador == 2:
                    raise OSError("Interrupção simulada")
                return substituir(origem, destino)

            with patch("classificacao_topicos.preparacao.os.replace", side_effect=interromper):
                with self.assertRaisesRegex(OSError, "Interrupção simulada"):
                    executar_preparacao(RAIZ, saida)
            self.assertFalse((saida / "manifesto.json").exists())
            executar_preparacao(RAIZ, saida)
            self.assertTrue((saida / "manifesto.json").is_file())


if __name__ == "__main__":
    unittest.main()
