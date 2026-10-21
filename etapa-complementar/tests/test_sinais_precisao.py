"""Contratos M8 exercitados somente com textos e temas sintéticos."""

from copy import deepcopy
import math
import unittest

from classificacao_precisao.sinais import (
    ALIASES_INSTRUMENTOS, NOMES_ATRIBUTOS, Sinais, _citacoes,
)


def preparar(especificacoes=None):
    especificacoes = especificacoes or [
        ("a", "Processo sintético alfa", "Art. 33 do CP.", ["processo sintético", "alfa singular"]),
        ("b", "Processo sintético beta", "Art. 33 do CPP.", ["processo sintético", "beta singular"]),
        ("c", "Processo sintético gama", "Descrição sem norma.", ["processo sintético", "gama singular"]),
    ]
    registros, descritores = [], []
    for i, titulo, descricao, termos in especificacoes:
        registros.append({"tema_id": i, "titulo": titulo, "descricao": descricao,
                          "status": "active", "nivel": 1})
        descritores.append({"tema_id": i, "descricao": descricao, "termos": list(termos),
                            "fontes": ["https://www.planalto.gov.br/ccivil_03/decreto-lei/del2848compilado.htm"]})
    taxonomia = {"registros": registros, "por_id": {t["tema_id"]: t for t in registros}}
    documentos = [{"registros": descritores}]
    return taxonomia, documentos


def consulta(enunciado="", comando="", alternativas=None, **extras):
    return {"id": "sintetica", "enunciado": enunciado, "comando": comando,
            "alternativas": alternativas or {}, **extras}


def ancora_sintetica(**alteracoes):
    registro = {"tema_id": "c", "instrumento": "lei:7210/1984", "artigos": ["art:1"],
                "fonte": "https://www.planalto.gov.br/ccivil_03/leis/l7210.htm",
                "ambiguo": False, "nota": "Associação sintética, sem tema real."}
    registro.update(alteracoes)
    return {"schema": "ancoras_normativas_m8_v1",
            "procedimento": "LLM_preparacao_somente_taxonomia_e_legislacao",
            "questoes_ou_rotulos_consultados": False, "registros": [registro]}


class ExtracaoNormativaPrecisaoTest(unittest.TestCase):
    def test_alias_numero_e_nome_da_mesma_norma_colapsam(self):
        normas, pares = _citacoes(["CP, Código Penal, decreto-lei nº 2.848/1940: art. 33."])
        self.assertEqual(normas, {"decreto_lei:2848/1940"})
        self.assertEqual(pares, {"decreto_lei:2848/1940|art:33"})

    def test_equivalencia_cp_cpp_lep_e_anos_omitidos_conhecidos(self):
        for numero, alias in (("DL 2848", "cp"), ("Decreto Lei 3689/41", "CPP"),
                               ("Lei 7.210, de 1984", "Lei de Execução Penal")):
            with self.subTest(numero=numero):
                self.assertEqual(_citacoes([numero])[0], _citacoes([alias])[0])

    def test_aliases_fechados_possuem_fonte_e_canonico_consistente(self):
        for canonico, aliases, fonte in ALIASES_INSTRUMENTOS:
            self.assertTrue(fonte.startswith("https://www.planalto.gov.br/"))
            for alias in aliases:
                with self.subTest(alias=alias):
                    self.assertEqual(_citacoes([alias])[0], {canonico})

    def test_nao_corrige_ano_incompativel_ou_inventa_ano_de_norma_desconhecida(self):
        self.assertEqual(_citacoes(["Lei 7210/2000"])[0], {"lei:7210/2000"})
        self.assertEqual(_citacoes(["Lei 999999"])[0], {"lei:999999"})
        self.assertEqual(_citacoes(["Lei 999999/2001"])[0], {"lei:999999/2001"})

    def test_normas_militares_e_substrings_nao_viram_codigos_comuns(self):
        normas, pares = _citacoes(["CPM CPPM XCP CPPextra Código Penal Militar, art. 1."])
        self.assertEqual(normas, set())
        self.assertEqual(pares, set())

    def test_artigos_isolados_nao_recebem_norma(self):
        self.assertEqual(_citacoes(["artigos 1, 2 e 3-A"]), (set(), set()))

    def test_par_nao_atravessa_campo_ou_segmento(self):
        for campos in (["CP", "art. 33"], ["CP; art. 33"], ["CP. Leia o art. 33"]):
            with self.subTest(campos=campos):
                self.assertEqual(_citacoes(campos)[1], set())

    def test_duas_normas_no_mesmo_segmento_nao_atribuem_artigos(self):
        normas, pares = _citacoes(["Art. 33 do CP e art. 34 do CPP"])
        self.assertEqual(len(normas), 2)
        self.assertEqual(pares, set())

    def test_codigo_nao_cadastrado_impede_atribuicao_ao_unico_conhecido(self):
        for texto in ("art. 33 do CPC comparado ao CPP", "CP e Código Penal Militar, art. 33",
                      "Código de Processo Civil e CPP, art. 33"):
            with self.subTest(texto=texto):
                self.assertEqual(_citacoes([texto])[1], set())

    def test_alias_com_ano_incompativel_nao_adota_ano_do_registro(self):
        self.assertEqual(_citacoes(["CF/1967"])[0], set())
        self.assertEqual(_citacoes(["CP de 1969"])[0], set())
        self.assertEqual(_citacoes(["CP e CF/1967, art. 33"])[1], set())

    def test_segmentos_separados_permitem_normas_diferentes_sem_cruzamento(self):
        _, pares = _citacoes(["CP, art. 33; CPP, art. 34"])
        self.assertEqual(pares, {"decreto_lei:2848/1940|art:33", "decreto_lei:3689/1941|art:34"})

    def test_artigos_com_ordinal_sufixo_e_abreviacao_nao_perdem_identidade(self):
        _, pares = _citacoes(["Art.  1º, 2º e 3º-A do CP"])
        self.assertEqual(pares, {"decreto_lei:2848/1940|art:1", "decreto_lei:2848/1940|art:2",
                                 "decreto_lei:2848/1940|art:3-A"})

    def test_intervalo_nao_inventa_artigos_intermediarios(self):
        _, pares = _citacoes(["arts. 1 a 5 do CP"])
        self.assertEqual(len(pares), 2)
        self.assertNotIn("decreto_lei:2848/1940|art:3", pares)


