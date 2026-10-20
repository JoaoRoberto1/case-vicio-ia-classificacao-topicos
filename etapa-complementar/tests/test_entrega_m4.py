"""Contratos da entrega e seus denominadores, usando somente fixtures sintéticas."""

from copy import deepcopy
import csv
import io
import json
import math
import unittest

from classificacao_decisao.calibracao import wilson
from classificacao_decisao.entrega import COLUNAS, gerar_csv, gerar_previsao, validar_csv


def taxonomia():
    temas = [
        {"tema_id": "raiz", "status": "active", "nivel": "0"},
        {"tema_id": "flor", "status": "active", "nivel": "1"},
        {"tema_id": "astro", "status": "active", "nivel": "2"},
        {"tema_id": "antigo", "status": "inactive", "nivel": "1"},
    ]
    return {"registros": temas, "por_id": {t["tema_id"]: t for t in temas}}


def registro(identificador, decisao="publicar", confianca=0.8, **extras):
    return {
        "id": identificador, "decisao": decisao,
        "tema_central_id": "" if decisao == "fora" else "flor",
        "extras_ids": "", "confianca": confianca,
        "motivo": "" if decisao == "publicar" else "Revisão necessária.",
        **extras,
    }


def csv_sem_validacao(registros, colunas=None):
    arquivo = io.StringIO(newline="")
    escritor = csv.DictWriter(
        arquivo, fieldnames=COLUNAS if colunas is None else colunas,
        lineterminator="\n",
    )
    escritor.writeheader()
    escritor.writerows(registros)
    return arquivo.getvalue().encode("utf-8")


def reserva(n=0, acertos=0):
    return {
        "geral": {
            "publicacao": {
                "n": n, "acertos": acertos,
                "precisao": acertos / n if n else None,
                "intervalo_wilson_95": wilson(acertos, n),
            },
        },
    }


def lote():
    return [
        registro("e0", confianca=0.75),
        registro("e1", confianca=0.25),
        registro("e2", "revisar", confianca=0.99),
        registro("ref0", confianca=1.0),
        registro("ref1", confianca=0.99),
    ]


