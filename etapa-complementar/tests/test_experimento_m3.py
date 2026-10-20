"""Protocolo M3 verificado somente com textos, rótulos e vetores sintéticos."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from classificacao_experimentos import experimento
from classificacao_experimentos.entradas import hash_texto
from classificacao_experimentos.motor import predizer, treinar
from classificacao_local.experimento import selecionar_protocolo
from test_experimento import (
    AVALIACAO, DESENVOLVIMENTO, RESERVA, dados_sinteticos,
)


RAIZ = Path(__file__).resolve().parents[1]


def linhas_json(conteudo: bytes) -> list[dict]:
    return [json.loads(linha) for linha in conteudo.decode("utf-8").split("\n") if linha]


def fixture_m3():
    """O cache é construído em memória; nenhum anexo ou artefato real é aberto."""
    questoes, rotulos, taxonomia, particoes, protocolo_config, _ = dados_sinteticos()
    protocolo = selecionar_protocolo(particoes, protocolo_config)
    config = {
        "versao": 1,
        "criterio_selecao": list(experimento.CRITERIO),
        "top_k": 2,
        "limiares_diagnosticos_score": [0.0, 0.5, 1.0],
        "rrf_k": 20,
        "peso_semantico": 0.5,
        "lexical_base": {
            "peso_catalogo": 0.7, "peso_exemplos": 0.3, "peso_leis": 0.0,
        },
        "receitas": {
            "lexical": {
                "prioridade": 1, "modo": "lexical",
                "peso_exemplos": 0.3, "peso_leis": 0.0, "vizinhos": "lexicais",
            },
            "semantico": {
                "prioridade": 2, "modo": "semantico",
                "peso_exemplos": 0.0, "peso_leis": 0.0, "vizinhos": "lexicais",
            },
            "hibrido_catalogo": {
                "prioridade": 3, "modo": "hibrido",
                "peso_exemplos": 0.0, "peso_leis": 0.0, "vizinhos": "lexicais",
            },
            "hibrido_semanticos": {
                "prioridade": 4, "modo": "hibrido",
                "peso_exemplos": 0.3, "peso_leis": 0.0, "vizinhos": "semanticos",
            },
        },
    }
    vetores = {
        "D01": [0.8, 0.6, 0.0], "D02": [0.6, 0.8, 0.0],
        "D03": [0.96, 0.28, 0.0], "D04": [0.28, 0.96, 0.0],
        "D05": [0.8, 0.6, 0.0], "D06": [0.0, 0.0, 1.0],
        "A01": [0.8, 0.6, 0.0], "A02": [0.6, 0.8, 0.0],
    }
    cache = {
        "schema": "embeddings_e5_v1", "dimensoes": 3,
        "questoes": {
            q["id"]: {
                "texto_sha256": hash_texto("questao", q),
                "vetor": vetores[q["id"]], "tokens": 12, "janelas": 1,
            }
            for q in questoes if q["id"] not in RESERVA
        },
        "temas": {
            t["tema_id"]: {
                "texto_sha256": hash_texto("tema", t),
                "vetor": [1.0, 0.0, 0.0] if t["tema_id"] == "AMBAR"
                else [0.0, 1.0, 0.0],
                "tokens": 8, "janelas": 1,
            }
            for t in taxonomia["registros"]
            if t["status"] == "active" and int(t["nivel"]) > 0
        },
    }
    atualizar_assinatura(cache)
    return questoes, rotulos, taxonomia, protocolo, config, cache


def atualizar_assinatura(cache: dict) -> None:
    conteudo = {chave: valor for chave, valor in cache.items() if chave != "sha256"}
    cache["sha256"] = hashlib.sha256(json.dumps(
        conteudo, sort_keys=True, ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")).hexdigest()


class TestExperimentoM3(unittest.TestCase):
    def setUp(self):
        (self.questoes, self.rotulos, self.taxonomia,
         self.protocolo, self.config, self.cache) = fixture_m3()

    def processar(self):
        return experimento.processar_experimento(
            self.questoes, self.rotulos, self.taxonomia,
            self.protocolo, self.config, self.cache,
        )

    def test_isola_reserva_e_validacao_e_reajusta_apenas_vencedor(self):
        with (
            patch.object(experimento, "treinar", wraps=treinar) as ajustes,
            patch.object(experimento, "predizer", wraps=predizer) as inferencias,
        ):
            produtos, resumo = self.processar()
        n_receitas = len(self.config["receitas"])
        self.assertEqual(ajustes.call_count, n_receitas * 3 + 1)
        completos = []
        for chamada in ajustes.call_args_list:
            questoes, rotulos, _, parametros, cache = chamada.args
            ids = {q["id"] for q in questoes}
            self.assertEqual(ids, {r["id"] for r in rotulos})
            self.assertTrue(ids <= set(DESENVOLVIMENTO))
            self.assertFalse(ids & set(RESERVA + AVALIACAO))
            self.assertEqual(set(cache["questoes"]), set(DESENVOLVIMENTO + AVALIACAO))
            if ids == set(DESENVOLVIMENTO):
                completos.append(parametros)
            else:
                self.assertEqual(len(ids), 4)
        self.assertEqual(len(completos), 1)
        expandida = experimento.expandir_receitas(self.config)
        self.assertEqual(completos[0], expandida[resumo["receita_selecionada"]])
        self.assertEqual(len(ajustes.call_args_list[-1].args[0]), 6)

        consultas = Counter()
        for chamada in inferencias.call_args_list:
            modelo, questao, cache = chamada.args
            consultas[questao["id"]] += 1
            treino = {r["id"] for r in modelo["lexical"]["treino"]}
            self.assertNotIn(questao["id"], treino)
            self.assertNotIn(questao["id"], RESERVA)
            self.assertNotIn("segredoreserva", modelo["lexical"]["idf"])
            self.assertNotIn("futuroavaliacao", modelo["lexical"]["idf"])
            self.assertFalse(set(RESERVA) & set(cache["questoes"]))
        self.assertEqual(consultas, Counter({
            **{i: n_receitas for i in DESENVOLVIMENTO},
            **{i: 1 for i in AVALIACAO},
        }))
        self.assertEqual(resumo["reserva_sem_vetor_ou_predicao"], 2)
        modelo = json.loads(produtos["modelo_selecionado.json"])
        self.assertEqual({r["id"] for r in modelo["lexical"]["treino"]},
                         set(DESENVOLVIMENTO))

    def test_cache_com_reserva_ou_cobertura_incompleta_falha_antes_do_treino(self):
        original = deepcopy(self.cache)
        for alteracao in ("reserva", "ausencia"):
            with self.subTest(alteracao=alteracao):
                self.cache = deepcopy(original)
                if alteracao == "reserva":
                    reservada = next(q for q in self.questoes if q["id"] == "R01")
                    self.cache["questoes"]["R01"] = {
                        "texto_sha256": hash_texto("questao", reservada),
                        "vetor": [1.0, 0.0, 0.0], "tokens": 1, "janelas": 1,
                    }
                else:
                    self.cache["questoes"].pop("D01")
                atualizar_assinatura(self.cache)
                with (
                    patch.object(experimento, "treinar", wraps=treinar) as ajuste,
                    patch.object(experimento, "predizer", wraps=predizer) as inferencia,
                    self.assertRaisesRegex(ValueError, "Dados/cache"),
                ):
                    self.processar()
                ajuste.assert_not_called()
                inferencia.assert_not_called()

    def test_particao_com_reserva_ou_sobreposicao_falha_antes_de_inferir(self):
        original = deepcopy(self.protocolo)
        for tipo in ("reserva_treino", "reserva_validacao", "sobreposicao"):
            with self.subTest(tipo=tipo):
                self.protocolo = deepcopy(original)
                fold = self.protocolo["particoes_internas"][0]
                if tipo == "reserva_treino":
                    fold["treino_ids"][0] = "R01"
                elif tipo == "reserva_validacao":
                    fold["validacao_ids"][0] = "R01"
                else:
                    fold["treino_ids"].append(fold["validacao_ids"][0])
                with (
                    patch.object(experimento, "treinar", wraps=treinar) as ajuste,
                    patch.object(experimento, "predizer", wraps=predizer) as inferencia,
                    self.assertRaisesRegex(ValueError, "Partição interna"),
                ):
                    self.processar()
                ajuste.assert_not_called()
                inferencia.assert_not_called()

    def test_referencia_validada_duas_vezes_recusa_resultado_e_reajuste(self):
        internas = self.protocolo["particoes_internas"]
        internas[1]["treino_ids"] = internas[0]["treino_ids"].copy()
        internas[1]["validacao_ids"] = internas[0]["validacao_ids"].copy()
        with (
            patch.object(experimento, "treinar", wraps=treinar) as ajustes,
            self.assertRaisesRegex(ValueError, "uma predição fora da amostra"),
        ):
            self.processar()
        self.assertTrue(ajustes.called)
        self.assertTrue(all(len(c.args[0]) == 4 for c in ajustes.call_args_list))

    def test_oof_uma_vez_por_receita_e_sugestoes_so_do_vencedor(self):
        produtos, resumo = self.processar()
        predicoes = linhas_json(produtos["predicoes_desenvolvimento.jsonl"])
        self.assertEqual(len(predicoes), 6 * len(self.config["receitas"]))
        for receita in self.config["receitas"]:
            selecionadas = [p for p in predicoes if p["receita"] == receita]
            self.assertEqual(Counter(p["id"] for p in selecionadas),
                             Counter(DESENVOLVIMENTO))
            for p in selecionadas:
                fold = next(f for f in self.protocolo["particoes_internas"]
                            if f["indice"] == p["particao_interna"])
                self.assertIn(p["id"], fold["validacao_ids"])
                self.assertNotIn(p["id"], fold["treino_ids"])
                self.assertTrue({v["id"] for v in p["vizinhos"]}
                                <= set(fold["treino_ids"]))
        sugestoes = linhas_json(produtos["sugestoes_avaliacao.jsonl"])
        self.assertEqual(Counter(p["id"] for p in sugestoes), Counter(AVALIACAO))
        self.assertEqual({p["receita"] for p in sugestoes},
                         {resumo["receita_selecionada"]})
        self.assertTrue(all(p["uso"] == "sugestao_intermediaria" for p in sugestoes))

    def test_textos_e_rotulos_reservados_nao_mudam_nenhum_produto(self):
        esperado = self.processar()
        for q in self.questoes:
            if q["id"] in RESERVA:
                q["enunciado"] = "Texto reservado alterado por completo."
                q["comando"] = "Não participa do classificador."
                q["alternativas"] = {"z": "Novo conteúdo reservado."}
        for r in self.rotulos:
            if r["id"] in RESERVA:
                r.update({
                    "tema_central_id": "", "extras_ids": [],
                    "fora_da_taxonomia": True, "disciplina": "Mudança reservada",
                })
        self.assertEqual(self.processar(), esperado)

    def test_modelo_json_reproduz_sugestoes_e_ordem_de_entrada_nao_influencia(self):
        produtos, resumo = self.processar()
        self.questoes.reverse()
        self.rotulos.reverse()
        self.assertEqual(self.processar(), (produtos, resumo))
        modelo = json.loads(produtos["modelo_selecionado.json"])
        por_id = {q["id"]: q for q in self.questoes}
        for salvo in linhas_json(produtos["sugestoes_avaliacao.jsonl"]):
            reconstruido = predizer(
                modelo, por_id[salvo["id"]], self.cache, top_k=self.config["top_k"],
            )
            self.assertEqual(salvo, {
                **reconstruido, "receita": resumo["receita_selecionada"],
                "uso": "sugestao_intermediaria",
            })

    def test_fora_permanece_nos_denominadores_e_particoes(self):
        produtos, _ = self.processar()
        relatorio = json.loads(produtos["metricas_desenvolvimento.json"])
        self.assertEqual(relatorio["referencias_desenvolvimento"]["fora"], 1)
        for metricas in relatorio["receitas"].values():
            self.assertEqual(metricas["geral"]["total"], 6)
            self.assertEqual(metricas["dentro_taxonomia"]["total"], 5)
            self.assertEqual(metricas["fora_taxonomia"]["total"], 1)
            self.assertEqual(metricas["fora_taxonomia"]["acertos"],
                             {"ramo": 0, "imediato": 0, "exato": 0})
            self.assertEqual({k: v["total"] for k, v in
                              metricas["por_particao_interna"].items()},
                             {"1": 2, "2": 2, "3": 2})
            for modo, acertos in metricas["geral"]["acertos"].items():
                self.assertEqual(metricas["geral"]["taxas_acerto"][modo], acertos / 6)

    def test_curva_exclui_ausencia_evidencia_e_trata_subconjunto_vazio(self):
        resultados = []
        for identificador, score, sem_evidencia in (
            ("S1", 0.25, False), ("S2", 0.9, True),
        ):
            resultados.append({
                "id": identificador, "score": score, "sem_evidencia": sem_evidencia,
                "referencia_fora": False, "disciplina_referencia": "Sintética",
                "central_visto_treino": False, "particao_interna": 1,
                "acertos": {"ramo": True, "imediato": True, "exato": True},
                "acerto_top_k_ramo": True,
            })
        metricas = experimento.medir(resultados, [0.0, 0.5, 1.0])
        curva = metricas["curva_diagnostica_score"]
        self.assertEqual(curva[0]["total"], 1)
        self.assertEqual(curva[0]["fracao_retida"], 0.5)
        for vazia in curva[1:]:
            self.assertEqual(vazia["total"], 0)
            self.assertEqual(vazia["fracao_retida"], 0.0)
            self.assertIsNone(vazia["taxa_top_k_ramo"])
            self.assertEqual(vazia["taxas_acerto"],
                             {"ramo": None, "imediato": None, "exato": None})

    def test_congelamento_nao_confunde_classificador_com_politica_pronta(self):
        produtos, resumo = self.processar()
        congelamento = json.loads(produtos["receita_congelada.json"])
        self.assertTrue(congelamento["classificador_congelado_para_modulo4"])
        self.assertFalse(congelamento["calibrador_e_politica_congelados"])
        self.assertEqual(congelamento["treino_ids"], DESENVOLVIMENTO)
        self.assertEqual(congelamento["reserva_ids"], RESERVA)
        self.assertEqual(congelamento["cache_sha256"], self.cache["sha256"])
        self.assertEqual(congelamento["receita"], resumo["receita_selecionada"])
        relatorio = json.loads(produtos["metricas_desenvolvimento.json"])
        self.assertFalse(relatorio["score_e_probabilidade"])
        self.assertFalse(relatorio["curva_define_publicacao"])
        self.assertFalse(any(nome.endswith(".csv") for nome in produtos))
        for nome in ("predicoes_desenvolvimento.jsonl", "sugestoes_avaliacao.jsonl"):
            self.assertTrue(all("confianca" not in p and "decisao" not in p
                                for p in linhas_json(produtos[nome])))

    def test_execucao_em_processo_limpo_sem_importar_encoder_ou_acessar_rede(self):
        codigo = r'''
import builtins, json, socket, sys
original_import = builtins.__import__
proibidos = {"numpy", "onnxruntime", "tokenizers", "transformers", "torch"}
def importar(nome, *args, **kwargs):
    if nome.split(".")[0] in proibidos or (
        nome.startswith("classificacao_experimentos.")
        and any(t in nome for t in ("preparacao", "encoder", "embeddings"))
    ):
        raise AssertionError("Dependência de preparação importada: " + nome)
    return original_import(nome, *args, **kwargs)
builtins.__import__ = importar
def sem_rede(*args, **kwargs):
    raise AssertionError("A classificação tentou usar a rede")
socket.socket.connect = sem_rede
socket.create_connection = sem_rede
sys.path.insert(0, "tests")
from test_experimento_m3 import fixture_m3
from classificacao_experimentos.experimento import processar_experimento
produtos, resumo = processar_experimento(*fixture_m3())
print(json.dumps(resumo))
'''
        processo = subprocess.run(
            [sys.executable, "-B", "-c", codigo], cwd=RAIZ,
            capture_output=True, text=True, encoding="utf-8", timeout=90,
        )
        self.assertEqual(processo.returncode, 0, processo.stderr)
        resumo = json.loads(processo.stdout)
        self.assertEqual(resumo["desenvolvimento"], 6)
        self.assertEqual(resumo["reserva_sem_vetor_ou_predicao"], 2)
        self.assertEqual(resumo["predicoes_desenvolvimento"], 24)


class TestSelecaoM3(unittest.TestCase):
    """Resultados controlados isolam a política, sem supor desempenho do motor."""

    def setUp(self):
        self.dados = list(fixture_m3())
        taxonomia, config, cache = self.dados[2], self.dados[4], self.dados[5]
        del config["receitas"]["hibrido_semanticos"]
        self.centrais = {
            r["id"]: r["tema_central_id"] for r in self.dados[1]
            if r["id"] in DESENVOLVIMENTO and r["tema_central_id"]
        }
        for pai in ("AMBAR", "PRISMA"):
            original = taxonomia["por_id"][pai]
            filho = {
                **deepcopy(original), "tema_id": pai + "_DETALHE",
                "nivel": "2", "parent_id": pai, "ancestrais_ids": ["RAIZ", pai],
                "titulo": original["titulo"] + " detalhado",
                "caminho": original["caminho"] + " > Detalhe fictício",
            }
            taxonomia["registros"].append(filho)
            taxonomia["por_id"][filho["tema_id"]] = filho
            cache["temas"][filho["tema_id"]] = {
                "texto_sha256": hash_texto("tema", filho),
                "vetor": cache["temas"][pai]["vetor"].copy(),
                "tokens": 10, "janelas": 1,
            }
        atualizar_assinatura(cache)

    def executar_controlado(self, acertos: dict, descendentes: set[str] = frozenset()):
        def prever(modelo, questao, cache, top_k=2):
            modo = modelo["config"]["modo"]
            identificador = questao["id"]
            tema = "NAO_E_UM_TEMA"
            if identificador in acertos[modo]:
                tema = self.centrais[identificador]
                if modo in descendentes:
                    tema += "_DETALHE"
            return {
                "id": identificador, "tema_sugerido_id": tema,
                "score": 0.4, "margem": 0.1, "sem_evidencia": False,
                "apoio_fora": 0.0, "top_candidatos": [{"tema_id": tema, "score": 0.4}],
                "vizinhos": [],
            }
        with patch.object(experimento, "predizer", side_effect=prever):
            produtos, resumo = experimento.processar_experimento(*self.dados)
        return json.loads(produtos["metricas_desenvolvimento.json"]), resumo

    def test_ramo_tem_precedencia_sobre_exato_e_prioridade(self):
        relatorio, resumo = self.executar_controlado({
            "lexical": {"D01", "D02", "D03"},
            "semantico": {"D01", "D02", "D03", "D04"},
            "hibrido": {"D01", "D02"},
        }, descendentes={"semantico"})
        self.assertEqual(resumo["receita_selecionada"], "semantico")
        self.assertEqual(relatorio["receitas"]["semantico"]["geral"]["acertos"],
                         {"ramo": 4, "imediato": 4, "exato": 0})
        self.assertEqual(relatorio["receitas"]["lexical"]["geral"]["acertos"]["exato"], 3)

    def test_exato_desempata_ramo_antes_da_prioridade(self):
        relatorio, resumo = self.executar_controlado({
            "lexical": {"D01", "D02", "D03", "D04"},
            "semantico": {"D01", "D02", "D03", "D04"},
            "hibrido": {"D01", "D02"},
        }, descendentes={"lexical"})
        self.assertEqual(resumo["receita_selecionada"], "semantico")
        self.assertEqual(relatorio["receitas"]["lexical"]["geral"]["acertos"]["ramo"], 4)
        self.assertEqual(relatorio["receitas"]["semantico"]["geral"]["acertos"]["exato"], 4)

    def test_prioridade_desempata_acertos_sem_depender_da_ordem_alfabetica(self):
        receitas = self.dados[4]["receitas"]
        receitas["lexical"]["prioridade"] = 3
        receitas["semantico"]["prioridade"] = 1
        receitas["hibrido_catalogo"]["prioridade"] = 2
        _, resumo = self.executar_controlado({
            modo: {"D01", "D02"} for modo in ("lexical", "semantico", "hibrido")
        })
        self.assertEqual(resumo["receita_selecionada"], "semantico")

    def test_prioridade_repetida_recusada_antes_de_ajustar(self):
        receitas = self.dados[4]["receitas"]
        receitas["semantico"]["prioridade"] = receitas["lexical"]["prioridade"]
        with (
            patch.object(experimento, "treinar", wraps=treinar) as ajuste,
            self.assertRaisesRegex(ValueError, "Prioridades"),
        ):
            experimento.processar_experimento(*self.dados)
        ajuste.assert_not_called()


if __name__ == "__main__":
    unittest.main()
