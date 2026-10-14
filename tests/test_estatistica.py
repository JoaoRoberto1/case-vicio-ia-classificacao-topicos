"""Casos analíticos e cobertura exata, sem dados ou recibos do classificador."""

from fractions import Fraction
import json
from math import comb
import unittest

from classificacao_topicos.estatistica import (
    estimar_precisao,
    intervalo_erros_hipergeometrico,
)


class IntervaloHipergeometricoTests(unittest.TestCase):
    def test_limites_analiticos_e_caudas_inclusivas(self):
        # C(10,5)=252. Com k=0: K=3 dá 21/252; K=4 dá 6/252 < 1/40.
        self.assertEqual(intervalo_erros_hipergeometrico(10, 5, 0), (0, 3))
        self.assertEqual(intervalo_erros_hipergeometrico(10, 5, 5), (7, 10))
        self.assertEqual(intervalo_erros_hipergeometrico(10, 5, 1), (1, 5))
        self.assertEqual(intervalo_erros_hipergeometrico(10, 5, 2), (2, 7))

    def test_igualdade_exata_com_nivel_decimal_nao_sofre_erro_binario(self):
        # P(X=0 | K=1,N=40,n=39)=1/40: a igualdade é aceita.
        self.assertEqual(intervalo_erros_hipergeometrico(40, 39, 0, 0.95), (0, 1))
        self.assertEqual(intervalo_erros_hipergeometrico(40, 39, 0, Fraction(19, 20)), (0, 1))
        # Em N=41 a cauda 1/41 fica estritamente abaixo de 1/40.
        self.assertEqual(intervalo_erros_hipergeometrico(41, 40, 0), (0, 0))

    def test_censo_sem_amostra_e_populacao_vazia(self):
        self.assertEqual(intervalo_erros_hipergeometrico(0, 0, 0), (0, 0))
        self.assertEqual(intervalo_erros_hipergeometrico(10, 0, 0), (0, 10))
        for k in range(11):
            self.assertEqual(intervalo_erros_hipergeometrico(10, 10, k), (k, k))

    def test_cobertura_exaustiva_em_populacoes_pequenas(self):
        nivel = Fraction(19, 20)
        for N in range(1, 13):
            for n in range(N + 1):
                intervalos = [intervalo_erros_hipergeometrico(N, n, k, nivel) for k in range(n + 1)]
                for K in range(N + 1):
                    numerador = 0
                    for k in range(max(0, n - (N - K)), min(n, K) + 1):
                        inferior, superior = intervalos[k]
                        if inferior <= K <= superior:
                            numerador += comb(K, k) * comb(N - K, n - k)
                    cobertura = Fraction(numerador, comb(N, n))
                    with self.subTest(N=N, n=n, K=K):
                        self.assertGreaterEqual(cobertura, nivel)

    def test_simetria_e_monotonicidade_em_k(self):
        for N in range(1, 13):
            for n in range(N + 1):
                intervalos = [intervalo_erros_hipergeometrico(N, n, k) for k in range(n + 1)]
                for k, (inferior, superior) in enumerate(intervalos):
                    with self.subTest(N=N, n=n, k=k):
                        self.assertEqual(intervalos[n - k], (N - superior, N - inferior))
                        self.assertGreaterEqual(inferior, k)
                        self.assertLessEqual(superior, N - n + k)
                        if k:
                            self.assertGreaterEqual(inferior, intervalos[k - 1][0])
                            self.assertGreaterEqual(superior, intervalos[k - 1][1])

    def test_confianca_maior_nao_estreita_intervalo(self):
        for k in range(11):
            estreito = intervalo_erros_hipergeometrico(30, 10, k, 0.8)
            amplo = intervalo_erros_hipergeometrico(30, 10, k, 0.99)
            self.assertLessEqual(amplo[0], estreito[0])
            self.assertGreaterEqual(amplo[1], estreito[1])

    def test_rejeita_contagens_e_niveis_invalidos(self):
        for argumentos in ((True, 0, 0), (10, False, 0), (10, 1, True),
                           (-1, 0, 0), (10, -1, 0), (10, 2, -1),
                           (10.0, 2, 0), (10, 11, 0), (10, 2, 3)):
            with self.subTest(argumentos=argumentos), self.assertRaises(ValueError):
                intervalo_erros_hipergeometrico(*argumentos)
        for nivel in (True, False, 0, 1, -0.1, 1.1, float("nan"), float("inf"), "0.95", None):
            with self.subTest(nivel=nivel), self.assertRaises(ValueError):
                intervalo_erros_hipergeometrico(10, 5, 0, nivel)


