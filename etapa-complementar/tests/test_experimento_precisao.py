"""Isolamento dos estágios M8 com fixtures exclusivamente sintéticas.

Excluir uma partição do calibrador interno não torna independentes os rankers
que geraram seus atributos. A independência avaliada aqui é a do bloco externo
inteiro, excluído do treino dos rankers, da seleção e da confiança.
"""

from copy import deepcopy
import builtins
import json
import math
import socket
import unittest
from unittest.mock import patch

from classificacao_precisao import experimento as exp
from classificacao_precisao.confianca import ajustar, prever, aplicar
from classificacao_precisao.motor import Motor
from tests.test_motor_catalogo import caches, questao, taxonomia
from tests.test_sinais_precisao import ancora_sintetica


def dados(n=6):
    qs = {f"q{i}": questao(f"q{i}", f"Texto sintético alfa com marcador exclusivo {i}")
          for i in range(n)}
    rs = {i: {"id": i, "tema_central_id": "11" if j % 2 else "21", "extras_ids": [],
              "fora_da_taxonomia": False, "disciplina": "Sintética"}
          for j, i in enumerate(qs)}
    return qs, rs


def folds(ids):
    ids = sorted(ids)
    return [{"indice": j, "treino_ids": [i for k, i in enumerate(ids) if k % 3 != j],
             "validacao_ids": [i for k, i in enumerate(ids) if k % 3 == j]}
            for j in range(3)]


class MotorEspiao:
    """Espião de fronteiras, sem mecanismo de classificação externo."""
    def __init__(self):
        self.taxonomia = taxonomia()
        self.ajustes, self.predicoes = [], []

    def treinar(self, qs, rs, receitas):
        self.ajustes.append({"questoes": deepcopy(qs), "rotulos": deepcopy(rs), "receitas": list(receitas)})
        return {"treino_ids": [q["id"] for q in qs], "receitas": list(receitas)}

    def predizer(self, q, modelo, receita):
        if q["id"] in modelo["treino_ids"]:
            raise AssertionError("O espião recebeu ressubstituição.")
        self.predicoes.append((q["id"], deepcopy(modelo), receita))
        k = int(q["id"][1:])
        score = .51 + .01 * (k % 10)
        return {"id": q["id"], "receita": receita, "tema_sugerido_id": "11",
                "score": score, "margem": .02, "consenso": True, "sem_evidencia": False,
                "nivel_sugerido": 2, "recuou_na_hierarquia": False, "evidencia_especifica": .5,
                "atributos_confianca": [score, .02, .3, .6, 1., .5, .6, .01, .02],
                "top_candidatos": [{"tema_id": "11", "score": score},
                                   {"tema_id": "21", "score": score - .02}]}


