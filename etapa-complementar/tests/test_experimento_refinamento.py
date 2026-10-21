"""Invariantes de seleção M6 com exemplos sintéticos, sem dados do case."""

from collections import Counter
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from classificacao_refinamento import experimento as exp


def _folds(ids):
    return [
        {"indice": n + 1, "treino_ids": sorted(set(ids) - set(ids[n::3])),
         "validacao_ids": ids[n::3]}
        for n in range(3)
    ]


def _grupos(ids):
    return [{"id": "grupo-" + i, "ids": [i]} for i in ids]


def _acerto(identificador, ramo, exato=None):
    return {"id": identificador, "acertos": {
        "ramo": ramo, "imediato": ramo, "exato": ramo if exato is None else exato}}


def _predicao(identificador, tema="a"):
    return {
        "id": identificador, "tema_sugerido_id": tema, "score": 0.7,
        "margem": 0.4, "sem_evidencia": False,
        "top_candidatos": [{"tema_id": tema, "score": 0.7},
                           {"tema_id": "b" if tema == "a" else "a", "score": 0.3}],
    }


def _fixture():
    ids = [f"sintetica-{n}" for n in range(9)]
    taxonomia = {"por_id": {
        "raiz": {"tema_id": "raiz", "status": "active", "nivel": "0",
                 "parent_id": "", "ancestrais_ids": []},
        **{i: {"tema_id": i, "status": "active", "nivel": "1",
               "parent_id": "raiz", "ancestrais_ids": ["raiz"]} for i in ("a", "b")},
    }}
    rotulos = [
        {"id": i, "tema_central_id": "a" if n % 3 == 0 else "b", "extras_ids": [],
         "fora_da_taxonomia": False, "disciplina": "Sintética"}
        for n, i in enumerate(ids)
    ]
    return {
        "questoes": [{"id": i} for i in ids], "rotulos_dev": rotulos,
        "taxonomia": taxonomia,
        "protocolo": {"desenvolvimento_ids": ids, "particoes_internas": _folds(ids)},
        "grupos": _grupos(ids),
        "config": {
            "criterio_selecao": exp.CRITERIO[:], "top_k": 5,
            "publicacao_automatica": False, "recalibrar": False,
            "promover_entrega_m5": False, "natureza": "Somente teste sintético.",
            "nested": {"particoes_internas": 3, "salt": "teste-isolamento"},
            "receitas": {
                "baseline_m3": {"prioridade": 0, "parametros": {"modo": "baseline_m3"}},
                "alternativa": {"prioridade": 1, "parametros": {"modo": "campos"}},
            },
        },
        "cache": {"questoes": {i: {} for i in ids}},
    }


def _baseline(dados):
    return [exp.avaliar_predicao(_predicao(r["id"]), r, dados["taxonomia"], set())
            for r in dados["rotulos_dev"]]


