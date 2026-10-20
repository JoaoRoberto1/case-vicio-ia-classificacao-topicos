"""Contratos estruturais dos anexos; não avalia classificação temática."""

from __future__ import annotations

import copy
import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from classificacao_topicos.dados import (
    COLUNAS_FOLHA_VERDADE,
    carregar_folha_verdade,
    carregar_questoes,
    preparar_dados,
    preparar_questao,
)
from classificacao_topicos.taxonomia import COLUNAS_TAXONOMIA, carregar_taxonomia
from classificacao_topicos.texto import analisar_texto, normalizar_texto


RAIZ = Path(__file__).resolve().parents[1]


def questao(identificador="Q0001"):
    return {
        "id": identificador,
        "enunciado_html": "<p>Texto com ação &amp; reação.</p>",
        "comando": "Escolha a alternativa.",
        "alternativas": {"A": "Primeira.", "B": "Segunda."},
        "disciplina_origem": "Metadado sem autoridade",
        "assunto_origem": "Assunto importado",
    }


def temas():
    return [
        {"tema_id": "R", "parent_id": "", "disciplina": "Disciplina A",
         "nivel": "0", "titulo": "Disciplina A", "caminho": "Disciplina A",
         "descricao": "Raiz", "status": "active"},
        {"tema_id": "T1", "parent_id": "R", "disciplina": "Disciplina A",
         "nivel": "1", "titulo": "Tema um", "caminho": "Disciplina A > Tema um",
         "descricao": "Descrição", "status": "active"},
        {"tema_id": "T2", "parent_id": "T1", "disciplina": "Disciplina A",
         "nivel": "2", "titulo": "Subtema", "caminho": "Disciplina A > Tema um > Subtema",
         "descricao": "Descrição", "status": "active"},
        {"tema_id": "INATIVO", "parent_id": "R", "disciplina": "Disciplina A",
         "nivel": "1", "titulo": "Inativo", "caminho": "Disciplina A > Inativo",
         "descricao": "", "status": "inactive"},
    ]


def rotulo(identificador="Q0001", **alteracoes):
    resultado = {
        "id": identificador, "tema_central_id": "T1",
        "tema_central_caminho": "Caminho legível original",
        "extras_ids": "T2", "fora_da_taxonomia": "0",
    }
    resultado.update(alteracoes)
    return resultado


