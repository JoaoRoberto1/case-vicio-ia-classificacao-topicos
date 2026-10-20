"""Exemplos sintéticos de notação; não usam rótulos ou conteúdo das questões."""

import unittest

from classificacao_local.citacoes import extrair_citacoes


class CitacoesTests(unittest.TestCase):
    def test_normaliza_numero_pontuacao_e_ano(self):
        for texto in (
            "Lei nº 9.099/95",
            "lei n. 9099/1995",
            "LEI N° 9.099/1995",
            "Lei número 9.099, de 1995",
            "Lei 9.099, de 26 de setembro de 1995",
        ):
            with self.subTest(texto=texto):
                self.assertEqual(
                    extrair_citacoes(texto),
                    {"instrumentos": ["lei:9099/1995"],
                     "artigos": [], "pares": []},
                )

    def test_tipos_numericos_nao_colidem(self):
        resultado = extrair_citacoes(
            "Lei 123/2006; Lei Complementar nº 123/2006; "
            "Decreto-Lei n.º 123/2006; Decreto–Lei 123/2006."
        )
        self.assertEqual(
            resultado["instrumentos"],
            ["decreto_lei:123/2006", "lei:123/2006",
             "lei_complementar:123/2006"],
        )

    def test_corte_de_seculo_e_fixo_e_explicito(self):
        resultado = extrair_citacoes(
            "Lei 100/29, Lei 101/30, Lei 102/00, Lei 103/99."
        )
        self.assertEqual(
            resultado["instrumentos"],
            ["lei:100/2029", "lei:101/1930",
             "lei:102/2000", "lei:103/1999"],
        )

    def test_ano_da_fonte_nao_completa_ano_da_lei(self):
        resultado = extrair_citacoes(
            "Fonte publicada em 2026. Lei nº 8.000. Revisão do texto: 2025."
        )
        self.assertEqual(resultado["instrumentos"], ["lei:8000"])
        self.assertEqual(extrair_citacoes("Fonte: relatório de 2026.")["instrumentos"], [])

    def test_aliases_deduplicados_e_acentos(self):
        resultado = extrair_citacoes(
            "Código Penal (CP); codigo de processo penal (CPP); "
            "Constituição Federal (CF/88); Lei de Execução Penal (LEP)."
        )
        self.assertEqual(
            resultado["instrumentos"],
            ["codigo:penal", "codigo:processo_penal",
             "constituicao:federal", "lei_nome:execucao_penal"],
        )

    def test_siglas_exigem_fronteiras_e_maiusculas(self):
        resultado = extrair_citacoes(
            "ABCPC; XCPP; CFake; LEPTO; cp; cpp; cf; lep; CP_RASCUNHO"
        )
        self.assertEqual(resultado["instrumentos"], [])
        self.assertEqual(
            extrair_citacoes("(CP), [CPP], CF/1988 e LEP")["instrumentos"],
            ["codigo:penal", "codigo:processo_penal",
             "constituicao:federal", "lei_nome:execucao_penal"],
        )

    def test_numero_de_norma_nao_inventa_nome_do_codigo(self):
        resultado = extrair_citacoes("Decreto-Lei 2.848/40")
        self.assertEqual(resultado["instrumentos"], ["decreto_lei:2848/1940"])

    def test_artigos_ordinais_sufixos_e_listas(self):
        resultado = extrair_citacoes(
            "Arts. 5º, 6° e 7-A. Artigo 8B; artigo 008-b. art.9º-A."
        )
        self.assertEqual(
            resultado["artigos"],
            ["art:5", "art:6", "art:7-A", "art:8-B", "art:9-A"],
        )

    def test_intervalos_conservam_somente_extremos(self):
        resultado = extrair_citacoes("Artigos 10 a 15; arts. 20–24.")
        self.assertEqual(
            resultado["artigos"], ["art:10", "art:15", "art:20", "art:24"]
        )
        self.assertNotIn("art:12", resultado["artigos"])

    def test_nao_extrai_paragrafos_incisos_anos_ou_palavras_parecidas(self):
        resultado = extrair_citacoes(
            "artístico 25; arte 26; articular 27; § 4º, inciso II; ano 2020."
        )
        self.assertEqual(resultado, {"instrumentos": [], "artigos": [], "pares": []})

    def test_um_instrumento_gera_pares_deterministicos(self):
        resultado = extrair_citacoes(
            "Lei nº 8.000/2020: arts. 2 e 1. Lei 8000/20, art. 2."
        )
        self.assertEqual(
            resultado["pares"],
            ["lei:8000/2020|art:1", "lei:8000/2020|art:2"],
        )
        self.assertEqual(resultado, extrair_citacoes(
            "Lei nº 8.000/2020: arts. 2 e 1. Lei 8000/20, art. 2."
        ))

    def test_multiplos_instrumentos_nao_recebem_pares(self):
        resultado = extrair_citacoes(
            "Lei 8.000/2020, art. 3; Lei 9.000/2021, art. 4."
        )
        self.assertEqual(resultado["artigos"], ["art:3", "art:4"])
        self.assertEqual(resultado["pares"], [])

    def test_alias_deduplicado_ainda_permite_par(self):
        resultado = extrair_citacoes("Código Penal (CP): art. 2.")
        self.assertEqual(resultado["pares"], ["codigo:penal|art:2"])

    def test_numero_e_nome_nao_sao_fundidos_por_conhecimento_juridico(self):
        resultado = extrair_citacoes(
            "Decreto-Lei 2.848/1940, Código Penal, art. 2."
        )
        self.assertEqual(len(resultado["instrumentos"]), 2)
        self.assertEqual(resultado["pares"], [])

    def test_sem_instrumento_nao_produz_par(self):
        resultado = extrair_citacoes("Art. 12.")
        self.assertEqual(resultado["artigos"], ["art:12"])
        self.assertEqual(resultado["pares"], [])

    def test_texto_vazio_e_tipo_invalido(self):
        self.assertEqual(
            extrair_citacoes(""), {"instrumentos": [], "artigos": [], "pares": []}
        )
        with self.assertRaises(TypeError):
            extrair_citacoes(None)


if __name__ == "__main__":
    unittest.main()