class ParticoesRefinamentoTests(unittest.TestCase):
    def setUp(self):
        self.ids = [f"q{n}" for n in range(9)]
        self.grupos = _grupos(self.ids)
        self.folds = _folds(self.ids)

    def test_cobertura_e_disjuncao_validas(self):
        exp.validar_particoes(self.folds, set(self.ids), self.grupos)

    def test_recusa_ids_repetidos_overlap_cobertura_e_indices(self):
        casos = []
        alterado = deepcopy(self.folds)
        alterado[0]["treino_ids"].append(alterado[0]["treino_ids"][0])
        casos.append(alterado)
        alterado = deepcopy(self.folds)
        alterado[0]["treino_ids"].append(alterado[0]["validacao_ids"][0])
        casos.append(alterado)
        alterado = deepcopy(self.folds)
        alterado[0]["treino_ids"].pop()
        casos.append(alterado)
        alterado = deepcopy(self.folds)
        alterado[1]["indice"] = alterado[0]["indice"]
        casos.append(alterado)
        alterado = deepcopy(self.folds)
        alterado[1] = {**deepcopy(alterado[0]), "indice": 2}
        casos.append(alterado)
        for folds in casos:
            with self.subTest(folds=folds), self.assertRaises(ValueError):
                exp.validar_particoes(folds, set(self.ids), self.grupos)

    def test_recusa_grupo_duplicado_incompleto_ou_atravessando_corte(self):
        casos = [self.grupos[:-1], self.grupos + [self.grupos[0]],
                 [{"ids": ["q0", "q1"]}] + self.grupos[2:],
                 [{"ids": ["q0", "fora-do-universo"]}] + self.grupos[1:]]
        for grupos in casos:
            with self.subTest(grupos=grupos), self.assertRaises(ValueError):
                exp.validar_particoes(self.folds, set(self.ids), grupos)

    def test_internas_deterministicas_independentes_da_ordem_e_sem_mutacao(self):
        treino = self.folds[0]["treino_ids"]
        entrada = deepcopy((treino, self.grupos))
        config = {"particoes_internas": 3, "salt": "sintetico"}
        geradas = exp.criar_internas(treino, self.grupos, 1, config)
        invertidas = exp.criar_internas(treino[::-1], self.grupos[::-1], 1, config)
        self.assertEqual(geradas, invertidas)
        self.assertEqual((treino, self.grupos), entrada)
        self.assertEqual(Counter(i for f in geradas for i in f["validacao_ids"]), Counter(treino))
        self.assertTrue(all(set(f["treino_ids"] + f["validacao_ids"]) == set(treino)
                            for f in geradas))

    def test_internas_preservam_grupos_multiplos(self):
        ids = [f"q{n}" for n in range(12)]
        grupos = [{"ids": ids[n:n + 2]} for n in range(0, 12, 2)]
        folds = exp.criar_internas(ids, grupos, 7, {"particoes_internas": 3, "salt": "s"})
        for fold in folds:
            for grupo in grupos:
                membros = set(grupo["ids"])
                self.assertIn(membros & set(fold["validacao_ids"]), (set(), membros))

    def test_internas_recusam_grupo_cortado_e_dobras_vazias(self):
        with self.assertRaises(ValueError):
            exp.criar_internas(["q0", "q1", "q2"], [{"ids": ["q0", "externa"]},
                {"ids": ["q1"]}, {"ids": ["q2"]}], 1, {"particoes_internas": 2, "salt": "s"})
        with self.assertRaises(ValueError):
            exp.criar_internas(["q0", "q1"], _grupos(["q0", "q1"]), 1,
                              {"particoes_internas": 3, "salt": "s"})


class ComparacaoRefinamentoTests(unittest.TestCase):
    def test_selecao_ordena_ramo_depois_exato_depois_prioridade(self):
        receitas = {n: {"prioridade": p} for n, p in (("a", 2), ("b", 1), ("c", 0))}
        resultados = {
            "a": [_acerto("q1", True), _acerto("q2", True, False)],
            "b": [_acerto("q1", True, False), _acerto("q2", True, False)],
            "c": [_acerto("q1", False), _acerto("q2", True)],
        }
        self.assertEqual(exp.selecionar(resultados, receitas), "a")
        resultados["b"] = deepcopy(resultados["a"])
        self.assertEqual(exp.selecionar(resultados, receitas), "b")
        receitas["a"]["prioridade"] = receitas["b"]["prioridade"]
        self.assertEqual(exp.selecionar(resultados, receitas), "a")

    def test_selecao_recusa_amostras_incomparaveis_repetidas_e_acerto_nao_booleano(self):
        receitas = {"a": {"prioridade": 0}, "b": {"prioridade": 1}}
        casos = [
            {"a": [_acerto("q", True)]},
            {"a": [_acerto("q", True)], "b": [_acerto("outro", True)]},
            {"a": [_acerto("q", True)] * 2, "b": [_acerto("q", True)]},
            {"a": [_acerto("q", 1)], "b": [_acerto("q", True)]},
        ]
        for resultados in casos:
            with self.subTest(resultados=resultados), self.assertRaises(ValueError):
                exp.selecionar(resultados, receitas)

    def test_comparacao_pareada_alinha_por_id_e_expoe_perdas(self):
        baseline = [_acerto(f"q{i}", valor) for i, valor in enumerate([False, True, True, False])]
        nova = [_acerto(f"q{i}", valor) for i, valor in enumerate([True, False, True, False])]
        resultado = exp.comparar_pareado(baseline, nova[::-1])
        esperado = {"melhorou": 1, "piorou": 1, "ambos_corretos": 1,
                    "ambos_errados": 1, "ganho_liquido": 0}
        self.assertEqual(resultado, {m: esperado for m in ("ramo", "imediato", "exato")})
        for invalida in (nova[:-1], nova + [nova[0]]):
            with self.assertRaises(ValueError):
                exp.comparar_pareado(baseline, invalida)

    def test_baseline_detecta_drift_de_score_e_ranking_mesmo_com_igual_acuracia(self):
        dados = _fixture()
        baseline = _baseline(dados)
        exp.conferir_baseline(baseline[::-1], baseline)
        for campo in ("score", "margem", "top_candidatos"):
            alterada = deepcopy(baseline)
            if campo == "top_candidatos":
                alterada[0][campo].reverse()
            else:
                alterada[0][campo] += 1e-12
            with self.subTest(campo=campo), self.assertRaises(ValueError):
                exp.conferir_baseline(alterada, baseline)


