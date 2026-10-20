"""Crossfit e abstenção com referências fictícias, sem examinar casos reais."""

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from classificacao_decisao import desenvolvimento as d
from classificacao_decisao import politica as p


RAIZ = Path(__file__).resolve().parents[1]


def configuracao():
    # Somente parâmetros declarados; nenhum artefato com textos/rótulos reais.
    return json.loads((RAIZ / "config/modulo4/protocolo.json").read_text(encoding="utf-8"))


def taxonomia():
    registros = [
        {"tema_id": "RAIZ", "titulo": "Ciências", "status": "active", "nivel": "0",
         "parent_id": "", "ancestrais_ids": []},
        {"tema_id": "PAI", "titulo": "Plantas", "status": "active", "nivel": "1",
         "parent_id": "RAIZ", "ancestrais_ids": ["RAIZ"]},
        {"tema_id": "PONTE", "titulo": "Coleção antiga", "status": "inactive", "nivel": "2",
         "parent_id": "PAI", "ancestrais_ids": ["RAIZ", "PAI"]},
        {"tema_id": "FLOR", "titulo": "Flores amarelas", "status": "active", "nivel": "3",
         "parent_id": "PONTE", "ancestrais_ids": ["RAIZ", "PAI", "PONTE"]},
        {"tema_id": "GEN", "titulo": "Introdução às cores", "status": "active", "nivel": "1",
         "parent_id": "RAIZ", "ancestrais_ids": ["RAIZ"]},
        {"tema_id": "COR", "titulo": "Pigmentos azuis", "status": "active", "nivel": "1",
         "parent_id": "RAIZ", "ancestrais_ids": ["RAIZ"]},
    ]
    return {"registros": registros, "por_id": {t["tema_id"]: t for t in registros}}


def fixture():
    dev = [f"D{i}" for i in range(6)]
    folds = []
    predicoes = []
    for indice in range(3):
        validacao = dev[2 * indice:2 * indice + 2]
        folds.append({
            "indice": indice + 1, "validacao_ids": validacao,
            "treino_ids": [i for i in dev if i not in validacao],
        })
        for i in validacao:
            numero = int(i[1:])
            acerto = numero % 2 == 1
            predicoes.append({
                "id": i, "receita": "hibrido_catalogo", "particao_interna": indice + 1,
                "tema_sugerido_id": "FLOR" if acerto else "COR",
                "score": (numero + 1) / 10, "margem": (numero + 1) / 100,
                "sem_evidencia": False, "referencia_fora": numero == 0,
                "acertos": {"ramo": acerto, "imediato": acerto, "exato": acerto},
                "acerto_top_k_ramo": acerto,
            })
    protocolo = {
        "desenvolvimento_ids": dev, "reserva_ids": ["R1", "R2"],
        "avaliacao_ids": ["E1", "E2"], "particoes_internas": folds,
    }
    return predicoes, protocolo, taxonomia(), configuracao()


def decodificar_jsonl(conteudo):
    return [json.loads(linha) for linha in conteudo.decode("utf-8").split("\n") if linha]


def retencao(n, acertos=None, confianca=0.99):
    acertos = n if acertos is None else acertos
    return [{
        "id": f"F{i}", "tema_sugerido_id": "FLOR", "sem_evidencia": False,
        "dentro_dominio": True, "confianca": confianca, "acerto": i < acertos,
    } for i in range(n)]


