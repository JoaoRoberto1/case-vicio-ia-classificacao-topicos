"""Contrato da árvore real e casos que poderiam corromper a navegação."""

import csv
import tempfile
import unittest
from pathlib import Path

from classificacao_topicos.taxonomia import (
    COLUNAS_TAXONOMIA,
    carregar_taxonomia,
    exportar_arvore,
)


RAIZ_REPOSITORIO = Path(__file__).resolve().parents[1]


def registro(tema_id="1", parent_id="", nivel="0", titulo="Penal", **alteracoes):
    resultado = {
        "tema_id": tema_id, "parent_id": parent_id, "disciplina": "Penal",
        "nivel": nivel, "titulo": titulo, "caminho": titulo,
        "descricao": "Descrição do tema.", "status": "active",
    }
    resultado.update(alteracoes)
    return resultado


class TaxonomiaTest(unittest.TestCase):
    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporario.cleanup)
        self.caminho = Path(self.temporario.name) / "temas.csv"

    def carregar(self, registros, colunas=COLUNAS_TAXONOMIA):
        with self.caminho.open("w", encoding="utf-8-sig", newline="") as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=colunas, extrasaction="ignore")
            escritor.writeheader()
            escritor.writerows(registros)
        return carregar_taxonomia(self.caminho)

    def test_contagens_e_ramos_do_arquivo_real(self):
        arvore = carregar_taxonomia(RAIZ_REPOSITORIO / "temas.csv")
        diagnostico = arvore["diagnostico"]
        self.assertEqual(diagnostico["total"], 377)
        self.assertEqual(diagnostico["niveis"], {"0": 4, "1": 111, "2": 262})
        self.assertEqual(diagnostico["status"], {"active": 375, "inactive": 2})
        self.assertEqual(diagnostico["total_disciplinas"], 4)
        self.assertEqual(diagnostico["inativos_ids"], ["5078", "5234"])
        self.assertEqual(
            {chave: valor["total"] for chave, valor in diagnostico["descricoes"].items()},
            {"vazias": 20, "metadados": 337, "outras": 20},
        )
        self.assertEqual(len(diagnostico["titulos_repetidos"]), 8)
        self.assertTrue(all(diagnostico["validacao_estrutural"].values()))
        for tema_id in ("5078", "5234"):
            self.assertFalse(arvore["por_id"][tema_id]["elegivel"])
        lei_a, lei_b = (arvore["por_id"][tema_id] for tema_id in ("4704", "6724"))
        self.assertEqual(lei_a["titulo"], lei_b["titulo"])
        self.assertNotEqual(lei_a["ancestrais_ids"], lei_b["ancestrais_ids"])
        self.assertNotEqual(lei_a["caminho_calculado"], lei_b["caminho_calculado"])

    def test_preserva_campos_originais_e_ordem_mesmo_com_filho_antes_do_pai(self):
        originais = [
            registro("3", "2", "2", "Subtema", caminho="Penal > Tema > Subtema"),
            registro("2", "1", "1", "Tema", caminho="Penal > Tema"),
            registro(),
        ]
        arvore = self.carregar(originais)
        for original, enriquecido in zip(originais, arvore["registros"]):
            self.assertEqual({campo: enriquecido[campo] for campo in COLUNAS_TAXONOMIA}, original)
        self.assertEqual(arvore["por_id"]["3"]["ancestrais_ids"], ["1", "2"])
        self.assertEqual(arvore["por_id"]["1"]["filhos_ids"], ["2"])
        self.assertEqual(arvore["por_id"]["3"]["filhos_ids"], [])
        self.assertEqual(arvore["diagnostico"]["alertas_caminho"], [])
        texto = exportar_arvore(arvore)
        self.assertLess(texto.index("[1]"), texto.index("[2]"))
        self.assertIn("    - [3] Subtema (active)", texto)

    def test_caminho_divergente_e_apenas_sinalizado(self):
        arvore = self.carregar([
            registro(),
            registro("2", "1", "1", "Tema", caminho="Caminho antigo"),
        ])
        tema = arvore["por_id"]["2"]
        self.assertEqual(tema["caminho"], "Caminho antigo")
        self.assertEqual(tema["caminho_calculado"], "Penal > Tema")
        self.assertIn("caminho_divergente", tema["avisos"])
        self.assertEqual(arvore["diagnostico"]["alertas_caminho"][0]["tema_id"], "2")

    def test_titulos_repetidos_nao_sao_fundidos(self):
        arvore = self.carregar([
            registro(),
            registro("2", "1", "1", "Ação Penal"),
            registro("3", "1", "1", " AÇÃO PENAL "),
        ])
        self.assertEqual(len(arvore["por_id"]), 3)
        grupo = arvore["diagnostico"]["titulos_repetidos"][0]
        self.assertEqual(grupo["titulo_normalizado"], "ação penal")
        self.assertEqual(grupo["ids"], ["2", "3"])

    def test_status_ativo_nao_e_alterado_por_ancestral_inativo(self):
        arvore = self.carregar([
            registro(status="inactive"), registro("2", "1", "1", "Tema"),
        ])
        self.assertTrue(arvore["por_id"]["2"]["elegivel"])
        self.assertIn("ancestral_inativo", arvore["por_id"]["2"]["avisos"])
        self.assertEqual(arvore["diagnostico"]["ativos_com_ancestral_inativo_ids"], ["2"])
        self.assertIn("[1] Penal (inactive)", exportar_arvore(arvore))

    def test_pai_inexistente(self):
        with self.assertRaisesRegex(ValueError, "parent_id.*inexistente"):
            self.carregar([registro("2", "404", "1", "Tema")])

    def test_ciclo_e_autorreferencia(self):
        for registros in ([registro(parent_id="1")], [
            registro("1", "2", "1"), registro("2", "1", "2"),
        ]):
            with self.subTest(registros=registros), self.assertRaisesRegex(ValueError, "Ciclo"):
                self.carregar(registros)

    def test_nivel_precisa_corresponder_a_profundidade(self):
        for registros in ([registro(nivel="1")], [
            registro(), registro("2", "1", "0", "Tema"),
        ], [registro(), registro("2", "1", "2", "Tema")]):
            with self.subTest(registros=registros), self.assertRaisesRegex(ValueError, "profundidade"):
                self.carregar(registros)

    def test_disciplina_do_descendente_precisa_corresponder_a_raiz(self):
        with self.assertRaisesRegex(ValueError, "disciplina.*raiz"):
            self.carregar([
                registro(), registro("2", "1", "1", "Tema", disciplina="Processo Penal"),
            ])

    def test_id_duplicado_vazio_ou_com_espacos(self):
        casos = [([registro(), registro()], "duplicado"),
                 ([registro(tema_id="")], "vazio"),
                 ([registro(tema_id=" 1")], "espaços")]
        for registros, mensagem in casos:
            with self.subTest(mensagem=mensagem), self.assertRaisesRegex(ValueError, mensagem):
                self.carregar(registros)

    def test_nivel_status_e_campos_obrigatorios(self):
        for campo, valor in (("nivel", "3"), ("nivel", "1.0"), ("status", "ativo"),
                             ("titulo", " "), ("disciplina", "")):
            with self.subTest(campo=campo, valor=valor), self.assertRaises(ValueError):
                self.carregar([registro(**{campo: valor})])

    def test_esquema_e_quantidade_de_campos(self):
        with self.assertRaisesRegex(ValueError, "colunas ausentes"):
            self.carregar([registro()], COLUNAS_TAXONOMIA[:-1])
        cabecalho = ",".join(COLUNAS_TAXONOMIA)
        for linha in ("1,,Penal,0,Penal,Penal,Texto,active,EXTRA", "1,,Penal,0"):
            self.caminho.write_text(cabecalho + "\n" + linha + "\n", encoding="utf-8")
            with self.subTest(linha=linha), self.assertRaisesRegex(ValueError, "quantidade de campos"):
                carregar_taxonomia(self.caminho)

    def test_cabecalho_duplicado_csv_malformado_e_arquivo_vazio(self):
        casos = [
            ("tema_id,tema_id\n", "colunas duplicadas"),
            ('"cabeçalho sem fechamento', "Cabeçalho CSV.*inválido"),
            ("", "sem cabeçalho"),
            (",".join(COLUNAS_TAXONOMIA) + "\n", "sem registros"),
            (",".join(COLUNAS_TAXONOMIA) + '\n1,,Penal,0,"texto sem fechamento', "CSV.*inválido"),
        ]
        for conteudo, mensagem in casos:
            self.caminho.write_text(conteudo, encoding="utf-8")
            with self.subTest(mensagem=mensagem), self.assertRaisesRegex(ValueError, mensagem):
                carregar_taxonomia(self.caminho)


if __name__ == "__main__":
    unittest.main()