class CortesExperimentoPrecisaoTests(unittest.TestCase):
    def setUp(self):
        self.qs, self.rs = dados()
        self.motor = MotorEspiao()
        self.folds = folds(self.qs)
        self.receitas = ["baseline_m7", "sinais_small"]

    def test_corte_envia_apenas_questoes_e_rotulos_do_treino_ordenados(self):
        treino, validacao = ["q3", "q1"], ["q5", "q0"]
        ps, modelo = exp._corte(self.motor, self.qs, {i: self.rs[i] for i in treino},
                                treino, validacao, self.receitas)
        ajuste = self.motor.ajustes[0]
        self.assertEqual([q["id"] for q in ajuste["questoes"]], ["q1", "q3"])
        self.assertEqual([r["id"] for r in ajuste["rotulos"]], ["q1", "q3"])
        self.assertEqual(modelo["treino_ids"], ["q1", "q3"])
        for receita in self.receitas:
            self.assertEqual([p["id"] for p in ps[receita]], ["q0", "q5"])
        self.assertEqual(len(self.motor.ajustes), 1)

    def test_corte_recusa_rotulo_externo_antes_do_ajuste(self):
        with self.assertRaisesRegex(ValueError, "rótulo de avaliação"):
            exp._corte(self.motor, self.qs, self.rs, ["q0", "q1"], ["q2"], self.receitas)
        self.assertEqual(self.motor.ajustes, [])

    def test_corte_recusa_rotulo_de_treino_ausente_antes_do_ajuste(self):
        with self.assertRaises(ValueError):
            exp._corte(self.motor, self.qs, {"q0": self.rs["q0"]}, ["q0", "q1"], ["q2"], self.receitas)
        self.assertEqual(self.motor.ajustes, [])

    def test_corte_recusa_sobreposicao_antes_do_ajuste(self):
        with self.assertRaises(ValueError):
            exp._corte(self.motor, self.qs, {"q0": self.rs["q0"]}, ["q0"], ["q0"], self.receitas)
        self.assertEqual(self.motor.ajustes, [])

    def test_oof_cobre_cada_id_uma_vez_sem_labels_da_validacao_no_ranker(self):
        saida = exp._oof(self.motor, self.qs, self.rs, self.folds, self.receitas)
        for fold, ajuste in zip(self.folds, self.motor.ajustes):
            treino = {r["id"] for r in ajuste["rotulos"]}
            self.assertEqual(treino, set(fold["treino_ids"]))
            self.assertFalse(treino & set(fold["validacao_ids"]))
        for receita, ps in saida.items():
            self.assertEqual([p["id"] for p in ps], sorted(self.qs))
            self.assertTrue(all(p["receita"] == receita for p in ps))
            self.assertTrue(all(math.isfinite(p["confianca_oof"]) and 0 <= p["confianca_oof"] <= 1 for p in ps))

    def test_confianca_interna_exclui_particao_inteira_e_nao_mistura_receitas(self):
        chamadas = []
        def ajustar_espiado(ps):
            modelo = {"ids": {p["id"] for p in ps},
                      "particoes": {p["particao_interna"] for p in ps},
                      "receitas": {p["receita"] for p in ps}}
            chamadas.append(modelo)
            return modelo
        def prever_espiado(modelo, p):
            self.assertNotIn(p["id"], modelo["ids"])
            self.assertNotIn(p["particao_interna"], modelo["particoes"])
            self.assertEqual(modelo["receitas"], {p["receita"]})
            return .6
        with patch.object(exp, "ajustar", side_effect=ajustar_espiado), \
             patch.object(exp, "prever", side_effect=prever_espiado):
            saida = exp._oof(self.motor, self.qs, self.rs, self.folds, self.receitas)
        self.assertEqual(len(chamadas), len(self.folds) * len(self.receitas))
        self.assertTrue(all(p["confianca_oof"] == .6 for ps in saida.values() for p in ps))

    def test_oof_recusa_fold_com_sobreposicao(self):
        malformado = deepcopy(self.folds)
        malformado[0]["treino_ids"].append(malformado[0]["validacao_ids"][0])
        with self.assertRaises(ValueError):
            exp._oof(self.motor, self.qs, self.rs, malformado, self.receitas)
        self.assertEqual(self.motor.ajustes, [])

    def test_validacao_de_folds_rejeita_repeticao_e_grupos_cruzados(self):
        grupos = [{"ids": [i]} for i in self.qs]
        exp.validar_particoes(self.folds, set(self.qs), grupos)
        repetido = deepcopy(self.folds)
        repetido.append(deepcopy(repetido[0]))
        with self.assertRaises(ValueError):
            exp.validar_particoes(repetido, set(self.qs), grupos)
        grupos = [{"ids": ["q0", "q1"]}] + [{"ids": [i]} for i in self.qs if i not in {"q0", "q1"}]
        with self.assertRaises(ValueError):
            exp.validar_particoes(self.folds, set(self.qs), grupos)

    def test_internas_permanecem_dentro_do_treino_externo(self):
        qs, _ = dados(12)
        treino = sorted(qs)[:9]
        grupos = [{"ids": [i]} for i in qs]
        internas = exp.criar_internas(treino, grupos, 7, {"particoes_internas": 3, "salt": "sintetico"})
        exp.validar_particoes(internas, set(treino), grupos)
        for fold in internas:
            self.assertEqual(set(fold["treino_ids"]) | set(fold["validacao_ids"]), set(treino))
            self.assertFalse((set(qs) - set(treino)) & (set(fold["treino_ids"]) | set(fold["validacao_ids"])))

    def test_oof_nao_muta_inputs(self):
        antes = deepcopy((self.qs, self.rs, self.folds, self.receitas))
        exp._oof(self.motor, self.qs, self.rs, self.folds, self.receitas)
        self.assertEqual((self.qs, self.rs, self.folds, self.receitas), antes)

    def test_pipeline_numerico_nao_importa_encoder_ou_abre_rede(self):
        importar = builtins.__import__
        def bloqueio(nome, *args, **kwargs):
            if nome.split(".")[0] in {"onnxruntime", "tokenizers", "torch", "transformers",
                                       "sentence_transformers", "google", "openai", "requests", "httpx"}:
                raise AssertionError("Dependência de modelo ou API acionada na classificação.")
            return importar(nome, *args, **kwargs)
        with patch("builtins.__import__", side_effect=bloqueio), \
             patch.object(socket, "socket", side_effect=AssertionError("Rede acionada.")):
            ps = exp._oof(self.motor, self.qs, self.rs, self.folds, self.receitas)
        self.assertEqual(len(ps["baseline_m7"]), len(self.qs))


