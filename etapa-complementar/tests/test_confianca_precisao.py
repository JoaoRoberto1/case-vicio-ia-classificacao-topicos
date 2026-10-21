"""Somente cenários numéricos sintéticos, sem dados ou rótulos do case."""

import copy
import math
import unittest

from classificacao_precisao.confianca import (
    MAX_ITERACOES, REGULARIZACAO, ajustar, aplicar, medir, prever, selecionar,
    validar_modelo,
)


def treino(n=40, dimensoes=9):
    return [{
        "atributos_confianca": [float(i - n / 2), float(i % 3), 7.0,
                                 math.sin(i), float(i % 2), 0.5, 0.0, 0.1, 0.9, 3.0][:dimensoes],
        "acertos": {"ramo": i >= n // 2},
    } for i in range(n)]


def predicao(i, ramo, *, exato=None, score=0.0, margem=0.0, consenso=False,
             confianca_oof=0.1, evidencia=0.0):
    return {
        "id": f"sintetico_{i}", "particao_interna": i % 3,
        "score": score, "margem": margem, "consenso": consenso,
        "confianca_oof": confianca_oof, "evidencia_especifica": evidencia,
        "acertos": {"ramo": ramo, "exato": ramo if exato is None else exato},
    }


class ConfiancaPrecisaoTests(unittest.TestCase):
    def test_ajusta_nove_atributos_com_objetivo_soma_e_newton(self):
        modelo = ajustar(treino())
        self.assertEqual(modelo["dimensoes"], 9)
        self.assertEqual(modelo["regularizacao"], REGULARIZACAO)
        self.assertEqual(modelo["convergencia"]["max_iteracoes"], MAX_ITERACOES)
        self.assertTrue(modelo["convergencia"]["convergiu"])
        self.assertLess(prever(modelo, treino()[0]), 0.2)
        self.assertGreater(prever(modelo, treino()[-1]), 0.8)
        self.assertEqual(modelo["metodo"], "logistica_l2_pseudocontagens")

    def test_dimensoes_suportadas_e_colinearidade_regularizada(self):
        for d in (6, 9, 10):
            with self.subTest(d=d):
                ps = treino(dimensoes=d)
                for p in ps:
                    p["atributos_confianca"] = [p["atributos_confianca"][0]] * d
                modelo = ajustar(ps)
                self.assertEqual(modelo["dimensoes"], d)
                self.assertGreater(prever(modelo, ps[-1]), prever(modelo, ps[0]))

    def test_constante_em_cada_extremo_usa_pseudocontagens(self):
        for alvo in (False, True):
            ps = treino(12)
            for p in ps:
                p["acertos"]["ramo"] = alvo
            modelo = ajustar(ps)
            self.assertEqual(modelo["metodo"], "constante_pseudocontagens")
            self.assertEqual(modelo["coeficientes"], [0.0] * 9)
            esperado = (12 * alvo + 0.5) / 13
            self.assertAlmostEqual(prever(modelo, ps[0]), esperado)
            self.assertAlmostEqual(prever(modelo, ps[-1]), esperado)
            self.assertEqual(modelo["convergencia"]["iteracoes"], 0)

    def test_atributos_constantes_com_alvos_mistos(self):
        ps = treino(12)
        for p in ps:
            p["atributos_confianca"] = [7.0] * 9
        modelo = ajustar(ps)
        self.assertEqual(modelo["medias"], [7.0] * 9)
        self.assertEqual(modelo["escalas"], [1.0] * 9)
        self.assertEqual(modelo["coeficientes"], [0.0] * 9)
        self.assertAlmostEqual(prever(modelo, ps[0]), 0.5)

    def test_transformacao_usa_so_treino_e_nao_muta_modelo(self):
        ps = treino(20)
        original = copy.deepcopy(ps)
        modelo = ajustar(ps)
        antes = copy.deepcopy(modelo)
        self.assertEqual(modelo["medias"][0], -0.5)
        self.assertAlmostEqual(modelo["escalas"][0], math.sqrt(33.25))
        externo = {"atributos_confianca": [1000.0] * 9}
        probabilidade = prever(modelo, externo)
        self.assertTrue(0 <= probabilidade <= 1)
        self.assertEqual(modelo, antes)
        self.assertEqual(ps, original)
        self.assertEqual(modelo, ajustar(ps))

    def test_prever_nao_consulta_alvos_ou_particoes(self):
        class SemAlvos(dict):
            def get(self, chave, *args):
                if chave != "atributos_confianca":
                    raise AssertionError(f"Acesso indevido: {chave}")
                return super().get(chave, *args)

            def __getitem__(self, chave):
                if chave != "atributos_confianca":
                    raise AssertionError(f"Acesso indevido: {chave}")
                return super().__getitem__(chave)

        modelo = ajustar(treino())
        p = treino()[3]
        self.assertEqual(prever(modelo, p), prever(modelo, SemAlvos(p)))
        p["acertos"] = "não consultado"
        self.assertEqual(prever(modelo, p), prever(modelo, SemAlvos(p)))

    def test_rejeita_nan_inf_bool_e_string_nos_atributos(self):
        modelo = ajustar(treino())
        for v in (float("nan"), float("inf"), float("-inf"), True, "0.5", 10 ** 500):
            with self.subTest(v=str(v)[:20]):
                ps = treino()
                ps[0]["atributos_confianca"][1] = v
                with self.assertRaises(ValueError):
                    ajustar(ps)
                with self.assertRaises(ValueError):
                    prever(modelo, ps[0])

    def test_rejeita_dimensao_vazia_excessiva_mista_ou_incompativel(self):
        modelo = ajustar(treino())
        for valores in ([], [0.0] * 5, [0.0] * 11, (0.0,) * 9):
            ps = treino()
            ps[0]["atributos_confianca"] = valores
            with self.assertRaises(ValueError):
                ajustar(ps)
        ps = treino()
        ps[0]["atributos_confianca"] = [0.0] * 6
        with self.assertRaises(ValueError):
            ajustar(ps)
        with self.assertRaises(ValueError):
            prever(modelo, {"atributos_confianca": [0.0] * 6})

    def test_rejeita_treino_vazio_e_alvos_nao_booleanos(self):
        for ps in ([], {}, None):
            with self.assertRaises(ValueError):
                ajustar(ps)
        for alvo in (1, 0, None, "True"):
            ps = treino()
            ps[0]["acertos"]["ramo"] = alvo
            with self.assertRaises(ValueError):
                ajustar(ps)

    def test_escalas_grandes_finitas_e_overflow_recusado(self):
        ps = treino()
        for p in ps:
            p["atributos_confianca"][0] *= 1e100
        modelo = ajustar(ps)
        self.assertTrue(math.isfinite(prever(modelo, ps[-1])))
        for i, p in enumerate(ps):
            p["atributos_confianca"][0] = 1.7e308 if i % 2 else -1.7e308
        with self.assertRaises(ValueError):
            ajustar(ps)

    def test_modelos_corrompidos_recusados(self):
        modelo = ajustar(treino())
        alteracoes = [("schema", "outro"), ("dimensoes", True), ("regularizacao", 0.5),
                      ("coeficientes", [0.0]), ("escalas", [0.0] * 9),
                      ("intercepto", float("nan")), ("acertos", -1), ("n", True),
                      ("pseudocontagens", {}), ("convergencia", {}), ("metodo", "constante")]
        for chave, valor in alteracoes:
            with self.subTest(chave=chave):
                alterado = copy.deepcopy(modelo)
                alterado[chave] = valor
                with self.assertRaises(ValueError):
                    validar_modelo(alterado)

    def test_constante_corrompida_nao_e_aceita(self):
        ps = treino()
        for p in ps:
            p["acertos"]["ramo"] = True
        modelo = ajustar(ps)
        modelo["coeficientes"][0] = 0.1
        with self.assertRaises(ValueError):
            prever(modelo, ps[0])


class SelecaoPrecisaoTests(unittest.TestCase):
    def test_grade_tem_dezoito_regras_com_cortes_fixos(self):
        ps = [predicao(i, True) for i in range(20)]
        politica = selecionar({"a": ps}, ["a"])
        candidatos = politica["diagnosticos"]
        self.assertEqual(len(candidatos), 18)
        self.assertEqual(len({c["regra"] for c in candidatos}), 18)
        cortes = [c["corte"] for c in candidatos if c["regra"].startswith("confianca_p")]
        self.assertEqual(cortes, [0.5, 0.6, 0.7, 0.8, 0.9, 0.95])

    def test_selecao_confia_oof_aplicacao_confia_final_sem_contaminacao(self):
        ps = [predicao(i, i < 12, confianca_oof=0.8 if i < 12 else 0.2) for i in range(20)]
        for p in ps:
            p["confianca"] = 0.01
        politica = selecionar({"a": ps}, ["a"])
        self.assertEqual(politica["regra"], "confianca_p50")
        self.assertEqual((politica["n"], politica["k"]), (12, 12))
        self.assertFalse(aplicar({"confianca": 0.1, "confianca_oof": 0.99}, politica))
        self.assertTrue(aplicar({"confianca": 0.9, "confianca_oof": 0.01}, politica))
        with self.assertRaises(ValueError):
            aplicar({"confianca_oof": 0.9}, politica)
        self.assertEqual(politica["probabilidade_condicional"], 1.0)
        self.assertAlmostEqual(politica["probabilidade_condicional_suavizada"], 12.5 / 13)

    def test_tres_conjuncoes_salvam_mediana_interna(self):
        ps = [predicao(i, i >= 9, margem=float(i), consenso=i % 2 == 0,
                       evidencia=0.5 if i % 3 == 0 else 0.25) for i in range(20)]
        politica = selecionar({"a": ps}, ["a"])
        regras = {c["regra"]: c for c in politica["diagnosticos"]}
        for nome in ("consenso_margem_q50", "evidencia_50_margem_q50"):
            self.assertEqual(regras[nome]["corte"], 9.0)
        regra = {**regras["consenso_margem_q50"], "habilitada": True}
        self.assertTrue(aplicar({"consenso": True, "margem": 9.0}, regra))
        self.assertFalse(aplicar({"consenso": True, "margem": 8.9}, regra))
        self.assertFalse(aplicar({"consenso": False, "margem": 999.0}, regra))
        regra = {**regras["evidencia_50_margem_q50"], "habilitada": True}
        self.assertTrue(aplicar({"evidencia_especifica": 0.5, "margem": 9.0}, regra))
        self.assertFalse(aplicar({"evidencia_especifica": 0.49, "margem": 999.0}, regra))
        regra = {**regras["consenso_evidencia_25"], "habilitada": True}
        self.assertTrue(aplicar({"evidencia_especifica": 0.25, "consenso": True}, regra))
        self.assertFalse(aplicar({"evidencia_especifica": 0.24, "consenso": True}, regra))

    def test_suporte_nove_nao_habilita_e_retorna_fallback_sem_precisao(self):
        politica = selecionar({"a": [predicao(i, True, consenso=True) for i in range(9)]}, ["a"])
        self.assertFalse(politica["habilitada"])
        self.assertIsNone(politica["regra"])
        self.assertIsNone(politica["precisao_empirica"])
        self.assertIsNone(politica["probabilidade_condicional"])
        self.assertFalse(aplicar({}, politica))

    def test_precisao_exatamente_noventa_e_cinco_com_suporte_vinte(self):
        ps = [predicao(i, i != 0, consenso=True) for i in range(20)]
        politica = selecionar({"a": ps}, ["a"])
        self.assertTrue(politica["habilitada"])
        self.assertEqual(politica["n"], 20)
        self.assertEqual(politica["precisao_empirica"], 0.95)
        self.assertEqual(politica["probabilidade_condicional"], 0.95)
        self.assertLess(politica["probabilidade_condicional_suavizada"], 0.95)

    def test_cobertura_tem_prioridade_sobre_precisao(self):
        a = [predicao(i, i != 0) for i in range(20)]
        b = [predicao(i, i < 10, consenso=i < 10) for i in range(20)]
        politica = selecionar({"a": a, "b": b}, ["b", "a"])
        self.assertEqual(politica["receita"], "a")
        self.assertEqual(politica["n"], 20)

    def test_prioridade_desempata_e_fallback_usa_ramo_depois_exato(self):
        ps = [predicao(i, True) for i in range(20)]
        self.assertEqual(selecionar({"a": ps, "b": ps}, ["b", "a"])["receita"], "b")
        a = [predicao(i, i < 3, exato=False) for i in range(8)]
        b = [predicao(i, i < 3) for i in range(8)]
        politica = selecionar({"a": a, "b": b}, ["a", "b"])
        self.assertFalse(politica["habilitada"])
        self.assertEqual(politica["receita"], "b")

    def test_global_desempata_candidatas_antes_da_prioridade(self):
        a = [predicao(i, i < 10, consenso=i < 10) for i in range(20)]
        b = [predicao(i, i < 11, consenso=i < 10) for i in range(20)]
        politica = selecionar({"a": a, "b": b}, ["a", "b"])
        self.assertEqual(politica["receita"], "b")
        self.assertEqual(politica["n"], 10)

    def test_aplicacao_sem_alvo_sem_reajuste_e_modelo_inalterado(self):
        ps = [predicao(i, i >= 9, margem=float(i)) for i in range(20)]
        politica = selecionar({"a": ps}, ["a"])
        original = copy.deepcopy(politica)
        self.assertTrue(aplicar({"margem": 100.0}, politica))
        self.assertFalse(aplicar({"margem": 1.0}, politica))
        self.assertEqual(politica, original)
        resultado = medir([predicao(99, False)], [True])
        self.assertEqual(resultado["precision"], 0.0)
        self.assertIsNone(medir([predicao(99, False)], [False])["precision"])

    def test_rejeita_dados_e_prioridades_inconsistentes(self):
        ps = [predicao(i, True) for i in range(12)]
        for prioridades in ([], ["a", "a"], ["b"], [1]):
            with self.assertRaises(ValueError):
                selecionar({"a": ps}, prioridades)
        for chave, valor in (("id", ""), ("score", float("nan")), ("margem", float("inf")),
                             ("confianca_oof", 1.1), ("evidencia_especifica", -0.1),
                             ("consenso", 1), ("particao_interna", None), ("acertos", {})):
            alterados = copy.deepcopy(ps)
            alterados[0][chave] = valor
            with self.subTest(chave=chave), self.assertRaises(ValueError):
                selecionar({"a": alterados}, ["a"])
        alterados = copy.deepcopy(ps)
        alterados[1]["id"] = alterados[0]["id"]
        with self.assertRaises(ValueError):
            selecionar({"a": alterados}, ["a"])

    def test_receitas_precisam_mesmos_ids_e_particoes(self):
        ps = [predicao(i, True) for i in range(12)]
        for chave, valor in (("id", "outro"), ("particao_interna", "outra")):
            alterados = copy.deepcopy(ps)
            alterados[0][chave] = valor
            with self.assertRaises(ValueError):
                selecionar({"a": ps, "b": alterados}, ["a", "b"])

    def test_aplicacao_recusa_regra_desconhecida_e_probabilidade_invalida(self):
        with self.assertRaises(ValueError):
            aplicar({}, {"habilitada": True, "regra": "livre"})
        with self.assertRaises(ValueError):
            aplicar({}, {"habilitada": 1})
        for valor in (float("nan"), float("inf"), -0.1, 1.1, True):
            with self.assertRaises(ValueError):
                aplicar({"confianca": valor}, {"habilitada": True, "regra": "confianca_p50", "corte": 0.5})


if __name__ == "__main__":
    unittest.main()
