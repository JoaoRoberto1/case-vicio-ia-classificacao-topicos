"""Contratos M7 com taxonomia, textos e rótulos inteiramente sintéticos."""

from copy import deepcopy
import unittest
from unittest.mock import patch

from classificacao_catalogo.experimento import _corte
from classificacao_catalogo.motor import (
    CONFIG_PADRAO, Representacao, _texto_questao, ancestral_comum, hash_texto,
)


def questao(identificador, texto="texto alfa sintetico"):
    return {"id": identificador, "enunciado": texto, "comando": "Analise o texto",
            "alternativas": {"A": "alternativa alfa", "B": "alternativa beta"}}


def taxonomia():
    definicoes = [
        ("0", "Disciplina", "", [], 0),
        ("10", "Grupo alfa", "0", ["0"], 1),
        ("11", "Especie alfa um", "10", ["0", "10"], 2),
        ("12", "Especie alfa dois", "10", ["0", "10"], 2),
        ("13", "Especie alfa tres", "10", ["0", "10"], 2),
        ("20", "Grupo beta", "0", ["0"], 1),
        ("21", "Especie beta", "20", ["0", "20"], 2),
        ("30", "Considerações Gerais", "0", ["0"], 1),
        ("31", "Subgrupo um", "30", ["0", "30"], 2),
        ("32", "Subgrupo dois", "30", ["0", "30"], 2),
        ("33", "Subgrupo tres", "30", ["0", "30"], 2),
    ]
    registros = [{"tema_id": i, "titulo": titulo, "parent_id": pai,
                  "ancestrais_ids": ancestrais, "nivel": str(nivel),
                  "status": "active", "descricao": "Descricao sintetica " + titulo,
                  "caminho": "Disciplina > " + titulo}
                 for i, titulo, pai, ancestrais, nivel in definicoes]
    return {"por_id": {t["tema_id"]: t for t in registros}, "registros": registros}


def caches(tax, questoes):
    temas = {i: {"vetor": [1.0, 0.0], "texto_sha256": hash_texto("tema", t)}
             for i, t in tax["por_id"].items() if int(t["nivel"]) > 0}
    qs = {q["id"]: {"vetor": [0.6, 0.8], "texto_sha256": hash_texto("questao", q)}
          for q in questoes}
    return {"temas": deepcopy(temas), "questoes": qs}, {"temas": deepcopy(temas)}


def modelo_sem_consulta(qtreino=None):
    qtreino = qtreino or questao("treino", "texto distinto de treinamento")
    return {"ranker": {}, "treino_ids": [qtreino["id"]],
            "treino_textos": [hash_texto("questao", qtreino)]}