class DadosSinteticos(unittest.TestCase):
    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporario.cleanup)
        self.pasta = Path(self.temporario.name)
        self.gravar_questoes([questao(), questao("Q0360")])
        self.gravar_csv("temas.csv", COLUNAS_TAXONOMIA, temas())
        self.gravar_folha([rotulo()])
        self.taxonomia = carregar_taxonomia(self.pasta / "temas.csv")
        self.questoes = carregar_questoes(self.pasta / "questoes.jsonl")

    def gravar_questoes(self, registros):
        conteudo = "".join(json.dumps(q, ensure_ascii=False) + "\n" for q in registros)
        (self.pasta / "questoes.jsonl").write_text(conteudo, encoding="utf-8")

    def gravar_csv(self, nome, colunas, registros):
        with (self.pasta / nome).open("w", encoding="utf-8", newline="") as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=colunas, lineterminator="\n")
            escritor.writeheader()
            escritor.writerows(registros)

    def gravar_folha(self, registros):
        self.gravar_csv("folha_verdade.csv", COLUNAS_FOLHA_VERDADE, registros)

    def ler_folha(self):
        return carregar_folha_verdade(
            self.pasta / "folha_verdade.csv", self.questoes, self.taxonomia
        )

    def test_preparacao_preserva_textos_origem_hash_ordem_e_nao_grava(self):
        antes = {p.name: p.read_bytes() for p in self.pasta.iterdir()}
        resultado = preparar_dados(self.pasta)
        self.assertEqual([q["id"] for q in resultado["questoes"]], ["Q0001", "Q0360"])
        q = resultado["questoes"][0]
        self.assertEqual(q["enunciado"], "Texto com ação & reação.")
        self.assertIn("COMANDO\nEscolha a alternativa.", q["texto_completo"])
        self.assertIn("B) Segunda.", q["texto_completo"])
        self.assertNotIn("Metadado sem autoridade", q["texto_completo"])
        self.assertEqual(q["disciplina_origem"], "Metadado sem autoridade")
        self.assertEqual(q["referencia_origem"]["linha"], 1)
        canonico = json.dumps(questao(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self.assertEqual(q["referencia_origem"]["sha256_registro_canonico"],
                         hashlib.sha256(canonico.encode("utf-8")).hexdigest())
        self.assertFalse({"tema_central_id", "extras_ids", "decisao"} & q.keys())
        self.assertEqual(resultado["diagnostico"]["questoes"]["coortes"],
                         {"historicas": 1, "recentes": 1})
        self.assertEqual(resultado["diagnostico"]["rotulos"]["questoes_sem_rotulo"], 1)
        self.assertEqual(antes, {p.name: p.read_bytes() for p in self.pasta.iterdir()})

    def test_coorte_limites_nao_restringe_ids_do_parser(self):
        for identificador, esperado in (
            ("Q0001", "historicas"), ("Q0359", "historicas"),
            ("Q0360", "recentes"), ("Q0659", "recentes"),
            ("Q0000", "nao_identificada"), ("Q0660", "nao_identificada"),
            ("ID-LIVRE", "nao_identificada"),
        ):
            with self.subTest(id=identificador):
                original = questao(identificador)
                self.gravar_questoes([original])
                self.assertEqual(carregar_questoes(self.pasta / "questoes.jsonl"), [original])
                self.assertEqual(preparar_questao(original, 1)["coorte"], esperado)

    def test_parser_nao_quebra_registros_em_separadores_unicode(self):
        original = questao()
        original["enunciado_html"] = "Parte um\u2028Parte dois\u0085Parte três"
        self.gravar_questoes([original, questao("Q0002")])
        registros = carregar_questoes(self.pasta / "questoes.jsonl")
        self.assertEqual(len(registros), 2)
        self.assertEqual(registros[0]["enunciado_html"], original["enunciado_html"])

    def test_parser_recusa_ids_duplicados_e_campo_extra(self):
        for registros in ([questao(), questao()], [{**questao(), "tema_sugerido": "T1"}]):
            with self.subTest(registros=registros):
                self.gravar_questoes(registros)
                with self.assertRaises(ValueError):
                    carregar_questoes(self.pasta / "questoes.jsonl")

    def test_parser_recusa_chave_json_duplicada_e_linha_vazia(self):
        serializado = json.dumps(questao())
        for conteudo in ('{"id":"Q0001",' + serializado[1:], serializado + "\n\n"):
            with self.subTest(conteudo=conteudo):
                (self.pasta / "questoes.jsonl").write_text(conteudo, encoding="utf-8")
                with self.assertRaises(ValueError):
                    carregar_questoes(self.pasta / "questoes.jsonl")

    def test_texto_entidades_apenas_uma_vez_e_imagem_sem_ocr(self):
        self.assertEqual(normalizar_texto("&lt;script&gt;conteúdo&lt;/script&gt;"),
                         "<script>conteúdo</script>")
        resultado = analisar_texto("<p>Ação</p><img src='imagem.png'><p>Fim</p>")
        self.assertEqual(resultado["texto"], "Ação\nFim")
        self.assertIn("imagem_sem_texto_alternativo", resultado["avisos"])

    def test_taxonomia_ancestrais_e_inativo_sem_escolha_de_tema(self):
        self.assertEqual(self.taxonomia["por_id"]["T2"]["ancestrais_ids"], ["R", "T1"])
        self.assertEqual(self.taxonomia["por_id"]["T1"]["filhos_ids"], ["T2"])
        self.assertFalse(self.taxonomia["por_id"]["INATIVO"]["elegivel"])

    def test_taxonomia_recusa_pai_ausente_ciclo_e_nivel_incoerente(self):
        for alteracoes in (
            {"parent_id": "AUSENTE"}, {"parent_id": "T2"}, {"nivel": "2"},
        ):
            with self.subTest(alteracoes=alteracoes):
                registros = temas()
                registros[1].update(alteracoes)
                self.gravar_csv("temas.csv", COLUNAS_TAXONOMIA, registros)
                with self.assertRaises(ValueError):
                    carregar_taxonomia(self.pasta / "temas.csv")

    def test_folha_preserva_caminho_deriva_disciplina_e_nao_muta_entradas(self):
        self.gravar_folha([
            rotulo("Q0360", tema_central_id="", tema_central_caminho="",
                   extras_ids="", fora_da_taxonomia="1"),
            rotulo(),
        ])
        antes = copy.deepcopy((self.questoes, self.taxonomia))
        resultado = self.ler_folha()
        self.assertEqual([r["id"] for r in resultado], ["Q0360", "Q0001"])
        self.assertEqual(resultado[0], {
            "id": "Q0360", "tema_central_id": "", "tema_central_caminho": "",
            "extras_ids": [], "fora_da_taxonomia": True, "disciplina": "fora",
        })
        self.assertEqual(resultado[1]["disciplina"], "Disciplina A")
        self.assertEqual(resultado[1]["tema_central_caminho"], "Caminho legível original")
        self.assertEqual(resultado[1]["extras_ids"], ["T2"])
        self.assertIs(resultado[1]["fora_da_taxonomia"], False)
        self.assertEqual(antes, (self.questoes, self.taxonomia))

    def test_folha_recusa_esquema_alterado_e_numero_de_campos(self):
        cabecalho = ",".join(COLUNAS_FOLHA_VERDADE)
        casos = (
            ",".join(reversed(COLUNAS_FOLHA_VERDADE)) + "\n",
            cabecalho + ",extra\n",
            cabecalho.replace("extras_ids", "id") + "\n",
            cabecalho + "\nQ0001,T1,Caminho,T2\n",
            cabecalho + "\nQ0001,T1,Caminho,T2,0,a_mais\n",
        )
        for conteudo in casos:
            with self.subTest(conteudo=conteudo):
                (self.pasta / "folha_verdade.csv").write_text(conteudo, encoding="utf-8")
                with self.assertRaises(ValueError):
                    self.ler_folha()

    def test_folha_recusa_id_desconhecido_duplicado_e_folha_vazia(self):
        for registros in ([rotulo("Q0999")], [rotulo(), rotulo()], []):
            with self.subTest(registros=registros):
                self.gravar_folha(registros)
                with self.assertRaises(ValueError):
                    self.ler_folha()

    def test_folha_recusa_booleano_invalido_e_inconsistencia_de_fora(self):
        casos = [
            {"fora_da_taxonomia": valor} for valor in ("true", "false", "2", "", " 1")
        ] + [
            {"fora_da_taxonomia": "1"},
            {"fora_da_taxonomia": "1", "tema_central_id": "", "extras_ids": "T2"},
            {"tema_central_id": "", "extras_ids": ""},
        ]
        for alteracoes in casos:
            with self.subTest(alteracoes=alteracoes):
                self.gravar_folha([rotulo(**alteracoes)])
                with self.assertRaises(ValueError):
                    self.ler_folha()

    def test_folha_recusa_temas_inativos_inexistentes_e_extras_ambiguos(self):
        casos = [
            {"tema_central_id": "INATIVO"},
            {"tema_central_id": "AUSENTE"},
            *({"extras_ids": valor} for valor in (
                "INATIVO", "AUSENTE", "T2;T2", "T1", "T2;", ";T2", " T2", "T2 "
            )),
        ]
        for alteracoes in casos:
            with self.subTest(alteracoes=alteracoes):
                self.gravar_folha([rotulo(**alteracoes)])
                with self.assertRaises(ValueError):
                    self.ler_folha()


class AnexosReais(unittest.TestCase):
    def test_contrato_real_sem_classificacao(self):
        entrada = RAIZ / "anexos"
        fontes = ["questoes.jsonl", "temas.csv", "folha_verdade.csv"]
        antes = {nome: (entrada / nome).read_bytes() for nome in fontes}
        dados = preparar_dados(entrada)
        self.assertEqual(len(dados["questoes"]), 659)
        self.assertEqual(len(dados["rotulos"]), 100)
        self.assertEqual(len(dados["taxonomia"]["registros"]), 377)
        self.assertEqual(dados["diagnostico"]["questoes"]["coortes"],
                         {"historicas": 359, "recentes": 300})
        self.assertEqual(dados["diagnostico"]["rotulos"]["questoes_sem_rotulo"], 559)
        ids = [q["id"] for q in dados["questoes"]]
        self.assertEqual(ids, [f"Q{i:04d}" for i in range(1, 660)])
        self.assertEqual(len({r["id"] for r in dados["rotulos"]}), 100)
        self.assertTrue(all(r["id"] in ids for r in dados["rotulos"]))
        self.assertTrue(all(not ({"tema_central_id", "extras_ids", "decisao"} & q.keys())
                            for q in dados["questoes"]))
        self.assertEqual(antes, {nome: (entrada / nome).read_bytes() for nome in fontes})


if __name__ == "__main__":
    unittest.main()
