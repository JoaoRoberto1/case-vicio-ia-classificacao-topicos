"""Cenários sintéticos da grade M9; nenhuma questão ou rótulo do case."""

import copy
import math
import unittest

from classificacao_politica.politica import (
    ANCORA, RECEITAS_CONCORDANCIA, SCHEMA, aplicar, curvas, preparar, resumir, selecionar,
)


def predicao(i, *, probabilidade=.95, acerto=True, acordo=True, particao=None):
    return {
        "id": f"sintetico_{i:03d}", "tema_sugerido_id": "tema_sintetico",
        "particao_interna": i % 3 if particao is None else particao,
        "confianca_oof": probabilidade, "confianca": probabilidade,
        "concordancia_algoritmos": acordo,
        "acertos": {"ramo": acerto, "exato": acerto},
    }


def politica(corte=.9, acordo=False, habilitada=True):
    return {
        "schema": SCHEMA, "receita": ANCORA,
        "regra": f"confianca_p{round(corte*100)}" + ("_concordancia" if acordo else ""),
        "corte": corte, "exige_concordancia": acordo, "habilitada": habilitada,
    }


def receitas():
    return {nome: [{**predicao(i), "receita": nome} for i in range(3)]
            for nome in RECEITAS_CONCORDANCIA}


class PoliticaM9Tests(unittest.TestCase):
    def test_grade_tem_exatamente_seis_filtros_fixos(self):
        ps = [predicao(i) for i in range(3)]
        grade = curvas(ps)
        self.assertEqual([(p["corte"], p["exige_concordancia"]) for p in grade],
                         [(.8, False), (.8, True), (.9, False), (.9, True), (.95, False), (.95, True)])
        self.assertTrue(all(p["n"] == p["k"] == 3 for p in grade))
        self.assertTrue(all(p["precision"] == 1 for p in grade))

    def test_fronteira_inclusiva_e_concordancia_requerida(self):
        for corte in (.8, .9, .95):
            self.assertTrue(aplicar(predicao(0, probabilidade=corte), politica(corte)))
            self.assertFalse(aplicar(predicao(0, probabilidade=math.nextafter(corte, 0)), politica(corte)))
            self.assertTrue(aplicar(predicao(0, acordo=False), politica(corte)))
            self.assertFalse(aplicar(predicao(0, acordo=False), politica(corte, True)))

    def test_selecao_sem_minimo_de_dez_e_desempate_por_corte_maior(self):
        escolhida = selecionar([predicao(i) for i in range(3)])
        self.assertTrue(escolhida["habilitada"])
        self.assertEqual(escolhida["n"], 3)
        self.assertEqual(escolhida["corte"], .95)
        self.assertFalse(escolhida["exige_concordancia"])
        self.assertEqual(len(escolhida["diagnosticos"]), 6)

    def test_prioriza_cobertura_entre_filtros_elegiveis(self):
        ps = [predicao(i, probabilidade=.8 if i < 3 else .95) for i in range(6)]
        escolhida = selecionar(ps)
        self.assertEqual((escolhida["corte"], escolhida["n"]), (.8, 6))

    def test_desempate_prioriza_precisao_antes_de_simplicidade(self):
        ps = [predicao(i) for i in range(19)]
        ps += [predicao(19, acerto=False, acordo=False),
               predicao(20, probabilidade=.8),
               predicao(21, probabilidade=.8, acerto=False, acordo=False)]
        escolhida = selecionar(ps)
        self.assertEqual((escolhida["n"], escolhida["k"], escolhida["corte"]), (20, 20, .8))
        self.assertTrue(escolhida["exige_concordancia"])

    def test_desempate_prioriza_minimo_por_fold_antes_de_simplicidade(self):
        ps = [predicao(0, particao=0),
              predicao(1, particao=0, acordo=False),
              predicao(2, particao=0, acordo=False),
              predicao(3, particao=1, probabilidade=.8),
              predicao(4, particao=2, probabilidade=.8),
              predicao(5, particao=1, probabilidade=.8, acerto=False, acordo=False)]
        escolhida = selecionar(ps)
        self.assertEqual((escolhida["n"], escolhida["minimo_publicacoes_particao"]), (3, 1))
        self.assertTrue(escolhida["exige_concordancia"])
        self.assertEqual(escolhida["corte"], .8)

    def test_selecao_usa_oof_e_nao_confianca_final(self):
        ps = [predicao(i) for i in range(3)]
        for p in ps:
            p["confianca"] = .1
        self.assertEqual(selecionar(ps)["n"], 3)

    def test_erro_aceito_pode_inabilitar_filtro_e_concordancia_recupera(self):
        ps = [predicao(i) for i in range(3)] + [predicao(3, acerto=False, acordo=False)]
        escolhida = selecionar(ps)
        self.assertTrue(escolhida["exige_concordancia"])
        self.assertEqual((escolhida["n"], escolhida["k"]), (3, 3))

    def test_meta_95_inclusive_com_erro_e_sem_arredondamento(self):
        ps = [predicao(i, acerto=i != 0) for i in range(20)]
        self.assertEqual(selecionar(ps)["precision"], .95)
        self.assertTrue(selecionar(ps)["habilitada"])
        self.assertFalse(selecionar(ps[:-1])["habilitada"])

    def test_fallback_sem_regra_nao_publica_e_preserva_diagnosticos(self):
        escolhida = selecionar([predicao(i, acerto=False) for i in range(3)])
        self.assertFalse(escolhida["habilitada"])
        self.assertIsNone(escolhida["regra"])
        self.assertIsNone(escolhida["corte"])
        self.assertIsNone(escolhida["precision"])
        self.assertIsNone(escolhida["wilson95"])
        self.assertFalse(aplicar(predicao(0), escolhida))
        self.assertEqual(len(escolhida["diagnosticos"]), 6)

    def test_resumo_inclui_fold_sem_publicacoes(self):
        ps = [predicao(i) for i in range(3)]
        resumo = resumir(ps, [True, False, True])
        self.assertEqual((resumo["count"], resumo["n"], resumo["k"]), (3, 2, 2))
        self.assertAlmostEqual(resumo["coverage"], 2/3)
        self.assertEqual([p["n"] for p in resumo["por_particao"]], [1, 0, 1])
        self.assertEqual(resumo["minimo_publicacoes_particao"], 0)
        self.assertIsNone(resumo["por_particao"][1]["wilson95"])

    def test_resumo_sem_particao_e_vazio_nao_inventa_suporte(self):
        p = predicao(0)
        del p["particao_interna"]
        self.assertEqual(resumir([p], [True])["por_particao"], [])
        resumo = resumir([], [])
        self.assertEqual(resumo["n"], 0)
        self.assertIsNone(resumo["precision"])
        self.assertIsNone(resumo["coverage"])
        self.assertIsNone(resumo["wilson95"])

    def test_aplicacao_independe_de_alvos_textos_particoes_e_metadados(self):
        p = {"confianca": .9, "concordancia_algoritmos": True}
        esperado = aplicar(p, politica(acordo=True))
        for extras in ({"acertos": {"ramo": False}}, {"acertos": "invalido"},
                       {"texto": "ignorar", "tema_referencia_id": "outro"},
                       {"particao_interna": object(), "referencia_fora": True}):
            self.assertEqual(aplicar({**p, **extras}, politica(acordo=True)), esperado)
        self.assertTrue(esperado)

    def test_aplicacao_so_usa_campo_solicitado(self):
        p = predicao(0)
        p["confianca_oof"] = .1
        self.assertTrue(aplicar(p, politica()))
        self.assertFalse(aplicar(p, politica(), "confianca_oof"))
        with self.assertRaises(ValueError):
            aplicar(p, politica(), "acertos")

    def test_probabilidades_invalidas_rejeitadas_mesmo_desabilitada(self):
        for habilitada in (True, False):
            for valor in (None, True, "0.9", math.nan, math.inf, -math.inf, -.1, 1.1):
                with self.subTest(habilitada=habilitada, valor=valor), self.assertRaises(ValueError):
                    aplicar(predicao(0, probabilidade=valor), politica(habilitada=habilitada))
        with self.assertRaises(ValueError):
            aplicar({"concordancia_algoritmos": True}, politica(habilitada=False))

    def test_concordancia_e_indicadores_exigem_bool_exato(self):
        for valor in (None, 0, 1, "true"):
            with self.subTest(valor=valor), self.assertRaises(ValueError):
                aplicar(predicao(0, acordo=valor), politica())
            for campo in ("habilitada", "exige_concordancia"):
                p = politica()
                p[campo] = valor
                with self.subTest(campo=campo, valor=valor), self.assertRaises(ValueError):
                    aplicar(predicao(0), p)

    def test_esquema_grade_e_fallback_invalidos_rejeitados(self):
        alteracoes = [{"schema": "outro"}, {"receita": "outra"}, {"corte": .85},
                      {"corte": math.nan}, {"corte": True}, {"regra": "confianca_p95"},
                      {"regra": None}, {"regra": None, "corte": None},
                      {"regra": None, "corte": None, "habilitada": False, "exige_concordancia": True}]
        for alteracao in alteracoes:
            with self.subTest(alteracao=alteracao), self.assertRaises(ValueError):
                aplicar(predicao(0), {**politica(), **alteracao})

    def test_join_por_id_independe_da_ordem_e_nao_muta_entradas(self):
        rs = receitas()
        rs["sinais_small"].reverse()
        rs["large_rrf20"][1]["tema_sugerido_id"] = "outro_tema"
        antes = copy.deepcopy(rs)
        preparados = preparar(rs)
        self.assertEqual([p["concordancia_algoritmos"] for p in preparados], [True, False, True])
        self.assertTrue(all(p["receita"] == ANCORA for p in preparados))
        self.assertEqual(rs, antes)
        self.assertIsNot(preparados[0], rs[ANCORA][0])

    def test_join_preserva_tema_score_rotulos_e_demais_campos_da_ancora(self):
        rs = receitas()
        for indice, nome in enumerate(RECEITAS_CONCORDANCIA):
            for p in rs[nome]:
                p["score"] = .3 * indice
                p["acertos"] = {"ramo": indice == 2, "exato": indice == 2}
                p["metadado"] = {"origem": nome}
        for preparado, ancora in zip(preparar(rs), rs[ANCORA]):
            self.assertEqual({k: v for k, v in preparado.items() if k != "concordancia_algoritmos"},
                             {k: v for k, v in ancora.items() if k != "concordancia_algoritmos"})

    def test_join_nao_usa_acertos_nem_campos_da_referencia(self):
        rs = receitas()
        for nome, ps in rs.items():
            for p in ps:
                p["acertos"] = None if nome == ANCORA else "ignorar"
                p["referencia_fora"] = object()
        self.assertTrue(all(p["concordancia_algoritmos"] for p in preparar(rs)))

    def test_join_aceita_coorte_sem_particoes_e_receitas_extras_nao_participam(self):
        rs = receitas()
        for ps in rs.values():
            for p in ps:
                del p["particao_interna"]
        rs["receita_ignorada"] = None
        self.assertEqual(len(preparar(rs)), 3)

    def test_join_rejeita_ids_ausentes_duplicados_e_desconhecidos(self):
        for operacao in ("ausente", "duplicado", "outro"):
            rs = receitas()
            ps = rs["sinais_small"]
            if operacao == "ausente":
                ps.pop()
            elif operacao == "duplicado":
                ps.append(copy.deepcopy(ps[0]))
            else:
                ps[0]["id"] = "id_diferente"
            with self.subTest(operacao=operacao), self.assertRaises(ValueError):
                preparar(rs)

    def test_join_rejeita_particoes_incompativeis_e_campos_invalidos(self):
        alteracoes = [{"particao_interna": 4}, {"particao_interna": True},
                      {"particao_interna": "0"}, {"tema_sugerido_id": ""},
                      {"tema_sugerido_id": None}, {"receita": "outra"}, {"id": ""}]
        for alteracao in alteracoes:
            rs = receitas()
            rs["sinais_small"][0].update(alteracao)
            with self.subTest(alteracao=alteracao), self.assertRaises(ValueError):
                preparar(rs)
        rs = receitas()
        del rs["sinais_small"][0]["particao_interna"]
        with self.assertRaises(ValueError):
            preparar(rs)

    def test_join_requer_receitas_e_listas_nao_vazias(self):
        for rs in ({}, {nome: [] for nome in RECEITAS_CONCORDANCIA}, None):
            with self.assertRaises(ValueError):
                preparar(rs)

    def test_medicao_exige_alvos_e_decisoes_booleanos_e_mesmo_tamanho(self):
        for valor in (None, 0, 1, "true"):
            p = predicao(0)
            p["acertos"]["ramo"] = valor
            with self.assertRaises(ValueError):
                resumir([p], [True])
            with self.assertRaises(ValueError):
                resumir([predicao(0)], [valor])
        with self.assertRaises(ValueError):
            resumir([predicao(0)], [])

    def test_selecao_exige_coorte_nao_vazia_unica_e_com_particoes(self):
        with self.assertRaises(ValueError):
            selecionar([])
        p = predicao(0)
        with self.assertRaises(ValueError):
            selecionar([p, copy.deepcopy(p)])
        del p["particao_interna"]
        with self.assertRaises(ValueError):
            selecionar([p])


if __name__ == "__main__":
    unittest.main()
