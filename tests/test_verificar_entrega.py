"""A normalizacao de procedencia nao pode mascarar mudancas de metricas ou hashes."""
import unittest

from scripts.verificar_entrega import EXPANDIDOS, conferir_inventario, normalizar_fontes_avaliacao


class TestNormalizarProcedencia(unittest.TestCase):
    def test_ignora_ancestral_com_mesmo_nome_e_preserva_metrica(self):
        a = {"comparacao_central": {"exata": 77}, "fontes_sha256": {
            "C:\\work\\config\\case\\artefatos\\auditoria-v1\\manifesto_auditoria.json": "abc",
            "C:\\work\\artefatos\\case\\config\\politica_v1.json": "def"}}
        esperado = {"comparacao_central": {"exata": 77}, "fontes_sha256": {
            "artefatos/auditoria-v1/manifesto_auditoria.json": "abc", "config/politica_v1.json": "def"}}
        self.assertEqual(normalizar_fontes_avaliacao(a), esperado)
        self.assertIn("C:\\work\\artefatos\\case\\config\\politica_v1.json", a["fontes_sha256"])

    def test_diferenca_de_metrica_ou_hash_permanece_visivel(self):
        base = {"comparacao_central": {"exata": 77}, "fontes_sha256": {"/repo/config/politica_v1.json": "abc"}}
        metrica = dict(base, comparacao_central={"exata": 76})
        digest = dict(base, fontes_sha256={"/outra/config/politica_v1.json": "outro"})
        self.assertNotEqual(normalizar_fontes_avaliacao(base), normalizar_fontes_avaliacao(metrica))
        self.assertNotEqual(normalizar_fontes_avaliacao(base), normalizar_fontes_avaliacao(digest))

    def test_colisoes_e_fontes_desconhecidas_sao_recusadas(self):
        for fontes in (
            {"/a/config/x.json": "igual", "/b/config/x.json": "igual"},
            {"/a/arquivo_sem_prefixo.json": "abc"},
        ):
            with self.subTest(fontes=fontes), self.assertRaises(ValueError):
                normalizar_fontes_avaliacao({"fontes_sha256": fontes})

    def test_inventario_detecta_saida_nao_entregue_e_mudanca_no_contrato(self):
        arquivo = "artefatos/auditoria-v1/entradas_cegas.jsonl"
        conferir_inventario({arquivo}, {arquivo} | EXPANDIDOS)
        for versionados, gerados in (
            (set(), {arquivo} | EXPANDIDOS),
            ({arquivo}, set(EXPANDIDOS)),
            ({arquivo}, {arquivo, "artefatos/preparacao/extra.json"} | EXPANDIDOS),
        ):
            with self.subTest(versionados=versionados), self.assertRaises(ValueError):
                conferir_inventario(versionados, gerados)


if __name__ == "__main__":
    unittest.main()
