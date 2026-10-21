"""Integração M8 com textos, taxonomia, rótulos e vetores inteiramente sintéticos."""

from copy import deepcopy
import builtins
import math
import unittest
from unittest.mock import patch

from classificacao_catalogo.motor import Representacao, hash_texto
from classificacao_precisao.motor import Motor, RECEITAS
from tests.test_motor_catalogo import caches, questao, taxonomia


def documentos(tax):
    return [{"registros": [
        {"tema_id": i, "descricao": t["descricao"],
         "termos": [t["titulo"], "marcador sintetico", "texto alfa"]}
        for i, t in tax["por_id"].items() if t["status"] == "active" and int(t["nivel"]) > 0
    ]}]


def cache_large(tax, qs):
    return {
        "dimensoes": 1024,
        "temas": {
            i: {"texto_sha256": hash_texto("tema", t), "vetor": [1.0, 0.0] + [0.0] * 1022}
            for i, t in tax["por_id"].items() if t["status"] == "active" and int(t["nivel"]) > 0
        },
        "questoes": {
            q["id"]: {"texto_sha256": hash_texto("questao", q), "vetor": [0.6, 0.8] + [0.0] * 1022}
            for q in qs
        },
    }


def rotulo(q, tema):
    return {"id": q["id"], "tema_central_id": tema, "extras_ids": [], "fora_da_taxonomia": False}


