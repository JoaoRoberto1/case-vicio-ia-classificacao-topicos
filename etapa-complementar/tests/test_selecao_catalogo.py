"""Cenários sintéticos de seleção e aplicação fora da amostra, sem dados reais."""

import copy
import unittest

from classificacao_catalogo.selecao import aplicar, medir, selecionar


def predicao(i, ramo, exato=None, score=None, margem=None, consenso=False):
    return {
        "id": f"sintetico_{i}", "score": float(i) if score is None else score,
        "margem": float(i) if margem is None else margem,
        "consenso": consenso,
        "acertos": {"ramo": ramo, "exato": ramo if exato is None else exato},
    }


class SelecaoCatalogoTests(unittest.TestCase):
    def test_quantil_indice_piso_inclusivo_e_selecao_max_cobertura(self):
        ps = [predicao(i, i >= 9) for i in range(20)]
        politica = selecionar({"a": ps}, ["a"])
        self.assertTrue(politica["habilitada"])
        self.assertEqual((politica["n"], politica["k"]), (11, 11))
        self.assertEqual(politica["regra"], "margem_q50")
        self.assertEqual(politica["corte"], 9.0)
        self.assertAlmostEqual(politica["probabilidade_condicional"], 11.5 / 12)
        self.assertEqual(sum(aplicar(p, politica) for p in ps), 11)

    def test_empates_no_corte_sao_incluidos(self):
        ps = [predicao(i, True, score=1.0, margem=0.0) for i in range(20)]
        politica = selecionar({"a": ps}, ["a"])
        self.assertEqual(politica["n"], 20)
        self.assertEqual(politica["regra"], "margem_q50")

    def test_consenso_e_sem_rotulos_na_aplicacao(self):
        ps = [predicao(i, i < 12, score=0.0, margem=0.0, consenso=i < 12)
              for i in range(20)]
        politica = selecionar({"a": ps}, ["a"])
        self.assertEqual(politica["regra"], "consenso")
        self.assertTrue(aplicar({"consenso": True}, politica))
        self.assertFalse(aplicar({"consenso": False}, politica))
        self.assertFalse(aplicar({}, {"habilitada": False}))

    def test_suporte_nove_nao_habilita_mesmo_com_cem_porcento(self):
        ps = [predicao(i, True, consenso=True) for i in range(9)]
        politica = selecionar({"a": ps}, ["a"])
        self.assertFalse(politica["habilitada"])
        self.assertIsNone(politica["precisao_empirica"])
        self.assertIsNone(politica["probabilidade_condicional"])
        self.assertIsNone(politica["regra"])

    def test_precisao_exatamente_noventa_e_cinco_habilita(self):
        ps = [predicao(i, i != 0, score=1.0, margem=1.0, consenso=True)
              for i in range(20)]
        politica = selecionar({"a": ps}, ["a"])
        self.assertTrue(politica["habilitada"])
        self.assertEqual(politica["precisao_empirica"], 0.95)
        self.assertLess(politica["probabilidade_condicional"], 0.95)

    def test_desempate_prioridade_e_fallback_global(self):
        ps = [predicao(i, True, score=1.0, margem=1.0) for i in range(20)]
        self.assertEqual(selecionar({"a": ps, "b": ps}, ["b", "a"])["receita"], "b")
        a = [predicao(i, i < 3, exato=False) for i in range(8)]
        b = [predicao(i, i < 3) for i in range(8)]
        politica = selecionar({"a": a, "b": b}, ["a", "b"])
        self.assertFalse(politica["habilitada"])
        self.assertEqual(politica["receita"], "b")

    def test_cobertura_tem_prioridade_sobre_precisao_empirica(self):
        a = [predicao(i, i != 0, score=1.0, margem=1.0) for i in range(20)]
        b = [predicao(i, i >= 9) for i in range(20)]
        politica = selecionar({"a": a, "b": b}, ["b", "a"])
        self.assertEqual(politica["receita"], "a")
        self.assertEqual(politica["n"], 20)

    def test_corte_nao_reajusta_com_distribuicao_externa(self):
        politica = selecionar({"a": [predicao(i, i >= 9) for i in range(20)]}, ["a"])
        antes = copy.deepcopy(politica)
        externo = [predicao(100, False), predicao(101, False)]
        resultado = medir(externo, [aplicar(p, politica) for p in externo])
        self.assertEqual(resultado["precision"], 0.0)
        self.assertEqual(resultado["coverage"], 1.0)
        self.assertEqual(politica, antes)

    def test_medidas_sem_publicadas_nao_inventam_precisao(self):
        resultado = medir([predicao(0, False)], [False])
        self.assertEqual(resultado["count"], 1)
        self.assertEqual(resultado["n"], 0)
        self.assertEqual(resultado["coverage"], 0.0)
        self.assertIsNone(resultado["precision"])
        self.assertIsNone(resultado["wilson95"])
        self.assertIsNone(medir([], [])["coverage"])

    def test_intervalo_wilson_mantem_incerteza_mesmo_sem_erros(self):
        resultado = medir([predicao(i, True) for i in range(10)], [True] * 10)
        self.assertEqual(resultado["precision"], 1.0)
        self.assertLess(resultado["wilson95"]["inferior"], 0.95)

    def test_nao_muta_resultados_ou_prioridades(self):
        resultados = {"a": [predicao(i, True) for i in range(20)]}
        antes = copy.deepcopy(resultados)
        prioridades = ["a"]
        politica = selecionar(resultados, prioridades)
        self.assertEqual(resultados, antes)
        self.assertEqual(prioridades, ["a"])
        self.assertEqual(len(politica["diagnosticos"]), 9)
        self.assertFalse(any("id" in d for d in politica["diagnosticos"]))

    def test_recusa_cobertura_divergente_duplicatas_e_alvos_invalidos(self):
        a = [predicao(i, True) for i in range(10)]
        with self.assertRaises(ValueError):
            selecionar({"a": a, "b": a[:-1]}, ["a", "b"])
        with self.assertRaises(ValueError):
            selecionar({"a": a + [a[0]]}, ["a"])
        invalido = copy.deepcopy(a)
        invalido[0]["acertos"]["ramo"] = 1
        with self.assertRaises(ValueError):
            selecionar({"a": invalido}, ["a"])

    def test_recusa_prioridades_e_numeros_invalidos(self):
        a = [predicao(i, True) for i in range(10)]
        for prioridades in [[], ["a", "a"], ["b"]]:
            with self.subTest(prioridades=prioridades), self.assertRaises(ValueError):
                selecionar({"a": a}, prioridades)
        for valor in [True, float("nan"), float("inf"), "1"]:
            invalido = copy.deepcopy(a)
            invalido[0]["score"] = valor
            with self.subTest(valor=valor), self.assertRaises(ValueError):
                selecionar({"a": invalido}, ["a"])
        with self.assertRaises(ValueError):
            aplicar({"score": 1.0}, {"habilitada": True, "regra": "desconhecida"})
        with self.assertRaises(ValueError):
            medir(a, [1] * len(a))


if __name__ == "__main__":
    unittest.main()
