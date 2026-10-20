"""Testes sintéticos de calibração, sem conteúdo ou rótulos do case."""

from copy import deepcopy
import json
import math
import unittest

from classificacao_decisao.calibracao import ajustar, metricas, prever, validar_modelo, wilson


def registros():
    return [
        {"score": indice / 19, "margem": (indice % 3) / 10, "acerto": indice >= 10}
        for indice in range(20)
    ]


class TestCalibracaoM4(unittest.TestCase):
    def test_constante_e_pseudocontagens(self):
        dados = [{"acerto": True}] * 3 + [{"acerto": False}]
        modelo = ajustar(dados, [])
        self.assertAlmostEqual(prever(modelo, {}), 3.5 / 5)
        self.assertEqual(modelo["n"], 4)
        self.assertEqual(modelo["acertos"], 3)
        self.assertEqual(modelo["metodo"], "constante_pseudocontagens")

    def test_classe_unica_nao_inventa_efeito_dos_atributos(self):
        for alvo in (True, False):
            dados = [{"score": i, "margem": i * 10, "acerto": alvo} for i in range(4)]
            modelo = ajustar(dados, ["score", "margem"])
            esperado = (4 * alvo + 0.5) / 5
            self.assertEqual(modelo["coeficientes"], [0.0, 0.0])
            self.assertAlmostEqual(prever(modelo, {"score": -100, "margem": 100}), esperado)
            self.assertAlmostEqual(prever(modelo, {"score": 100, "margem": -100}), esperado)

    def test_dados_informativos_produzem_relacao_monotona(self):
        modelo = ajustar(registros(), ["score"])
        probabilidades = [prever(modelo, {"score": i / 20}) for i in range(21)]
        self.assertGreater(modelo["coeficientes"][0], 0.0)
        self.assertTrue(all(a < b for a, b in zip(probabilidades, probabilidades[1:])))
        self.assertLess(probabilidades[0], 0.15)
        self.assertGreater(probabilidades[-1], 0.85)

    def test_separacao_perfeita_tem_coeficientes_finitos_e_probabilidades_interiores(self):
        dados = [
            {"score": -1.0, "margem": -1.0, "acerto": False},
            {"score": 1.0, "margem": 1.0, "acerto": True},
        ] * 20
        modelo = ajustar(dados, ["score", "margem"])
        for valor in [modelo["intercepto"], *modelo["coeficientes"]]:
            self.assertTrue(math.isfinite(valor))
        self.assertTrue(0 < prever(modelo, dados[0]) < 0.1)
        self.assertTrue(0.9 < prever(modelo, dados[1]) < 1)
        self.assertTrue(modelo["convergencia"]["convergiu"])

    def test_padronizacao_torna_ajuste_invariante_a_escala_positiva(self):
        dados = registros()
        transformados = [
            {**r, "score": 1e6 * r["score"] + 200, "margem": 7 * r["margem"] - 4}
            for r in dados
        ]
        modelo = ajustar(dados, ["score", "margem"])
        outro = ajustar(transformados, ["score", "margem"])
        for original, transformado in zip(dados, transformados):
            self.assertAlmostEqual(prever(modelo, original), prever(outro, transformado), places=10)

    def test_predicao_nao_muda_estatisticas_ou_lera_alvo(self):
        dados = [{"score": 0.0, "acerto": False}, {"score": 2.0, "acerto": True}]
        modelo = ajustar(dados, ["score"])
        antes = deepcopy(modelo)
        self.assertEqual(modelo["medias"], [1.0])
        self.assertEqual(modelo["escalas"], [1.0])
        p = prever(modelo, {"score": 5000, "acerto": object()})
        self.assertEqual(modelo, antes)
        self.assertEqual(p, prever(modelo, {"score": 5000}))
        self.assertGreater(p, 0.99)

    def test_atributo_constante_tem_escala_um_e_coeficiente_zero(self):
        for n, constante in ((20, 4.2), (3, 0.1)):
            dados = [{**r, "margem": constante} for r in registros()[:n]]
            dados[-1]["acerto"] = True
            modelo = ajustar(dados, ["score", "margem"])
            self.assertEqual(modelo["escalas"][1], 1.0)
            self.assertEqual(modelo["medias"][1], constante)
            self.assertAlmostEqual(modelo["coeficientes"][1], 0.0)

    def test_roundtrip_json_preserva_predicao_e_novo_treino_e_deterministico(self):
        modelo = ajustar(registros(), ["score", "margem"])
        recarregado = json.loads(json.dumps(modelo, allow_nan=False))
        self.assertEqual(modelo, ajustar(registros(), ["score", "margem"]))
        for registro in registros():
            self.assertEqual(prever(modelo, registro), prever(recarregado, registro))

    def test_regularizacao_maior_reduz_coeficientes(self):
        fraco = ajustar(registros(), ["score"], regularizacao=0.1)
        forte = ajustar(registros(), ["score"], regularizacao=10.0)
        self.assertGreater(abs(fraco["coeficientes"][0]), abs(forte["coeficientes"][0]))

    def test_colinearidade_converge_e_satisfaz_equacoes_do_objetivo(self):
        # Regressão do caso cuja Armijo estacionava por arredondamento da log-loss.
        # Derivadas calculadas independentemente, sem chamar helpers do otimizador.
        dados = [
            {"score": (i + 1) / 10, "margem": (i + 1) / 100, "acerto": i % 2 == 1}
            for i in range(6)
        ]
        for indices in ((0, 1, 2, 3), (0, 1, 4, 5), (2, 3, 4, 5)):
            treino = [dados[i] for i in indices]
            modelo = ajustar(treino, ["score", "margem"])
            erros = [prever(modelo, r) - r["acerto"] for r in treino]
            centro = 1 / (1 + math.exp(-modelo["intercepto"]))
            gradiente_intercepto = math.fsum(erros) + centro - 0.5
            self.assertLessEqual(abs(gradiente_intercepto), 1e-8)
            for atributo, media, escala, coeficiente in zip(
                modelo["atributos"], modelo["medias"], modelo["escalas"], modelo["coeficientes"],
            ):
                gradiente = math.fsum(
                    erro * (r[atributo] - media) / escala for erro, r in zip(erros, treino)
                ) + modelo["regularizacao"] * coeficiente
                self.assertLessEqual(abs(gradiente), 1e-8)
            self.assertLess(modelo["convergencia"]["iteracoes"], 100)
            self.assertEqual(modelo["convergencia"]["tolerancia"], 1e-8)
            self.assertEqual(modelo["convergencia"]["tolerancia_decremento"], 1e-12)

    def test_treinos_invalidos_sao_rejeitados(self):
        casos = [
            ([], [], 1), ({}, [], 1), ([{"acerto": 1}], [], 1),
            ([{"acerto": True}], ["score"], 1),
            ([{"acerto": True, "score": True}], ["score"], 1),
            ([{"acerto": True, "score": math.nan}], ["score"], 1),
            ([{"acerto": True, "score": math.inf}], ["score"], 1),
            (registros(), ["score", "score"], 1), (registros(), ["id"], 1),
            (registros(), "score", 1), (registros(), [], 0),
            (registros(), [], -1), (registros(), [], math.inf),
            (registros(), [], True),
        ]
        for dados, atributos, regularizacao in casos:
            with self.subTest(atributos=atributos, regularizacao=regularizacao):
                with self.assertRaises(ValueError):
                    ajustar(dados, atributos, regularizacao)

    def test_modelos_corrompidos_sao_rejeitados_antes_da_predicao(self):
        base = ajustar(registros(), ["score", "margem"])
        alteracoes = [
            ("schema", "v999"), ("coeficientes", [1]),
            ("coeficientes", [math.inf, 0]), ("escalas", [0, 1]),
            ("medias", [1]), ("intercepto", math.nan),
            ("n", 0), ("n", True), ("acertos", 500),
            ("regularizacao", 0), ("metodo", "outro"),
            ("pseudocontagens", {}), ("atributos", ["score", "score"]),
            ("convergencia", {**base["convergencia"], "convergiu": False}),
        ]
        for campo, valor in alteracoes:
            with self.subTest(campo=campo, valor=valor):
                modelo = {**deepcopy(base), campo: valor}
                with self.assertRaises(ValueError):
                    prever(modelo, registros()[0])
        for modelo in (None, [], {**base, "extra": 5}):
            with self.assertRaises(ValueError):
                validar_modelo(modelo)

    def test_constante_corrompida_e_rejeitada(self):
        modelo = ajustar([{"acerto": True}], [])
        modelo["intercepto"] = 0.0
        with self.assertRaises(ValueError):
            prever(modelo, {})

    def test_registro_de_predicao_invalido_e_rejeitado(self):
        modelo = ajustar(registros(), ["score"])
        for registro in (None, [], {}, {"score": "1"}, {"score": False}, {"score": math.nan}):
            with self.assertRaises(ValueError):
                prever(modelo, registro)

    def test_metricas_conhecidas_e_faixas_sem_ambiguidade_nas_bordas(self):
        resultado = metricas([0, 0.2, 0.4, 0.6, 0.8, 1], [False, False, False, True, True, True])
        self.assertEqual([f["n"] for f in resultado["faixas"]], [1, 1, 1, 1, 2])
        self.assertAlmostEqual(resultado["brier"], 0.4 / 6)
        self.assertAlmostEqual(resultado["ece"], 0.2)
        self.assertEqual(resultado["n"], 6)
        self.assertEqual(resultado["acertos"], 3)
        self.assertEqual(resultado["faixas"][-1]["probabilidade_media"], 0.9)
        self.assertTrue(resultado["faixas"][-1]["inclui_superior"])
        perfeito = metricas([0, 1], [False, True])
        self.assertEqual(perfeito["brier"], 0)
        self.assertEqual(perfeito["ece"], 0)
        self.assertTrue(0 <= perfeito["logloss"] < 1e-12)

    def test_logloss_extremo_e_finito(self):
        resultado = metricas([0, 1], [True, False])
        self.assertEqual(resultado["brier"], 1)
        self.assertEqual(resultado["ece"], 1)
        self.assertTrue(math.isfinite(resultado["logloss"]))
        self.assertGreater(resultado["logloss"], 34)

    def test_metricas_vazias_nao_inventam_estimativas(self):
        resultado = metricas([], [])
        for campo in ("taxa_acerto", "brier", "logloss", "ece", "intervalo_wilson_95"):
            self.assertIsNone(resultado[campo])
        self.assertEqual(resultado["n"], 0)
        self.assertEqual(len(resultado["faixas"]), 5)
        for faixa in resultado["faixas"]:
            self.assertEqual(faixa["n"], 0)
            self.assertIsNone(faixa["probabilidade_media"])
            self.assertIsNone(faixa["taxa_acerto"])
            self.assertIsNone(faixa["intervalo_wilson_95"])

    def test_metricas_invalidas_sao_rejeitadas(self):
        for probabilidades, alvos in [
            ([0.5], []), ([0.5], [1]), ([0.5], [None]),
            ([True], [True]), ([math.nan], [True]), ([math.inf], [True]),
            ([-0.1], [True]), ([1.1], [True]), ((0.5,), [True]), ([0.5], (True,)),
        ]:
            with self.assertRaises(ValueError):
                metricas(probabilidades, alvos)

    def test_wilson_extremos_nulo_e_referencia_numerica(self):
        self.assertIsNone(wilson(0, 0))
        zero = wilson(0, 10)
        tudo = wilson(10, 10)
        self.assertEqual(zero["inferior"], 0.0)
        self.assertEqual(tudo["superior"], 1.0)
        self.assertAlmostEqual(zero["superior"], 0.2775327998628892)
        self.assertAlmostEqual(tudo["inferior"], 1 - zero["superior"])
        referencia = wilson(8, 10)
        self.assertAlmostEqual(referencia["inferior"], 0.49016247153664183)
        self.assertAlmostEqual(referencia["superior"], 0.9433178485456247)
        self.assertGreater(wilson(80, 100)["inferior"], referencia["inferior"])
        self.assertLess(wilson(80, 100)["superior"], referencia["superior"])

    def test_wilson_rejeita_contagens_e_confiancas_invalidas(self):
        for acertos, n, confianca in [
            (-1, 1, 0.95), (2, 1, 0.95), (0, -1, 0.95), (True, 1, 0.95),
            (0, 1.0, 0.95), (0, 1, 1), (0, 1, 0), (0, 1, math.nan),
        ]:
            with self.assertRaises(ValueError):
                wilson(acertos, n, confianca)


if __name__ == "__main__":
    unittest.main()