class TestEntregaM4(unittest.TestCase):
    def test_csv_cabecalho_oficial_ordem_estavel_utf8_e_roundtrip(self):
        dados = [
            registro("c", "fora", motivo="Sem tema."),
            registro("b", "revisar", motivo='Revisão de "flores", árvores.\nNova linha.'),
            registro("a", confianca=0.987654321, tema_central_id="astro"),
        ]
        conteudo = gerar_csv(dados)
        self.assertTrue(conteudo.startswith(b"id,decisao,tema_central_id,extras_ids,confianca,motivo\n"))
        linhas = list(csv.DictReader(io.StringIO(conteudo.decode("utf-8"), newline="")))
        self.assertEqual([r["id"] for r in linhas], ["a", "b", "c"])
        self.assertEqual(linhas[0]["confianca"], "0.98765432")
        self.assertEqual(linhas[1]["motivo"], dados[1]["motivo"])
        self.assertEqual(gerar_csv(list(reversed(dados))), conteudo)
        self.assertEqual(validar_csv(conteudo, {"a", "b", "c"}, taxonomia()), {
            "linhas": 3, "decisoes": {"fora": 1, "publicar": 1, "revisar": 1},
        })

    def test_gerador_rejeita_duplicatas(self):
        with self.assertRaises(ValueError):
            gerar_csv([registro("a"), registro("a", "revisar")])

    def test_validador_exige_todos_os_ids_sem_substituicoes_ou_duplicatas(self):
        for dados in (
            [registro("a")],
            [registro("a"), registro("c")],
            [registro("a"), registro("a")],
            [registro("a"), registro("b"), registro("b")],
        ):
            with self.subTest(ids=[r["id"] for r in dados]):
                with self.assertRaises(ValueError):
                    validar_csv(csv_sem_validacao(dados), {"a", "b"}, taxonomia())

    def test_validador_rejeita_cabecalho_e_colunas_desalinhados(self):
        valido = gerar_csv([registro("a")])
        invalidos = [
            valido.replace(b"id,decisao,", b"identificador,decisao,", 1),
            valido.replace(b",motivo\n", b",motivo,extra\n", 1),
            valido.replace(b"0.80000000,\n", b"0.80000000\n"),
            valido.replace(b"0.80000000,\n", b"0.80000000,,extra\n"),
        ]
        for conteudo in invalidos:
            with self.assertRaises(ValueError):
                validar_csv(conteudo, {"a"}, taxonomia())

    def test_tema_central_deve_existir_ser_ativo_e_nao_ser_raiz(self):
        for tema in ("", "desconhecido", "antigo", "raiz"):
            for decisao in ("publicar", "revisar"):
                with self.subTest(tema=tema, decisao=decisao):
                    conteudo = gerar_csv([registro("a", decisao, tema_central_id=tema)])
                    with self.assertRaises(ValueError):
                        validar_csv(conteudo, {"a"}, taxonomia())

    def test_extras_devem_ser_vazios_em_todas_as_decisoes(self):
        for decisao in ("publicar", "revisar", "fora"):
            conteudo = gerar_csv([registro("a", decisao, extras_ids="astro")])
            with self.assertRaises(ValueError):
                validar_csv(conteudo, {"a"}, taxonomia())

    def test_fora_exige_tema_vazio(self):
        conteudo = gerar_csv([registro("a", "fora", tema_central_id="flor")])
        with self.assertRaises(ValueError):
            validar_csv(conteudo, {"a"}, taxonomia())

    def test_revisar_e_fora_exigem_motivo(self):
        for decisao in ("revisar", "fora"):
            for motivo in ("", " \t\n"):
                conteudo = gerar_csv([registro("a", decisao, motivo=motivo)])
                with self.assertRaises(ValueError):
                    validar_csv(conteudo, {"a"}, taxonomia())
        self.assertEqual(validar_csv(
            gerar_csv([registro("a", motivo="")]), {"a"}, taxonomia(),
        )["linhas"], 1)

    def test_decisao_desconhecida_e_rejeitada_no_csv(self):
        with self.assertRaises(ValueError):
            validar_csv(gerar_csv([registro("a", "talvez")]), {"a"}, taxonomia())

    def test_gerador_e_validador_rejeitam_confianca_invalida(self):
        for p in (math.nan, math.inf, -math.inf, -0.01, 1.01, True, "0.8"):
            with self.subTest(p=p):
                with self.assertRaises(ValueError):
                    gerar_csv([registro("a", confianca=p)])
        for p in ("nan", "inf", "-inf", "-0.01", "1.01", "", "True", "oitenta"):
            with self.subTest(p=p):
                with self.assertRaises(ValueError):
                    validar_csv(csv_sem_validacao([registro("a", confianca=p)]), {"a"}, taxonomia())
        for p in (0, 1):
            validar_csv(gerar_csv([registro("a", confianca=p)]), {"a"}, taxonomia())

    def test_previsao_exclui_referencias_e_usa_apenas_publicadas_da_avaliacao(self):
        dados = lote()
        previsao, texto = gerar_previsao(dados, {"e0", "e1", "e2"}, reserva(), 2)
        self.assertEqual(previsao["avaliacao_total"], 3)
        self.assertEqual(previsao["referencias_excluidas"], 2)
        self.assertEqual(previsao["publicadas"], 2)
        self.assertEqual(previsao["precisao_prevista"], 0.5)
        self.assertEqual(previsao["cobertura_prevista"], 2 / 3)
        self.assertEqual(previsao["cobertura_intervalo"], {"inferior": 2 / 3, "superior": 2 / 3})
        self.assertEqual(previsao["decisoes_avaliacao"], {"publicar": 2, "revisar": 1, "fora": 0})
        self.assertIn("as 2 referências humanas foram excluídas", texto.decode("utf-8"))
        for r in dados:
            if r["id"].startswith("ref"):
                r["confianca"] = 0
                r["decisao"] = "revisar"
        outra, _ = gerar_previsao(dados, {"e0", "e1", "e2"}, reserva(), 2)
        self.assertEqual(outra, previsao)

    def test_cobertura_e_contagem_conhecida_inclusive_decisao_fora(self):
        dados = [registro("a"), registro("b", "revisar"), registro("c", "fora")]
        previsao, _ = gerar_previsao(dados, {"a", "b", "c"}, reserva(), 0)
        self.assertEqual(previsao["cobertura_prevista"], 1 / 3)
        self.assertEqual(previsao["cobertura_intervalo"]["inferior"], 1 / 3)
        self.assertEqual(previsao["cobertura_intervalo"]["superior"], 1 / 3)
        self.assertIn("Contagem conhecida", previsao["cobertura_metodo"])
        self.assertEqual(sum(previsao["decisoes_avaliacao"].values()), 3)

    def test_sem_publicadas_json_null_e_sentinela_txt_explicitamente_explicada(self):
        dados = [registro("a", "revisar"), registro("ref", confianca=1)]
        previsao, texto = gerar_previsao(dados, {"a"}, reserva(n=10, acertos=10), 1)
        texto = texto.decode("utf-8")
        self.assertIsNone(previsao["precisao_prevista"])
        self.assertIn('"precisao_prevista": null', json.dumps(previsao, allow_nan=False))
        self.assertEqual(previsao["publicadas"], 0)
        self.assertEqual(previsao["cobertura_prevista"], 0)
        self.assertTrue(previsao["precisao_txt_sentinela_zero"])
        self.assertEqual(previsao["precisao_intervalo"], {"inferior": 0.0, "superior": 1.0})
        self.assertIsNone(previsao["precisao_intervalo_nivel"])
        self.assertTrue(texto.startswith("precisao_prevista: 0.00000000\n"))
        self.assertIn("matematicamente indefinida", texto)
        self.assertIn("sentinela", texto)
        self.assertIn("não significa previsão de 0% de acerto", texto)
        self.assertIn("não é um intervalo de confiança calculado", texto)
        self.assertFalse(previsao["meta_95_comprovada"])

    def test_publicadas_sem_suporte_na_reserva_usam_dominio_sem_ic(self):
        previsao, texto = gerar_previsao([registro("a", confianca=0.8)], {"a"}, reserva(), 0)
        self.assertEqual(previsao["precisao_prevista"], 0.8)
        self.assertFalse(previsao["precisao_txt_sentinela_zero"])
        self.assertEqual(previsao["precisao_intervalo"], {"inferior": 0.0, "superior": 1.0})
        self.assertIsNone(previsao["precisao_intervalo_nivel"])
        self.assertIn("não é um intervalo de confiança", previsao["precisao_intervalo_natureza"])
        self.assertIn("0 acertos em 0 publicações", texto.decode("utf-8"))

    def test_intervalo_da_reserva_e_transportado_e_refit_nao_e_teste_independente(self):
        referencia = reserva(n=10, acertos=8)
        antes = deepcopy(referencia)
        previsao, texto = gerar_previsao([registro("a", confianca=0.97)], {"a"}, referencia, 0)
        texto = texto.decode("utf-8")
        self.assertEqual(previsao["precisao_intervalo"], wilson(8, 10))
        self.assertEqual(previsao["precisao_intervalo_nivel"], 0.95)
        self.assertEqual(previsao["precisao_prevista"], 0.97)
        self.assertIn("transportado sob hipótese", previsao["precisao_intervalo_natureza"])
        self.assertFalse(previsao["ajuste_final_testado_independentemente"])
        self.assertFalse(previsao["meta_95_comprovada"])
        self.assertIn("não recebeu outro teste independente", texto)
        self.assertIn("não é um intervalo calculado para a média das probabilidades", texto)
        self.assertEqual(referencia, antes)

    def test_previsao_rejeita_ids_ausentes_duplicados_e_denominador_incorreto(self):
        casos = [
            (lote(), {"e0", "e1", "ausente"}, 2),
            (lote() + [registro("e0")], {"e0", "e1", "e2"}, 2),
            (lote() + [registro("ref0")], {"e0", "e1", "e2"}, 3),
            (lote(), set(), 5),
            (lote(), {"e0", "e1", "e2"}, 1),
            (lote(), {"e0", "e1", "e2"}, -1),
        ]
        for dados, ids, excluidas in casos:
            with self.assertRaises(ValueError):
                gerar_previsao(dados, ids, reserva(), excluidas)

    def test_previsao_rejeita_probabilidades_nao_finitas_ou_fora_do_intervalo(self):
        for p in (math.nan, math.inf, -math.inf, -0.1, 1.1, True, "0.5"):
            with self.subTest(p=p):
                with self.assertRaises(ValueError):
                    gerar_previsao([registro("a", confianca=p)], {"a"}, reserva(), 0)

    def test_previsao_rejeita_decisoes_desconhecidas_e_contagem_de_referencias_invalida(self):
        for identificador in ("e0", "ref0"):
            dados = lote()
            next(r for r in dados if r["id"] == identificador)["decisao"] = "talvez"
            with self.assertRaises(ValueError):
                gerar_previsao(dados, {"e0", "e1", "e2"}, reserva(), 2)
        for excluidas in (True, 2.0, "2", math.nan, math.inf, -1):
            with self.assertRaises(ValueError):
                gerar_previsao(lote(), {"e0", "e1", "e2"}, reserva(), excluidas)

    def test_contagens_de_reserva_invalidas_sao_rejeitadas(self):
        for n, acertos in ((-1, 0), (10, -1), (10, 11), (True, 1), (10, True), (10.0, 8), (10, 8.0)):
            referencia = reserva(10, 8)
            referencia["geral"]["publicacao"].update(n=n, acertos=acertos)
            with self.assertRaises(ValueError):
                gerar_previsao([registro("a")], {"a"}, referencia, 0)

    def test_intervalos_de_reserva_nao_finitos_invertidos_ou_incompletos_sao_rejeitados(self):
        intervalos = [
            None, {}, {"inferior": 0.1},
            {"inferior": 0.1, "superior": 0.9, "extra": 1},
            {"inferior": 0.8, "superior": 0.2},
            {"inferior": -0.1, "superior": 0.9},
            {"inferior": 0.1, "superior": 1.1},
            {"inferior": math.nan, "superior": 0.9},
            {"inferior": 0.1, "superior": math.inf},
            {"inferior": False, "superior": 0.9},
        ]
        for intervalo in intervalos:
            referencia = reserva(10, 8)
            referencia["geral"]["publicacao"]["intervalo_wilson_95"] = intervalo
            with self.assertRaises(ValueError):
                gerar_previsao([registro("a")], {"a"}, referencia, 0)

    def test_reserva_sem_suporte_nao_aceita_intervalo_estatistico_inventado(self):
        referencia = reserva()
        referencia["geral"]["publicacao"]["intervalo_wilson_95"] = {
            "inferior": 0.0, "superior": 1.0,
        }
        with self.assertRaises(ValueError):
            gerar_previsao([registro("a")], {"a"}, referencia, 0)


if __name__ == "__main__":
    unittest.main()