class IntegracaoExternaPrecisaoTests(unittest.TestCase):
    def test_rotulos_externos_nao_afetam_treino_selecao_ou_confianca_externa(self):
        qs, rs = dados(9)
        treino, externa = sorted(qs)[:6], sorted(qs)[6:]
        internas = folds(treino)
        def executar(rotulos):
            motor = MotorEspiao()
            rs_treino = {i: rotulos[i] for i in treino}
            ps = exp._oof(motor, {i: qs[i] for i in treino}, rs_treino, internas, ["sinais_small"])
            politica = exp.selecionar(ps, ["sinais_small"])
            calibrador = ajustar(ps[politica["receita"]])
            teste, modelo = exp._corte(motor, qs, rs_treino, treino, externa, [politica["receita"]])
            externos = [{**p, "confianca": prever(calibrador, p)} for p in teste[politica["receita"]]]
            for ajuste in motor.ajustes:
                self.assertFalse({r["id"] for r in ajuste["rotulos"]} & set(externa))
            return politica, calibrador, modelo, externos
        esperado = executar(rs)
        alterados = deepcopy(rs)
        for i in externa:
            alterados[i]["tema_central_id"] = "TEMA_EXTERNO_PROIBIDO_NO_TREINO"
            alterados[i]["fora_da_taxonomia"] = True
        self.assertEqual(executar(alterados), esperado)

    def test_aplicacao_externa_usa_confianca_externa_mesmo_existindo_oof(self):
        politica = {"habilitada": True, "regra": "confianca_p95", "corte": .95}
        p = {"confianca": .4, "confianca_oof": 1.0}
        self.assertFalse(aplicar(p, politica))
        p.update(confianca=.98, confianca_oof=.1)
        self.assertTrue(aplicar(p, politica))

    def test_motor_recebe_ancora_versionada_e_mantem_quatorze_atributos(self):
        tax = taxonomia()
        q = questao("q0", "Art. 1 da LEP, texto inteiramente sintético")
        original, enriquecido = caches(tax, [q])
        docs = [{"registros": [{"tema_id": i, "descricao": t["descricao"], "termos": [t["titulo"]]}
                                for i, t in tax["por_id"].items() if int(t["nivel"]) > 0]}]
        ancora = ancora_sintetica(tema_id="11")
        motor = Motor(tax, original, enriquecido, docs, None, ancora)
        xs, _, _ = motor.atributos(q)
        self.assertEqual(len(xs["11"]), 14)
        self.assertEqual((xs["11"][8], xs["11"][9], xs["11"][13]), (1, 1, 1))
        self.assertEqual(xs["21"][9], 0)
        json.dumps(motor.sinais.suporte_catalogo())


if __name__ == "__main__":
    unittest.main()