class TestDesenvolvimentoM4(unittest.TestCase):
    def test_crossfit_treina_so_nos_ids_do_fold_e_cobre_tres_vezes_desenvolvimento(self):
        predicoes, protocolo, temas, config = fixture()
        originais = deepcopy((predicoes, protocolo, temas, config))
        ajustar_original, prever_original = d.ajustar, d.prever
        treinados, consultas = [], []

        def ajustar(registros, atributos, regularizacao):
            modelo = ajustar_original(registros, atributos, regularizacao)
            treinados.append((modelo, tuple(r["id"] for r in registros), tuple(atributos)))
            self.assertTrue(all(r["acerto"] == r["acertos"]["ramo"] for r in registros))
            return modelo

        def prever(modelo, registro):
            ids = next(ids for ajustado, ids, _ in treinados if ajustado is modelo)
            self.assertNotIn(registro["id"], ids)
            consultas.append(registro["id"])
            return prever_original(modelo, registro)

        with patch.object(d, "ajustar", side_effect=ajustar), patch.object(d, "prever", side_effect=prever):
            produtos, resumo = d.processar_desenvolvimento(predicoes, protocolo, temas, config)
        self.assertEqual(len(treinados), 10)  # 3 receitas x 3 folds, depois 1 ajuste final.
        for indice, (_, ids, atributos) in enumerate(treinados[:-1]):
            fold = protocolo["particoes_internas"][indice % 3]
            self.assertEqual(set(ids), set(fold["treino_ids"]))
            self.assertEqual(atributos, ((), ("score",), ("score", "margem"))[indice // 3])
        self.assertEqual(set(treinados[-1][1]), set(protocolo["desenvolvimento_ids"]))
        self.assertEqual(Counter(consultas), Counter({i: 3 for i in protocolo["desenvolvimento_ids"]}))
        linhas = decodificar_jsonl(produtos["predicoes_calibradas.jsonl"])
        self.assertEqual(len(linhas), 18)
        self.assertEqual(Counter((r["calibrador"], r["id"]) for r in linhas),
                         Counter({(c, i): 1 for c in config["calibradores"]
                                  for i in protocolo["desenvolvimento_ids"]}))
        self.assertTrue(all(r["procedencia_probabilidade"] == "crossfit_desenvolvimento" for r in linhas))
        self.assertEqual(resumo["predicoes_calibradas"], 18)
        self.assertFalse(resumo["reserva_consultada"])
        self.assertEqual(originais, (predicoes, protocolo, temas, config))

    def test_predicao_reservada_duplicada_ausente_ou_avaliacao_recusada(self):
        predicoes, protocolo, temas, config = fixture()
        variacoes = [
            predicoes[:-1], predicoes + [predicoes[0]],
            predicoes[:-1] + [{**predicoes[-1], "id": "R1"}],
            predicoes + [{"id": "R1"}], predicoes + [{"id": "E1"}],
        ]
        with patch.object(d, "ajustar", side_effect=AssertionError("Não deve iniciar treino.")) as ajustar:
            for registros in variacoes:
                with self.subTest(ids=[r["id"] for r in registros]), self.assertRaises(ValueError):
                    d.processar_desenvolvimento(registros, protocolo, temas, config)
            ajustar.assert_not_called()

    def test_grupos_de_ids_dev_reserva_avaliacao_sao_unicos_e_disjuntos(self):
        predicoes, original, temas, config = fixture()
        variacoes = []
        for campo, valor in (
            ("desenvolvimento_ids", original["desenvolvimento_ids"] + ["D0"]),
            ("reserva_ids", ["D0", "R2"]), ("avaliacao_ids", ["D0", "E2"]),
            ("reserva_ids", ["E1", "R2"]), ("reserva_ids", ["R1", "R1"]),
            ("avaliacao_ids", ["E1", "E1"]),
        ):
            protocolo = deepcopy(original)
            protocolo[campo] = valor
            variacoes.append(protocolo)
        for protocolo in variacoes:
            with self.subTest(protocolo=protocolo), self.assertRaises(ValueError):
                d.processar_desenvolvimento(predicoes, protocolo, temas, config)

    def test_folds_com_vazamento_duplicacao_ausencia_ou_indice_divergente_recusados(self):
        predicoes, original, temas, config = fixture()
        variacoes = []
        for campo, valor in (
            ("treino_ids", ["D0", "D2", "D3", "D4", "D5"]),
            ("treino_ids", ["D2", "D2", "D3", "D4", "D5"]),
            ("treino_ids", ["D2", "D3", "D4", "R1"]),
            ("validacao_ids", ["D0", "D0", "D1"]),
            ("validacao_ids", ["D0"]), ("indice", 9),
        ):
            protocolo = deepcopy(original)
            protocolo["particoes_internas"][0][campo] = valor
            variacoes.append(protocolo)
        protocolo = deepcopy(original)
        protocolo["particoes_internas"] = protocolo["particoes_internas"][:-1]
        variacoes.append(protocolo)
        protocolo = deepcopy(original)
        protocolo["particoes_internas"] += [deepcopy(protocolo["particoes_internas"][0])]
        variacoes.append(protocolo)
        with patch.object(d, "ajustar", side_effect=AssertionError("Não iniciar ajuste.")):
            for protocolo in variacoes:
                with self.subTest(protocolo=protocolo), self.assertRaises(ValueError):
                    d.processar_desenvolvimento(predicoes, protocolo, temas, config)

    def test_registros_exigem_receita_booleanos_e_scores_finitos(self):
        original, protocolo, temas, config = fixture()
        variacoes = []
        for campo, valor in (
            ("receita", "outra"), ("score", float("nan")), ("score", True),
            ("score", 1.1), ("margem", -0.1), ("margem", float("inf")),
            ("referencia_fora", 0), ("sem_evidencia", 1),
            ("acertos", {"ramo": 1, "imediato": False, "exato": False}),
        ):
            registros = deepcopy(original)
            registros[0][campo] = valor
            variacoes.append(registros)
        for registros in variacoes:
            with self.subTest(registro=registros[0]), self.assertRaises(ValueError):
                d.processar_desenvolvimento(registros, protocolo, temas, config)

    def test_selecao_usa_brier_depois_logloss_depois_prioridade(self):
        predicoes, protocolo, temas, config = fixture()
        metrica_original = d.metricas
        casos = [
            ([(0.4, 0.1), (0.2, 0.9), (0.3, 0.05)], "logistica_score"),
            ([(0.2, 0.6), (0.2, 0.4), (0.2, 0.5)], "logistica_score"),
            ([(0.2, 0.4), (0.2, 0.4), (0.2, 0.4)], "constante"),
        ]
        for grade, esperado in casos:
            chamadas = 0

            def metricas(probabilidades, alvos):
                nonlocal chamadas
                resultado = metrica_original(probabilidades, alvos)
                if chamadas < 3:
                    resultado["brier"], resultado["logloss"] = grade[chamadas]
                chamadas += 1
                return resultado

            with self.subTest(grade=grade), patch.object(d, "metricas", side_effect=metricas):
                produtos, resumo = d.processar_desenvolvimento(predicoes, protocolo, temas, config)
                self.assertEqual(resumo["calibrador"], esperado)
                self.assertEqual(json.loads(produtos["calibrador.json"])["nome"], esperado)
                self.assertEqual(json.loads(produtos["politica.json"])["calibrador"], esperado)

    def test_dominio_crossfit_usa_somente_minimo_maximo_do_treino(self):
        predicoes, protocolo, temas, config = fixture()
        produtos, _ = d.processar_desenvolvimento(predicoes, protocolo, temas, config)
        linhas = decodificar_jsonl(produtos["predicoes_calibradas.jsonl"])
        por_id = {r["id"]: r for r in predicoes}
        folds = {f["indice"]: f for f in protocolo["particoes_internas"]}
        for r in linhas:
            atributos = config["calibradores"][r["calibrador"]]["atributos"]
            treino = [por_id[i] for i in folds[r["particao_interna"]]["treino_ids"]]
            esperado = all(min(t[a] for t in treino) <= r[a] <= max(t[a] for t in treino)
                           for a in atributos)
            self.assertEqual(r["dentro_dominio"], esperado)
        self.assertTrue(all(r["dentro_dominio"] for r in linhas if r["calibrador"] == "constante"))
        self.assertFalse(next(r["dentro_dominio"] for r in linhas
                              if r["id"] == "D0" and r["calibrador"] == "logistica_score"))
        self.assertFalse(next(r["dentro_dominio"] for r in linhas
                              if r["id"] == "D5" and r["calibrador"] == "logistica_score_margem"))

    def test_conteudo_e_rotulo_reservado_nao_influenciam_funcao_pura(self):
        predicoes, protocolo, temas, config = fixture()
        protocolo["dados_reserva"] = {
            "R1": {"texto": "Planeta violeta", "rotulo": "FLOR", "predicao": "COR"},
            "R2": {"texto": "Cometa âmbar", "rotulo": "COR", "predicao": "FLOR"},
        }
        original = d.processar_desenvolvimento(predicoes, protocolo, temas, config)
        alterado = deepcopy(protocolo)
        alterado["dados_reserva"] = {
            "R1": {"texto": "Texto totalmente alterado", "rotulo": "OUTRO", "predicao": None},
            "R2": {"texto": "", "rotulo": None, "predicao": "OUTRO"},
        }
        self.assertEqual(original, d.processar_desenvolvimento(predicoes, alterado, temas, config))


class TestPoliticaM4(unittest.TestCase):
    def test_suporte_minimo_dez_e_meta_de_precisao_95(self):
        config = configuracao()
        for n, acertos, habilitada in ((9, 9, False), (10, 10, True),
                                      (20, 19, True), (20, 18, False)):
            with self.subTest(n=n, acertos=acertos):
                politica, curvas = p.selecionar_politica(retencao(n, acertos), {"FLOR": ""}, config)
                self.assertEqual(politica["publicacao_habilitada"], habilitada)
                self.assertEqual(politica["limiar"], 0.95 if habilitada else None)
                self.assertEqual(curvas[0]["publicadas"], n)
                self.assertEqual(curvas[0]["acertos"], acertos)

    def test_zero_retidos_nao_produz_precisao_nem_intervalo_inventados(self):
        config = configuracao()
        conjuntos = [
            [], retencao(20, confianca=0.5),
            [{**r, "sem_evidencia": True} for r in retencao(20)],
            [{**r, "dentro_dominio": False} for r in retencao(20)],
        ]
        for registros in conjuntos:
            with self.subTest(n=len(registros)):
                politica, curvas = p.selecionar_politica(registros, {"FLOR": ""}, config)
                self.assertFalse(politica["publicacao_habilitada"])
                self.assertIsNone(politica["limiar"])
                for curva in curvas:
                    self.assertEqual(curva["publicadas"], 0)
                    self.assertIsNone(curva["precisao"])
                    self.assertIsNone(curva["intervalo_wilson_95"])
                    self.assertFalse(curva["atende_criterios"])

    def test_limiar_prefere_cobertura_e_desempata_pelo_menor_valor(self):
        registros = retencao(20, 19, 0.98) + [
            {**r, "id": "ERRO" + r["id"], "acerto": False} for r in retencao(2, 0, 0.96)
        ]
        politica, curvas = p.selecionar_politica(registros, {"FLOR": ""}, configuracao())
        self.assertEqual(politica["limiar"], 0.975)
        self.assertEqual(politica["selecao"]["publicadas"], 20)
        self.assertFalse(curvas[0]["atende_criterios"])
        empate, _ = p.selecionar_politica(retencao(10, confianca=1.0), {"FLOR": ""}, configuracao())
        self.assertEqual(empate["limiar"], 0.95)

    def test_ancestral_com_descendente_ativo_atraves_de_no_inativo_e_bloqueado(self):
        motivos = p.elegibilidade(taxonomia(), configuracao()["elegibilidade"])
        self.assertIn("descendentes ativos", motivos["PAI"])
        self.assertIn("inativo", motivos["PONTE"])
        self.assertIn("Disciplina", motivos["RAIZ"])
        self.assertEqual(motivos["FLOR"], "")
        self.assertEqual(motivos["COR"], "")

    def test_titulo_generico_e_normalizado_com_limites_de_palavra(self):
        temas = taxonomia()
        genericos = [
            "INTRODUÇÃO", "Considerações-gerais sobre planetas",
            "Aspectos   Gerais: pigmentos", "Noções gerais de astronomia",
            "Princípios gerais de cores",
        ]
        for indice, titulo in enumerate(genericos + ["Introducaozinha", "Cores gerais"]):
            temas["registros"].append({
                "tema_id": f"S{indice}", "titulo": titulo,
                "status": "active", "nivel": "1", "ancestrais_ids": ["RAIZ"],
            })
        motivos = p.elegibilidade(temas, configuracao()["elegibilidade"])
        for indice in range(len(genericos)):
            self.assertIn("Título genérico", motivos[f"S{indice}"])
        self.assertEqual(motivos[f"S{len(genericos)}"], "")
        self.assertEqual(motivos[f"S{len(genericos) + 1}"], "")
        politica, curvas = p.selecionar_politica(
            [{**r, "tema_sugerido_id": "GEN"} for r in retencao(20)],
            motivos, configuracao(),
        )
        self.assertFalse(politica["publicacao_habilitada"])
        self.assertTrue(all(c["publicadas"] == 0 for c in curvas))

    def test_decidir_respeita_motivos_e_nunca_promove_para_ancestral_ou_fora(self):
        config = configuracao()
        motivos = p.elegibilidade(taxonomia(), config["elegibilidade"])
        politica, _ = p.selecionar_politica(retencao(10), motivos, config)
        base = retencao(1)[0]
        casos = [
            ({**base, "tema_sugerido_id": "PAI"}, "descendentes"),
            ({**base, "tema_sugerido_id": "GEN"}, "genérico"),
            ({**base, "sem_evidencia": True}, "Sem evidência"),
            ({**base, "dentro_dominio": False}, "fora da faixa"),
            ({**base, "confianca": 0.94}, "abaixo do mínimo"),
        ]
        for predicao, trecho in casos:
            with self.subTest(predicao=predicao):
                resultado = p.decidir(predicao, politica, motivos)
                self.assertEqual(resultado["decisao"], "revisar")
                self.assertEqual(resultado["tema_central_id"], predicao["tema_sugerido_id"])
                self.assertIn(trecho, resultado["motivo"])
                self.assertEqual(resultado["extras_ids"], "")
        publicada = p.decidir(base, politica, motivos)
        self.assertEqual(publicada["decisao"], "publicar")
        self.assertEqual(publicada["motivo"], "")
        desabilitada = {**politica, "publicacao_habilitada": False, "limiar": None}
        self.assertIn("sem suporte", p.decidir(base, desabilitada, motivos)["motivo"])
        for confianca in (-0.01, 1.01, True, float("nan"), float("inf")):
            with self.subTest(confianca=confianca), self.assertRaises(ValueError):
                p.decidir({**base, "confianca": confianca}, politica, motivos)
        with self.assertRaises(ValueError):
            p.decidir({**base, "tema_sugerido_id": "ausente"}, politica, motivos)

    def test_faixas_sao_inclusivas_e_nao_aprendem_com_a_consulta(self):
        treino = [{"score": 0.2, "margem": 0.05}, {"score": 0.8, "margem": 0.15}]
        faixas = p.dominio(treino, ["score", "margem"])
        original = deepcopy(faixas)
        self.assertTrue(p.dentro_dominio(treino[0], faixas))
        self.assertTrue(p.dentro_dominio(treino[1], faixas))
        self.assertFalse(p.dentro_dominio({"score": 0.81, "margem": 0.1}, faixas))
        self.assertFalse(p.dentro_dominio({"score": 0.5, "margem": 0.01}, faixas))
        self.assertEqual(faixas, original)
        self.assertEqual(p.dominio(treino, []), {})
        self.assertTrue(p.dentro_dominio({}, {}))
        with self.assertRaises(ValueError):
            p.dominio([], ["score"])
        for valor in (True, float("nan"), float("inf")):
            with self.subTest(valor=valor), self.assertRaises(ValueError):
                p.dentro_dominio({"score": valor, "margem": 0.1}, faixas)


if __name__ == "__main__":
    unittest.main()