class MotorPrecisaoTests(unittest.TestCase):
    def setUp(self):
        self.tax = taxonomia()
        self.treino = [questao("treino_a", "Especie alfa um e marcador de treinamento"),
                       questao("treino_b", "Especie beta e outra observacao de treinamento")]
        self.rotulos = [rotulo(self.treino[0], "11"), rotulo(self.treino[1], "21")]
        self.q = questao("consulta", "Especie alfa um e marcador sintetico")
        self.original, self.enriquecido = caches(self.tax, [*self.treino, self.q])
        self.documentos = documentos(self.tax)
        self.large = cache_large(self.tax, [*self.treino, self.q])
        self.motor = Motor(self.tax, self.original, self.enriquecido, self.documentos, self.large)

    def _motor(self, large):
        return Motor(self.tax, self.original, self.enriquecido, self.documentos, large)

    def _modelo_dummy(self, receitas=None):
        return {"receitas": list(receitas or RECEITAS), "rankers": {},
                "treino_ids": [q["id"] for q in self.treino],
                "treino_textos": [hash_texto("questao", q) for q in self.treino]}

    def test_baseline_preserva_exatamente_modelo_e_predicao_m7(self):
        referencia = Representacao(self.tax, self.original, self.enriquecido)
        modelo_m7 = referencia.treinar(self.treino, self.rotulos)
        modelo_m8 = self.motor.treinar(self.treino, self.rotulos, ["baseline_m7"])
        self.assertEqual(modelo_m8["baseline"], modelo_m7)
        esperado = referencia.predizer(self.q, modelo_m7, "aprendido_hierarquico")
        obtido = self.motor.predizer(self.q, modelo_m8, "baseline_m7")
        esperado["receita"] = "baseline_m7"
        self.assertEqual({k: obtido[k] for k in esperado}, esperado)
        self.assertEqual(len(obtido["atributos_confianca"]), 9)

    def test_atributos_small_preservam_oito_base_e_acrescentam_seis_sinais(self):
        xs, rl, rs = self.motor.atributos(self.q)
        base, rl_base, rs_base = self.motor.base.atributos(self.q)
        self.assertEqual((rl, rs), (rl_base, rs_base))
        for i, x in xs.items():
            self.assertEqual(len(x), 14)
            self.assertEqual(x[:8], base[i])
            self.assertEqual(x[8:], self.motor.sinais.atributos(self.q, i))
            self.assertTrue(all(math.isfinite(v) for v in x))
            self.assertTrue(all(0 <= v <= 1 for v in x[8:]))

    def test_rankers_small_large_tem_quatorze_features_e_confianca_nove(self):
        receitas = ["sinais_small", "sinais_small_hierarquico", "large_rrf20",
                    "sinais_large", "sinais_large_hierarquico"]
        modelo = self.motor.treinar(self.treino, self.rotulos, receitas)
        self.assertEqual(set(modelo["rankers"]), {"sinais_small", "sinais_large"})
        for ranker in modelo["rankers"].values():
            self.assertEqual(ranker["dimensoes"], 14)
            self.assertEqual(len(ranker["pesos"]), 14)
        for receita in receitas:
            with self.subTest(receita=receita):
                p = self.motor.predizer(self.q, modelo, receita)
                self.assertEqual(p["receita"], receita)
                self.assertIn(p["tema_sugerido_id"], self.motor.temas)
                self.assertEqual(len(p["atributos_confianca"]), 9)
                self.assertTrue(all(math.isfinite(v) for v in p["atributos_confianca"]))
                self.assertEqual(p["atributos_confianca"][:2], [p["score"], p["margem"]])
                self.assertEqual(p["atributos_confianca"][4], float(p["consenso"]))
                self.assertEqual(p["atributos_confianca"][5], p["evidencia_especifica"])
                self.assertTrue(0 <= p["atributos_confianca"][6] <= 1)

    def test_large_substitui_semantica_e_recalcula_interacoes(self):
        large = deepcopy(self.large)
        large["temas"]["21"]["vetor"] = [0.0, 1.0] + [0.0] * 1022
        motor = self._motor(large)
        xs, _, rs = motor.atributos(self.q, True)
        antigos, _, _ = motor.atributos(self.q, False)
        self.assertAlmostEqual(xs["21"][1], 0.8)
        self.assertEqual(rs["21"], 1)
        self.assertEqual(xs["21"][4], 1.0)
        self.assertEqual(xs["21"][5], xs["21"][0] * xs["21"][1])
        self.assertEqual(xs["21"][6], min(xs["21"][3], xs["21"][4]))
        for i in xs:
            self.assertEqual(xs[i][0], antigos[i][0])
            self.assertEqual(xs[i][2], antigos[i][2])
            self.assertEqual(xs[i][7:], antigos[i][7:])

    def test_ressubstituicao_por_id_e_por_texto_e_recusada_antes_de_atributos(self):
        modelo = self._modelo_dummy()
        consultas = [{**self.q, "id": self.treino[0]["id"]}, {**self.treino[0], "id": "outro_id"}]
        for consulta in consultas:
            for receita in RECEITAS:
                with self.subTest(receita=receita), patch.object(self.motor, "atributos") as atributos:
                    with self.assertRaisesRegex(ValueError, "Ressubstituição"):
                        self.motor.predizer(consulta, modelo, receita)
                    atributos.assert_not_called()

    def test_metadados_gabarito_e_rotulo_na_consulta_nao_mudam_resultado(self):
        marcada = {**self.q, "disciplina": "ignorar", "assunto": "ignorar", "banca": "ignorar",
                   "ano": 9999, "tema_central_id": "21", "extras_ids": ["20"],
                   "fora_da_taxonomia": True, "gabarito": "B", "acertos": {"ramo": True}}
        modelo = self.motor.treinar(self.treino, self.rotulos, ["sinais_small", "large_rrf20"])
        for receita in modelo["receitas"]:
            self.assertEqual(self.motor.predizer(self.q, modelo, receita),
                             self.motor.predizer(marcada, modelo, receita))

    def test_receita_desconhecida_ou_nao_treinada_falha_antes_dos_atributos(self):
        with patch.object(self.motor, "atributos") as atributos:
            for receita, modelo in (("inventada", self._modelo_dummy()),
                                    ("sinais_small", self._modelo_dummy(["baseline_m7"]))):
                with self.assertRaisesRegex(ValueError, "Receita desconhecida"):
                    self.motor.predizer(self.q, modelo, receita)
            for receitas in ([], ["inventada"]):
                with self.assertRaisesRegex(ValueError, "Grade não registrada"):
                    self.motor.treinar(self.treino, self.rotulos, receitas)
            atributos.assert_not_called()

    def test_treino_rejeita_ids_duplicados_ou_rotulos_sem_correspondencia(self):
        cenarios = [([self.treino[0], self.treino[0]], self.rotulos),
                    (self.treino, [self.rotulos[0], self.rotulos[0]]),
                    (self.treino, self.rotulos[:1])]
        for qs, rs in cenarios:
            with self.assertRaisesRegex(ValueError, "únicos correspondentes"):
                self.motor.treinar(qs, rs, ["sinais_small"])

    def test_ausencia_de_cache_large_recusa_treino_e_predicao_large(self):
        motor = self._motor(None)
        with self.assertRaisesRegex(ValueError, "cache preparado"):
            motor.treinar(self.treino, self.rotulos, ["sinais_large"])
        modelo = motor.treinar(self.treino, self.rotulos, ["large_rrf20"])
        with self.assertRaisesRegex(ValueError, "cache preparado"):
            motor.predizer(self.q, modelo, "large_rrf20")

    def test_cache_large_recusa_dimensao_declarada_incompativel(self):
        large = deepcopy(self.large)
        large["dimensoes"] = 384
        with self.assertRaises(ValueError):
            self._motor(large)

    def test_cache_large_recusa_temas_incompletos_ou_assinatura_divergente(self):
        large = deepcopy(self.large)
        del large["temas"]["11"]
        with self.assertRaises(ValueError):
            self._motor(large)
        large = deepcopy(self.large)
        large["temas"]["11"]["texto_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "catálogo congelado"):
            self._motor(large)

    def test_cache_large_recusa_questao_ausente_ou_assinatura_divergente(self):
        for ausente in (True, False):
            large = deepcopy(self.large)
            if ausente:
                del large["questoes"][self.q["id"]]
            else:
                large["questoes"][self.q["id"]]["texto_sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "Questão large ausente ou texto divergente"):
                self._motor(large).atributos(self.q, True)

    def test_cache_large_recusa_vetores_reais_com_dimensao_errada(self):
        for secao, i in (("temas", "11"), ("questoes", self.q["id"])):
            for vetor in ([1.0, 0.0], [1.0] * 1023, [1.0] * 1025):
                large = deepcopy(self.large)
                large[secao][i]["vetor"] = vetor
                with self.subTest(secao=secao, dimensao=len(vetor)), self.assertRaises(ValueError):
                    self._motor(large).atributos(self.q, True)

    def test_cache_large_recusa_zero_nan_inf_e_booleanos(self):
        for secao, i in (("temas", "11"), ("questoes", self.q["id"])):
            for valor in (0.0, float("nan"), float("inf"), True):
                large = deepcopy(self.large)
                large[secao][i]["vetor"] = [valor] + [0.0] * 1023
                with self.subTest(secao=secao, valor=valor), self.assertRaises(ValueError):
                    self._motor(large).atributos(self.q, True)

    def test_cache_large_vazio_e_recusado_com_erro_explicito(self):
        with self.assertRaises(ValueError):
            self._motor({}).atributos(self.q, True)

    def test_recebidos_e_modelo_nao_sao_alterados_pela_execucao(self):
        objetos = [self.tax, self.original, self.enriquecido, self.documentos, self.large,
                   self.treino, self.rotulos, self.q]
        antes = deepcopy(objetos)
        modelo = self.motor.treinar(self.treino, self.rotulos, ["sinais_small", "large_rrf20"])
        modelo_antes = deepcopy(modelo)
        for receita in modelo["receitas"]:
            self.motor.predizer(self.q, modelo, receita)
        self.assertEqual(objetos, antes)
        self.assertEqual(modelo, modelo_antes)

    def test_cache_large_e_copiado_na_construcao(self):
        large = deepcopy(self.large)
        motor = self._motor(large)
        large["temas"]["11"]["vetor"] = [0.0] * 1024
        large["questoes"][self.q["id"]]["texto_sha256"] = "adulterado"
        xs, _, _ = motor.atributos(self.q, True)
        self.assertAlmostEqual(xs["11"][1], 0.6)

    def test_execucao_nao_importa_encoders_ou_bibliotecas_de_modelos(self):
        importar = builtins.__import__

        def seguro(nome, *args, **kwargs):
            if nome.split(".", 1)[0] in {"onnxruntime", "torch", "transformers", "tokenizers", "numpy"}:
                raise AssertionError("Encoder ou biblioteca externa importada durante classificação.")
            return importar(nome, *args, **kwargs)

        with patch("builtins.__import__", side_effect=seguro):
            motor = self._motor(self.large)
            modelo = motor.treinar(self.treino, self.rotulos, ["sinais_small", "large_rrf20"])
            for receita in modelo["receitas"]:
                self.assertIn(motor.predizer(self.q, modelo, receita)["tema_sugerido_id"], motor.temas)


if __name__ == "__main__":
    unittest.main()