class TestContratoRepresentacao(unittest.TestCase):
    def setUp(self):
        self.tax = taxonomia()
        self.q = questao("consulta")
        self.original, self.enriquecido = caches(self.tax, [self.q])
        self.motor = Representacao(self.tax, self.original, self.enriquecido)

    def test_metadata_nao_entra_no_texto_nem_hash(self):
        marcada = {**self.q, "disciplina": "NAO_INCLUIR_DISCIPLINA",
                   "assunto": "NAO_INCLUIR_ASSUNTO", "banca": "NAO_INCLUIR_BANCA",
                   "ano": "NAO_INCLUIR_ANO", "tema_central_id": "NAO_INCLUIR_ROTULO",
                   "extras_ids": ["NAO_INCLUIR_EXTRA"], "gabarito": "NAO_INCLUIR_GABARITO"}
        texto = _texto_questao(marcada, CONFIG_PADRAO)
        self.assertNotIn("NAO_INCLUIR", texto)
        self.assertEqual(texto, _texto_questao(self.q, CONFIG_PADRAO))
        self.assertEqual(hash_texto("questao", marcada), hash_texto("questao", self.q))
        self.assertEqual(self.motor.atributos(marcada), self.motor.atributos(self.q))

    def test_idf_nao_muda_quando_consulta_e_memorizada(self):
        antes = deepcopy(self.motor.idf)
        self.motor.atributos(self.q)
        self.assertEqual(antes, self.motor.idf)

    def test_recusa_ressubstituicao_por_id_mesmo_com_texto_diferente(self):
        modelo = modelo_sem_consulta(questao("consulta", "texto de treino diferente"))
        with self.assertRaisesRegex(ValueError, "Ressubstituição"):
            self.motor.predizer(self.q, modelo, "enriquecido_lexical")

    def test_recusa_ressubstituicao_por_texto_com_id_diferente(self):
        outro_id = {**self.q, "id": "treino"}
        modelo = modelo_sem_consulta(outro_id)
        with self.assertRaisesRegex(ValueError, "Ressubstituição"):
            self.motor.predizer(self.q, modelo, "enriquecido_lexical")

    def test_receita_desconhecida_falha_antes_de_calcular_atributos(self):
        with patch.object(self.motor, "atributos") as atributos:
            with self.assertRaisesRegex(ValueError, "Receita não registrada"):
                self.motor.predizer(self.q, modelo_sem_consulta(), "receita_inventada")
            atributos.assert_not_called()

    def test_tema_enriquecido_com_hash_divergente_e_recusado(self):
        cache = deepcopy(self.enriquecido)
        cache["temas"]["11"]["texto_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Descrição enriquecida diverge"):
            Representacao(self.tax, self.original, cache)

    def test_cache_incompleto_de_temas_e_recusado(self):
        cache = deepcopy(self.enriquecido)
        del cache["temas"]["11"]
        with self.assertRaisesRegex(ValueError, "exatamente os candidatos"):
            Representacao(self.tax, self.original, cache)

    def test_consulta_com_texto_divergente_e_recusada(self):
        alterada = {**self.q, "enunciado": "texto adulterado"}
        with self.assertRaisesRegex(ValueError, "texto diferente do cache"):
            self.motor.atributos(alterada)

    def test_consulta_ausente_e_recusada(self):
        with self.assertRaisesRegex(ValueError, "Questão ausente"):
            self.motor.atributos({**self.q, "id": "ausente"})

    def test_cache_de_consultas_nao_oculta_hash_adulterado(self):
        self.motor.atributos(self.q)
        self.original["questoes"]["consulta"]["texto_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "texto diferente do cache"):
            self.motor.atributos(self.q)

    def test_predicao_lexical_fora_do_treino_tem_candidato_valido(self):
        resultado = self.motor.predizer(self.q, modelo_sem_consulta(), "enriquecido_lexical")
        self.assertEqual(resultado["id"], self.q["id"])
        self.assertIn(resultado["tema_sugerido_id"], self.motor.temas)
        self.assertNotEqual(resultado["tema_sugerido_id"], "0")


class TestHierarquiaSintetica(unittest.TestCase):
    def setUp(self):
        self.tax = taxonomia()

    def test_lca_especifico_dos_tres_irmaos(self):
        self.assertEqual(ancestral_comum(["11", "12", "13"], self.tax), "10")

    def test_lca_inclui_o_proprio_candidato_quando_e_ancestral(self):
        self.assertEqual(ancestral_comum(["10", "11", "12"], self.tax), "10")

    def test_raiz_nao_e_retorno_valido(self):
        self.assertIsNone(ancestral_comum(["11", "12", "21"], self.tax))

    def test_titulo_generico_com_acentos_nao_e_retorno_valido(self):
        self.assertIsNone(ancestral_comum(["31", "32", "33"], self.tax))

    def test_ancestral_inativo_nao_e_retorno_valido(self):
        self.tax["por_id"]["10"]["status"] = "inactive"
        self.assertIsNone(ancestral_comum(["11", "12", "13"], self.tax))

    def _prever_com_ordem(self, primeiros):
        q = questao("consulta")
        original, enriquecido = caches(self.tax, [q])
        motor = Representacao(self.tax, original, enriquecido)
        ordem = primeiros + [i for i in motor.temas if i not in primeiros]
        ranks = {i: n for n, i in enumerate(ordem, 1)}
        atributos = {i: [1 / ranks[i], 0.5, 0.4, 0.3, 0.2, 0.1, 0.1, 0.2]
                     for i in motor.temas}
        with patch.object(motor, "atributos", return_value=(atributos, ranks, ranks)), \
                patch("classificacao_catalogo.motor.pontuar", side_effect=lambda _, x: x[0]):
            return motor.predizer(q, modelo_sem_consulta(), "aprendido_hierarquico")

    def test_predicao_hierarquica_recua_para_ramo_especifico(self):
        resultado = self._prever_com_ordem(["11", "12", "13"])
        self.assertEqual(resultado["tema_sugerido_id"], "10")
        self.assertTrue(resultado["recuou_na_hierarquia"])
        self.assertEqual(resultado["nivel_sugerido"], 1)
        self.assertEqual(resultado["top_candidatos"][0]["tema_id"], "11")

    def test_sem_lca_especifico_mantem_primeiro_candidato(self):
        resultado = self._prever_com_ordem(["11", "12", "21"])
        self.assertEqual(resultado["tema_sugerido_id"], "11")
        self.assertFalse(resultado["recuou_na_hierarquia"])

    def test_lca_generico_mantem_primeiro_candidato(self):
        resultado = self._prever_com_ordem(["31", "32", "33"])
        self.assertEqual(resultado["tema_sugerido_id"], "31")
        self.assertFalse(resultado["recuou_na_hierarquia"])


class TestSeparacaoCorte(unittest.TestCase):
    class MotorEspiao:
        def __init__(self):
            self.ajustes = []
            self.consultas = []

        def treinar(self, questoes, rotulos):
            self.ajustes.append((questoes, rotulos))
            return {"marcador": "modelo sintético"}

        def predizer(self, q, modelo, receita):
            self.consultas.append((q, modelo, receita))
            return {"id": q["id"], "receita": receita}

    def test_sobreposicao_de_ids_falha_antes_do_ajuste(self):
        motor = self.MotorEspiao()
        with self.assertRaisesRegex(ValueError, "Sobreposição"):
            _corte(motor, {}, {"a": {}}, ["a"], ["a"], ["enriquecido_lexical"])
        self.assertEqual(motor.ajustes, [])

    def test_rotulo_de_validacao_no_ajuste_e_recusado(self):
        motor = self.MotorEspiao()
        with self.assertRaisesRegex(ValueError, "rótulo de avaliação"):
            _corte(motor, {}, {"a": {}, "b": {}}, ["a"], ["b"], ["enriquecido_lexical"])
        self.assertEqual(motor.ajustes, [])

    def test_corte_entrega_somente_treino_ao_ajuste_e_validacao_a_predicao(self):
        motor = self.MotorEspiao()
        qs = {i: questao(i, "conteudo distinto " + i) for i in ["a", "b"]}
        rotulo = {"id": "a", "tema_central_id": "11"}
        resultado, modelo = _corte(motor, qs, {"a": rotulo}, ["a"], ["b"], ["enriquecido_lexical"])
        self.assertEqual(motor.ajustes, [([qs["a"]], [rotulo])])
        self.assertEqual(motor.consultas, [(qs["b"], modelo, "enriquecido_lexical")])
        self.assertEqual(resultado["enriquecido_lexical"], [{"id": "b", "receita": "enriquecido_lexical"}])


if __name__ == "__main__":
    unittest.main()