class SinaisPrecisaoTest(unittest.TestCase):
    def setUp(self):
        self.taxonomia, self.documentos = preparar()
        self.sinais = Sinais(self.taxonomia, self.documentos)

    def test_seis_atributos_finitos_com_limites_em_textos_extremos(self):
        for q in (consulta(), consulta("alfa " * 2000), consulta("Art. 33 do CP; CPP art. 34"),
                  consulta("processo sintético alfa", alternativas={"x": "gama"})):
            for i in ("a", "b", "c"):
                xs = self.sinais.atributos(q, i)
                self.assertEqual(len(xs), len(NOMES_ATRIBUTOS))
                self.assertEqual(len(xs), 6)
                self.assertTrue(all(math.isfinite(x) and 0 <= x <= 1 for x in xs))

    def test_ausencia_de_evidencia_e_metadados_nao_geram_sinais(self):
        q = consulta(gabarito="a", disciplina="CP", resposta="art. 33 do CP", titulo="alfa",
                     texto="processo sintético alfa", sugestao={"tema_id": "a"})
        self.assertEqual(self.sinais.atributos(q, "a"), [0.0] * 6)

    def test_norma_e_artigo_matching_explicito_e_conflito(self):
        xs = self.sinais.atributos(consulta("art. 33 do Decreto-Lei 2.848/1940"), "a")
        self.assertEqual((xs[0], xs[1], xs[5]), (1, 1, 1))
        xs = self.sinais.atributos(consulta("art. 34 do CP"), "a")
        self.assertEqual((xs[0], xs[1], xs[5]), (1, 0, 0))
        xs = self.sinais.atributos(consulta("art. 33 do CPP"), "a")
        self.assertEqual((xs[0], xs[1], xs[5]), (0, 0, 0))

    def test_norma_exclusiva_exige_mesma_norma_unica_dos_dois_lados(self):
        xs = self.sinais.atributos(consulta("CP e CPP"), "a")
        self.assertEqual(xs[0], .5)
        self.assertEqual(xs[5], 0)

    def test_citacao_na_alternativa_nao_entra_no_corpo(self):
        q = consulta("gama", alternativas={"a": "Art. 33 do CP; processo sintético alfa"})
        xs = self.sinais.atributos(q, "a")
        self.assertEqual([xs[i] for i in (0, 1, 2, 4, 5)], [0.0] * 5)
        self.assertGreater(xs[3], 0)

    def test_termo_no_corpo_e_na_alternativa_sao_features_distintas(self):
        corpo = self.sinais.atributos(consulta("alfa"), "a")
        alternativa = self.sinais.atributos(consulta(alternativas={"a": "alfa"}), "a")
        self.assertGreater(corpo[2], 0)
        self.assertEqual(corpo[3], 0)
        self.assertEqual(alternativa[2], 0)
        self.assertEqual(alternativa[3], corpo[2])

    def test_matching_acento_caixa_e_fronteira_nao_substring(self):
        xs = self.sinais.atributos(consulta("PROCESSO SINTÉTICO ALFA"), "a")
        self.assertEqual(xs, self.sinais.atributos(consulta("processo sintetico alfa"), "a"))
        self.assertEqual(xs[4], 1)
        self.assertEqual(self.sinais.atributos(consulta("alfabeto processou sinteticamente"), "a"), [0.0] * 6)

    def test_idf_do_catalogo_pesa_termo_raro_mais_que_comum(self):
        raro = self.sinais.atributos(consulta("alfa"), "a")[2]
        comum = self.sinais.atributos(consulta("processo"), "a")[2]
        self.assertGreater(raro, comum)

    def test_frase_nao_e_formada_entre_enunciado_comando_ou_alternativas(self):
        juntos = self.sinais.atributos(consulta("alfa singular"), "a")[2]
        separados = self.sinais.atributos(consulta("alfa", "singular"), "a")[2]
        self.assertGreater(juntos, separados)
        alts = self.sinais.atributos(consulta(alternativas={"a": "alfa", "b": "singular"}), "a")[3]
        self.assertEqual(alts, separados)

    def test_urls_nao_geram_evidencia_nem_artigos_no_catalogo(self):
        self.assertEqual(self.sinais.suporte_catalogo()["temas_com_instrumentos"], 2)
        q = consulta("https://exemplo.test/CP/artigo/33 processo")
        self.assertEqual(self.sinais.atributos(q, "a")[0], 0)

    def test_tema_sem_norma_nao_herda_do_caminho_ou_da_fonte(self):
        self.taxonomia["por_id"]["c"]["caminho"] = "CP > Art. 33"
        sinais = Sinais(self.taxonomia, self.documentos)
        xs = sinais.atributos(consulta("Art. 33 do CP"), "c")
        self.assertEqual((xs[0], xs[1], xs[5]), (0, 0, 0))

    def test_campos_com_tipos_incorretos_sao_ignorados_sem_stringificacao(self):
        q = consulta()
        q.update(enunciado={"vazamento": "alfa CP"}, comando=["alfa CP"], alternativas="alfa CP")
        self.assertEqual(self.sinais.atributos(q, "a"), [0.0] * 6)
        q["alternativas"] = {"alfa CP": 3}
        self.assertEqual(self.sinais.atributos(q, "a"), [0.0] * 6)

    def test_cache_por_texto_ignora_id_gabarito_e_rotulo_das_alternativas(self):
        q = consulta("alfa", alternativas={"a": "beta", "b": "gama"})
        esperado = self.sinais.atributos(q, "a")
        q.update(id="outra", gabarito="a", alternativas={"x": "gama", "y": "beta"})
        self.assertEqual(self.sinais.atributos(q, "a"), esperado)
        self.assertEqual(len(self.sinais._cache), 1)
        q["enunciado"] = "beta"
        self.assertNotEqual(self.sinais.atributos(q, "a"), esperado)

    def test_nao_muta_entradas_e_saida_nao_compartilha_memoria(self):
        antes = deepcopy((self.taxonomia, self.documentos))
        q = consulta("alfa", alternativas={"a": "beta"})
        anterior_q = deepcopy(q)
        esperado = self.sinais.atributos(q, "a")
        self.sinais.atributos(q, "a")[0] = 5
        self.assertEqual(self.sinais.atributos(q, "a"), esperado)
        self.assertEqual((self.taxonomia, self.documentos), antes)
        self.assertEqual(q, anterior_q)
        self.taxonomia["por_id"]["a"]["titulo"] = "mudança externa"
        self.documentos[0]["registros"][0]["termos"].clear()
        self.assertEqual(self.sinais.atributos(q, "a"), esperado)

    def test_ordem_de_consultas_nao_aprende_novo_idf(self):
        esperado = self.sinais.atributos(consulta("alfa"), "a")
        for palavra in ("alfa", "beta", "gama", "termo novo"):
            self.sinais.atributos(consulta((palavra + " ") * 30), "b")
        self.assertEqual(self.sinais.atributos(consulta("alfa"), "a"), esperado)

    def test_suporte_agregado_nao_expoe_ids_ou_textos(self):
        suporte = self.sinais.suporte_catalogo()
        self.assertEqual(suporte["temas"], 3)
        self.assertEqual(suporte["temas_com_instrumentos"], 2)
        self.assertEqual(suporte["temas_com_pares_artigo_instrumento"], 2)
        self.assertEqual(suporte["temas_com_unidades_distintivas"], 3)
        self.assertNotIn("a", suporte)

    def test_tema_desconhecido_e_catalogo_incompleto_sao_recusados(self):
        with self.assertRaises(ValueError):
            self.sinais.atributos(consulta(), "inexistente")
        self.documentos[0]["registros"].pop()
        with self.assertRaises(ValueError):
            Sinais(self.taxonomia, self.documentos)

    def test_ancora_preparada_agrega_norma_e_artigo_sem_alterar_idf(self):
        sinais = Sinais(self.taxonomia, self.documentos, ancora_sintetica())
        xs = sinais.atributos(consulta("art. 1 da LEP"), "c")
        self.assertEqual((xs[0], xs[1], xs[5]), (1, 1, 1))
        self.assertEqual(self.sinais._idf, sinais._idf)
        self.assertEqual(self.sinais.atributos(consulta("art. 1 da LEP"), "c")[1], 0)

    def test_ancora_ambigua_nao_vira_evidencia(self):
        sinais = Sinais(self.taxonomia, self.documentos, ancora_sintetica(ambiguo=True))
        self.assertEqual(sinais.atributos(consulta("art. 1 da LEP"), "c"), [0.0] * 6)

    def test_ancoras_nao_mutam_entradas_nem_guardam_referencias_mutaveis(self):
        ancoras = ancora_sintetica()
        antes = deepcopy(ancoras)
        sinais = Sinais(self.taxonomia, self.documentos, ancoras)
        self.assertEqual(ancoras, antes)
        esperado = sinais.atributos(consulta("art. 1 da LEP"), "c")
        ancoras["registros"][0]["artigos"].clear()
        self.assertEqual(sinais.atributos(consulta("art. 1 da LEP"), "c"), esperado)

    def test_ancora_invalida_e_fonte_inconsistente_sao_recusadas(self):
        for modificacoes in ({"tema_id": "desconhecido"}, {"instrumento": "lei:999999/2000"},
                             {"artigos": ["1"]}, {"artigos": ["art:1", "art:1"]},
                             {"artigos": ["art:01"]}, {"ambiguo": "false"},
                             {"fonte": "https://www.planalto.gov.br/ccivil_03/leis/l9099.htm"}):
            with self.subTest(modificacoes=modificacoes):
                with self.assertRaises(ValueError):
                    Sinais(self.taxonomia, self.documentos, ancora_sintetica(**modificacoes))

    def test_ancora_precisa_de_procedencia_cega_e_sem_duplicatas(self):
        ancoras = ancora_sintetica()
        for campo, valor in (("schema", "outro"), ("procedimento", "LLM_classificacao"),
                             ("questoes_ou_rotulos_consultados", True)):
            copia = deepcopy(ancoras)
            copia[campo] = valor
            with self.subTest(campo=campo), self.assertRaises(ValueError):
                Sinais(self.taxonomia, self.documentos, copia)
        ancoras["registros"].append(deepcopy(ancoras["registros"][0]))
        with self.assertRaises(ValueError):
            Sinais(self.taxonomia, self.documentos, ancoras)

    def test_duas_ancoras_legais_do_mesmo_tema_nao_criam_exclusividade(self):
        ancoras = ancora_sintetica()
        ancoras["registros"].append({"tema_id": "c", "instrumento": "decreto_lei:2848/1940",
                                    "artigos": ["art:1"], "ambiguo": False, "nota": "Sintética.",
                                    "fonte": "https://www.planalto.gov.br/ccivil_03/decreto-lei/del2848compilado.htm"})
        sinais = Sinais(self.taxonomia, self.documentos, ancoras)
        xs = sinais.atributos(consulta("art. 1 da LEP"), "c")
        self.assertEqual((xs[0], xs[1], xs[5]), (.5, .5, 0))


if __name__ == "__main__":
    unittest.main()