class DesenvolvimentoRefinamentoTests(unittest.TestCase):
    def _executar(self, dados):
        acessos = []

        def predizer_corte(qs, rs_treino, taxonomia, cache, treino, validacao, receitas):
            treino, validacao = set(treino), set(validacao)
            self.assertFalse(treino & validacao)
            self.assertEqual(set(rs_treino), treino)
            self.assertTrue(treino | validacao <= set(qs))
            self.assertEqual(set(cache["questoes"]), set(qs))
            acessos.append((set(qs), treino, validacao))
            return {nome: [dict(_predicao(i, "a" if nome == "baseline_m3" else "b"),
                               receita=nome) for i in sorted(validacao)] for nome in receitas}

        with patch.object(exp, "_predizer_corte", side_effect=predizer_corte):
            produtos, resumo = exp.processar_desenvolvimento(
                **dados, baseline_congelada=_baseline(dados))
        return produtos, resumo, acessos

    def test_nested_restringe_entradas_e_cobre_dev_uma_vez(self):
        dados = _fixture()
        copia = deepcopy(dados)
        produtos, resumo, acessos = self._executar(dados)
        self.assertEqual(dados, copia)
        self.assertEqual(resumo["receita_selecionada"], "alternativa")
        nested = [json.loads(linha) for linha in produtos["predicoes_nested.jsonl"].splitlines()]
        self.assertEqual(Counter(p["id"] for p in nested), Counter(dados["protocolo"]["desenvolvimento_ids"]))
        universo = set(dados["protocolo"]["desenvolvimento_ids"])
        acessos_internos = [a for a in acessos if a[0] != universo]
        self.assertEqual(len(acessos_internos), 9)
        treinos_externos = [set(f["treino_ids"]) for f in dados["protocolo"]["particoes_internas"]]
        for recebidos, treino, validacao in acessos_internos:
            self.assertIn(recebidos, treinos_externos)
            self.assertEqual(recebidos, treino | validacao)

    def test_rotulos_outer_nao_influenciam_sua_selecao_interna(self):
        dados = _fixture()
        produtos, _, _ = self._executar(dados)
        alterados = deepcopy(dados)
        teste_outer = set(dados["protocolo"]["particoes_internas"][0]["validacao_ids"])
        for rotulo in alterados["rotulos_dev"]:
            if rotulo["id"] in teste_outer:
                rotulo["tema_central_id"] = "b"
        outros, _, _ = self._executar(alterados)
        original = json.loads(produtos["metricas_desenvolvimento.json"])["nested"]["particoes"][0]
        alterado = json.loads(outros["metricas_desenvolvimento.json"])["nested"]["particoes"][0]
        self.assertEqual(original["receita"], alterado["receita"])
        self.assertEqual(original["metricas_internas"], alterado["metricas_internas"])
        self.assertNotEqual(original["validacao_externa"], alterado["validacao_externa"])

    def test_reserva_e_oficial_recusados_antes_de_qualquer_ajuste(self):
        for campo in ("questoes", "rotulos_dev", "cache"):
            dados = _fixture()
            if campo == "cache":
                dados[campo]["questoes"]["externa"] = {}
            else:
                dados[campo].append({"id": "externa"})
            with self.subTest(campo=campo), patch.object(exp, "_predizer_corte") as predizer:
                with self.assertRaises(ValueError):
                    exp.processar_desenvolvimento(**dados, baseline_congelada=[])
                predizer.assert_not_called()

    def test_recusa_ativar_publicacao_calibracao_ou_promocao(self):
        for campo in ("publicacao_automatica", "recalibrar", "promover_entrega_m5"):
            dados = _fixture()
            dados["config"][campo] = True
            with self.subTest(campo=campo), patch.object(exp, "_predizer_corte") as predizer:
                with self.assertRaises(ValueError):
                    exp.processar_desenvolvimento(**dados, baseline_congelada=[])
                predizer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
