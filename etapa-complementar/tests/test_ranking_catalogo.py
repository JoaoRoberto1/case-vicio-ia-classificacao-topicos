"""Testes sintéticos de aprendizado, isolamento e estabilidade do ranker M7."""

import copy
import json
import math
import unittest

from classificacao_catalogo.ranking import ajustar, pontuar


def candidato(atributos, positivo):
    return {"atributos": atributos, "positivo": positivo}


class RankingCatalogoTests(unittest.TestCase):
    def setUp(self):
        self.treino = [
            [candidato([2.0, 1.0], True), candidato([0.0, 1.0], False)],
            [candidato([3.0, 1.0], True), candidato([-1.0, 1.0], False)],
        ]

    def test_aprende_diferenca_e_preserva_constante(self):
        modelo = ajustar(self.treino, 2)
        self.assertGreater(pontuar(modelo, [1.5, 1.0]), pontuar(modelo, [0.5, 1.0]))
        self.assertGreater(modelo["pesos"][0], 0)
        self.assertEqual(modelo["pesos"][1], 0)
        self.assertEqual(modelo["escalas"][1], 1.0)
        self.assertLess(modelo["diagnostico"]["objetivo_final"],
                        modelo["diagnostico"]["objetivo_inicial"])

    def test_deterministico_sem_mutar_treino(self):
        antes = copy.deepcopy(self.treino)
        primeiro = ajustar(self.treino, 2)
        segundo = ajustar(self.treino, 2)
        self.assertEqual(primeiro, segundo)
        self.assertEqual(antes, self.treino)
        self.assertEqual(json.loads(json.dumps(primeiro)), primeiro)

    def test_alvos_nao_entram_na_normalizacao(self):
        invertido = copy.deepcopy(self.treino)
        for questao in invertido:
            for c in questao:
                c["positivo"] = not c["positivo"]
        a, b = ajustar(self.treino, 2), ajustar(invertido, 2)
        self.assertEqual(a["centros"], b["centros"])
        self.assertEqual(a["escalas"], b["escalas"])
        for pa, pb in zip(a["pesos"], b["pesos"]):
            self.assertAlmostEqual(pa, -pb)

    def test_consulta_nao_altera_modelo(self):
        modelo = ajustar(self.treino, 2)
        antes = copy.deepcopy(modelo)
        self.assertTrue(math.isfinite(pontuar(modelo, [500.0, 900.0])))
        self.assertEqual(antes, modelo)

    def test_peso_igual_por_questao_independe_quantidade_pares(self):
        a = [candidato([1.0], True), candidato([-1.0], False)]
        b = [candidato([1.0], False), candidato([-1.0], True)]
        simples = ajustar([a, b], 1)
        repetido = ajustar([a * 4, b], 1)
        self.assertEqual(simples["pesos"], [0.0])
        self.assertEqual(repetido["pesos"], [0.0])
        self.assertEqual(repetido["diagnostico"]["pares"], 17)

    def test_limita_pares_e_ignora_questoes_sem_par_na_perda(self):
        grande = [candidato([float(i)], True) for i in range(8)]
        grande += [candidato([float(-i)], False) for i in range(30)]
        modelo = ajustar([grande, [candidato([100.0], True)]], 1)
        self.assertEqual(modelo["diagnostico"]["pares"], 100)
        self.assertEqual(modelo["diagnostico"]["questoes_com_pares"], 1)
        self.assertEqual(modelo["diagnostico"]["questoes_sem_pares"], 1)
        self.assertAlmostEqual(modelo["centros"][0], (sum(range(8))-sum(range(30))+100)/39)

    def test_transformacao_afim_positiva_preserva_escores(self):
        alterado = [[candidato([c["atributos"][0] * 7 + 19, 8], c["positivo"])
                     for c in q] for q in self.treino]
        a, b = ajustar(self.treino, 2), ajustar(alterado, 2)
        self.assertAlmostEqual(pontuar(a, [1.7, 1.0]), pontuar(b, [1.7 * 7 + 19, 8]))

    def test_recusa_treino_sem_pares(self):
        for treino in [[], [[]], [[candidato([1.0], True)]]]:
            with self.subTest(treino=treino), self.assertRaises(ValueError):
                ajustar(treino, 1)

    def test_recusa_dimensoes_alvos_e_numeros_invalidos(self):
        for dimensao in [0, -1, True, 1.0]:
            with self.subTest(dimensao=dimensao), self.assertRaises(ValueError):
                ajustar(self.treino, dimensao)
        for valor in [True, None, "1", float("inf"), float("nan")]:
            treino = [[candidato([valor], True), candidato([0], False)]]
            with self.subTest(valor=valor), self.assertRaises(ValueError):
                ajustar(treino, 1)
        with self.assertRaises(ValueError):
            ajustar([[candidato([1], 1), candidato([0], False)]], 1)
        with self.assertRaises(ValueError):
            ajustar(self.treino, 1)

    def test_recusa_modelo_ou_consulta_invalidos(self):
        modelo = ajustar(self.treino, 2)
        for atributos in [[1], [1, float("nan")], [1, True]]:
            with self.subTest(atributos=atributos), self.assertRaises(ValueError):
                pontuar(modelo, atributos)
        for campo, valor in [("schema", "outro"), ("dimensoes", True),
                             ("escalas", [0.0, 1.0]), ("pesos", [float("inf"), 0.0])]:
            modificado = {**modelo, campo: valor}
            with self.subTest(campo=campo), self.assertRaises(ValueError):
                pontuar(modificado, [1.0, 1.0])


if __name__ == "__main__":
    unittest.main()