class EstimarPrecisaoTests(unittest.TestCase):
    def test_ponto_pondera_populacoes_e_nao_quantidades_revisadas(self):
        resultado = estimar_precisao(10, 0, 0, 90, 10, 1, 0)
        cenario = resultado["cenarios"]["conservador"]
        self.assertEqual(cenario["ponto"], 0.91)
        self.assertEqual(cenario["ponto_exato"], "91/100")
        self.assertNotEqual(cenario["ponto"], 19 / 20)
        self.assertEqual(resultado["status"], "estimativa_amostral")
        self.assertEqual(resultado["total_publicadas"], 100)

    def test_transformacao_do_intervalo_adiciona_censo_sem_extrapola_lo(self):
        resultado = estimar_precisao(10, 1, 0, 10, 5, 0, 0)
        for cenario in resultado["cenarios"].values():
            self.assertEqual(cenario["intervalo_erros_restante"], [0, 3])
            self.assertEqual(cenario["ponto"], 0.95)
            self.assertEqual(cenario["intervalo"], [0.8, 0.95])
            self.assertEqual(cenario["intervalo_exato"], ["4/5", "19/20"])

    def test_inconclusivos_ficam_no_denominador_dos_dois_cenarios(self):
        resultado = estimar_precisao(10, 1, 2, 10, 5, 0, 1)
        conservador, otimista = (resultado["cenarios"][nome] for nome in ("conservador", "otimista"))
        self.assertEqual((conservador["erros_D"], conservador["erros_amostra"]), (3, 1))
        self.assertEqual(conservador["ponto"], 0.75)
        self.assertEqual(conservador["intervalo"], [0.6, 0.8])
        self.assertEqual((otimista["erros_D"], otimista["erros_amostra"]), (1, 0))
        self.assertEqual(otimista["ponto"], 0.95)
        self.assertEqual(otimista["intervalo"], [0.8, 0.95])
        self.assertEqual(resultado["contagens"]["n"], 5)

    def test_censo_total_tem_intervalos_degenerados_condicionais(self):
        resultado = estimar_precisao(10, 1, 2, 10, 10, 2, 1)
        self.assertEqual(resultado["status"], "censo")
        self.assertEqual(resultado["cenarios"]["conservador"]["intervalo"], [0.7, 0.7])
        self.assertEqual(resultado["cenarios"]["otimista"]["intervalo"], [0.85, 0.85])
        self.assertTrue(resultado["intervalos_condicionais_referencia"])
        self.assertFalse(resultado["inclui_incerteza_referencia"])

    def test_estrato_restante_vazio_usa_somente_censo_D(self):
        resultado = estimar_precisao(10, 1, 2, 0, 0, 0, 0)
        self.assertEqual(resultado["status"], "censo")
        self.assertEqual(resultado["cenarios"]["conservador"]["ponto"], 0.7)
        self.assertEqual(resultado["cenarios"]["conservador"]["intervalo"], [0.7, 0.7])
        self.assertEqual(resultado["cenarios"]["otimista"]["ponto"], 0.9)

    def test_sem_amostra_nao_inventa_ponto_e_preserva_informacao_de_D(self):
        resultado = estimar_precisao(10, 1, 2, 10, 0, 0, 0)
        self.assertEqual(resultado["status"], "sem_amostra_restante")
        self.assertEqual(resultado["cenarios"]["conservador"]["intervalo"], [0.35, 0.85])
        self.assertEqual(resultado["cenarios"]["otimista"]["intervalo"], [0.45, 0.95])
        for cenario in resultado["cenarios"].values():
            self.assertIsNone(cenario["ponto"])
            self.assertIsNone(cenario["ponto_exato"])
            self.assertEqual(cenario["intervalo_erros_restante"], [0, 10])
        sem_censo = estimar_precisao(0, 0, 0, 10, 0, 0, 0)
        self.assertEqual(sem_censo["cenarios"]["conservador"]["intervalo"], [0.0, 1.0])

    def test_sem_publicadas_precisao_indefinida_e_json_serializavel(self):
        resultado = estimar_precisao(0, 0, 0, 0, 0, 0, 0)
        self.assertEqual(resultado["status"], "sem_publicadas")
        for cenario in resultado["cenarios"].values():
            for campo in ("ponto", "ponto_exato", "intervalo", "intervalo_exato"):
                self.assertIsNone(cenario[campo])
        json.dumps(resultado, allow_nan=False)

    def test_limites_nao_sao_arredondados_ao_limiar(self):
        resultado = estimar_precisao(359, 18, 0, 0, 0, 0, 0)
        cenario = resultado["cenarios"]["conservador"]
        self.assertEqual(cenario["ponto_exato"], "341/359")
        self.assertLess(cenario["ponto"], 0.95)
        self.assertLess(cenario["intervalo"][0], 0.95)

    def test_valida_todas_contagens_e_somas(self):
        validos = [10, 1, 0, 10, 5, 1, 0]
        for indice in range(len(validos)):
            for invalido in (True, False, -1, 0.5, "1", None):
                argumentos = validos.copy()
                argumentos[indice] = invalido
                with self.subTest(indice=indice, invalido=invalido), self.assertRaises(ValueError):
                    estimar_precisao(*argumentos)
        for argumentos in ((10, 8, 3, 10, 5, 0, 0), (10, 0, 0, 10, 5, 4, 2),
                           (10, 0, 0, 10, 11, 0, 0), (0, 1, 0, 10, 5, 0, 0)):
            with self.subTest(argumentos=argumentos), self.assertRaises(ValueError):
                estimar_precisao(*argumentos)
        with self.assertRaises(ValueError):
            estimar_precisao(0, 0, 0, 0, 0, 0, 0, nivel=1)


if __name__ == "__main__":
    unittest.main()
