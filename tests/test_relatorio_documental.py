"""Protege denominadores, custo e integridade da previsao; sem dependencias PDF."""
import unittest

from scripts.gerar_relatorio import RAIZ, cenarios, custo_tokens, documentos, reunir, substituir_modelo


class TestCalculosDocumentais(unittest.TestCase):
    def setUp(self):
        self.config = {"erros_cenario_minimo": 0, "erros_cenario_central": 4,
            "erros_cenario_maximo": 8, "natureza": "subjetiva"}

    def test_previsao_nao_confunde_v1_v2_nem_meta(self):
        p = cenarios(359, 77, self.config)
        self.assertAlmostEqual(p["precisao_prevista"], 73 / 77)
        self.assertLess(p["precisao_prevista"], .95)
        self.assertEqual(p["precisao_intervalo"], [69 / 77, 1])
        self.assertEqual(p["cobertura_intervalo"], [77 / 359, 77 / 359])

    def test_cenarios_invalidos_nao_produzem_previsao(self):
        for valor in (-1, 3, 78, True, 8.0):
            with self.subTest(valor=valor), self.assertRaises(ValueError):
                cenarios(359, 77, dict(self.config, erros_cenario_maximo=valor))
        with self.assertRaises(ValueError):
            cenarios(359, 0, self.config)

    def test_custo_inclui_raciocinio_cache_nao_duplica_entrada(self):
        precos = {"entrada": .30, "entrada_cache": .03, "saida_incluindo_raciocinio": 2.5}
        t = {"promptTokenCount": 1_000_000, "cachedContentTokenCount": 800_000,
            "candidatesTokenCount": 100_000, "thoughtsTokenCount": 200_000}
        custos = custo_tokens(t, precos)
        self.assertAlmostEqual(custos["sem_desconto_cache_usd"], 1.05)
        self.assertAlmostEqual(custos["com_cache_informado_usd"], .834)
        with self.assertRaises(ValueError):
            custo_tokens(dict(t, cachedContentTokenCount=1_000_001), precos)

    def test_modelo_nao_silencia_campo_desconhecido(self):
        with self.assertRaises(ValueError):
            substituir_modelo("Precisao {{campo_inexistente}}", {})


class TestIntegracaoDocumental(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.e = reunir()

    def test_consumo_preserva_falhas_e_nao_duplica_piloto_revalidacao(self):
        etapas = list(self.e["consumo_por_etapa"].values())
        self.assertEqual(sum(x["tentativas"] for x in etapas), 474)
        self.assertEqual(sum(x["tentativas_sem_usage_metadata"] for x in etapas), 40)
        self.assertEqual(sum(x["tokens_observados"]["totalTokenCount"] for x in etapas), 13_079_922)
        lote = self.e["consumo_por_etapa"]["lote_v2_inclui_piloto_v2"]
        self.assertEqual(lote["questoes_com_recibo"], 359)
        self.assertEqual(lote["tentativas"], 404)

    def test_saida_tem_contrato_e_memo_na_quinta_pagina(self):
        produtos = documentos(self.e)
        primeiras = produtos["previsao.txt"].decode().splitlines()[:4]
        self.assertEqual(primeiras, ["precisao_prevista: 0.948052", "precisao_intervalo: 0.896104-1.000000",
            "cobertura_prevista: 0.214485", "cobertura_intervalo: 0.214485-0.214485"])
        paginas = produtos["relatorio.md"].decode().split("<!-- pagina -->")
        self.assertEqual(len(paginas), 5)
        self.assertIn("# Memo ao professor", paginas[-1])
        self.assertNotIn("{{", produtos["relatorio.md"].decode())
        self.assertEqual(self.e["decisoes"], {"publicar": 77, "revisar": 278, "fora": 4})

    def test_csv_alterado_recusado_antes_de_ler_recibos(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        with TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            (raiz / "config").mkdir()
            (raiz / "config/previsao_v2.json").write_bytes((RAIZ / "config/previsao_v2.json").read_bytes())
            (raiz / "publicacao.csv").write_bytes(b"id,decisao\nQ0001,publicar\n")
            with self.assertRaisesRegex(ValueError, "CSV diverge"):
                reunir(raiz)

    def test_recibo_faltante_ou_excedente_nao_subestima_custo(self):
        from pathlib import Path
        from unittest.mock import patch
        glob_original = Path.glob
        for alteracao in ("falta", "sobra"):
            def glob_alterado(pasta, padrao):
                arquivos = list(glob_original(pasta, padrao))
                if pasta.name == "lote-v2-35-flash-lite":
                    if alteracao == "falta":
                        arquivos = [p for p in arquivos if p.stem != "Q0001"]
                    else:
                        arquivos.append(pasta / "Q9999.json")
                return iter(arquivos)
            with self.subTest(alteracao=alteracao), patch.object(Path, "glob", glob_alterado):
                with self.assertRaisesRegex(ValueError, "incompleto ou excedente"):
                    reunir()


if __name__ == "__main__":
    unittest.main()
