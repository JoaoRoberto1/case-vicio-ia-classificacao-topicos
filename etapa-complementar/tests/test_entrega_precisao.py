"""Exportação oficial com 659 IDs e estatísticas inteiramente sintéticos."""

from copy import deepcopy
import csv
import io
import json
import unittest

from classificacao_decisao.calibracao import wilson
from classificacao_decisao.entrega import COLUNAS, validar_csv
from classificacao_precisao.entrega import construir_entrega


def _json(objeto):
    return (json.dumps(objeto, ensure_ascii=False) + "\n").encode("utf-8")


def _jsonl(registros):
    return b"".join(_json(r) for r in registros)


def _ler_linhas(conteudo):
    return [json.loads(linha) for linha in conteudo.decode("utf-8").splitlines() if linha]


def cenario(*, habilitada=False, n=10, k=9, publicadas_avaliacao=0, publicadas_reserva=0,
            receita="sinais_small"):
    qs = [{"id": f"sintetica_{i:04d}"} for i in range(659)]
    temas = [{"tema_id": "0", "status": "active", "nivel": "0"},
             {"tema_id": "11", "status": "active", "nivel": "1"},
             {"tema_id": "12", "status": "inactive", "nivel": "1"}]
    tax = {"por_id": {t["tema_id"]: t for t in temas}, "registros": temas}
    grupos = []
    for inicio, fim, quantidade, campo in ((0, 80, n, "publicaria"),
                                          (80, 100, publicadas_reserva, "publicaria_politica_candidata"),
                                          (100, 659, publicadas_avaliacao, "publicaria_politica_candidata")):
        grupos.append([{"id": qs[i]["id"], "tema_sugerido_id": "11", "receita": receita,
                        "confianca": 0.6 + (i % 20) / 100, campo: i - inicio < quantidade}
                       for i in range(inicio, fim)])
    externa = {"count": 80, "n": n, "k": k, "coverage": n / 80,
               "precision": k / n if n else None, "wilson95": wilson(k, n)}
    produtos = {
        "predicoes_aninhadas.jsonl": _jsonl(grupos[0]),
        "predicoes_reserva_conhecida.jsonl": _jsonl(grupos[1]),
        "sugestoes_avaliacao.jsonl": _jsonl(grupos[2]),
        "politica.json": _json({"habilitada": habilitada, "receita": receita}),
        "metricas.json": _json({"selecao_aninhada": {"publicacao": externa}}),
    }
    return produtos, qs, tax


class EntregaPrecisaoTests(unittest.TestCase):
    def test_659_linhas_reutilizam_contrato_csv_e_preservam_sugestao(self):
        produtos, qs, tax = cenario()
        entrega = construir_entrega(produtos, qs, tax)
        self.assertEqual(set(entrega), {"publicacao.csv", "previsao.txt", "previsao.json"})
        self.assertTrue(all(isinstance(v, bytes) for v in entrega.values()))
        resultado = validar_csv(entrega["publicacao.csv"], {q["id"] for q in qs}, tax)
        self.assertEqual(resultado, {"linhas": 659, "decisoes": {"revisar": 659}})
        leitor = csv.DictReader(io.StringIO(entrega["publicacao.csv"].decode("utf-8")))
        self.assertEqual(leitor.fieldnames, COLUNAS)
        for linha in leitor:
            self.assertEqual(linha["tema_central_id"], "11")
            self.assertEqual(linha["extras_ids"], "")
            self.assertEqual(len(linha["confianca"].split(".")[1]), 8)
            self.assertTrue(linha["motivo"])

    def test_politica_desabilitada_governa_todas_as_procedencias(self):
        produtos, qs, tax = cenario(n=80, k=70, publicadas_avaliacao=559, publicadas_reserva=20)
        entrega = construir_entrega(produtos, qs, tax)
        previsao = json.loads(entrega["previsao.json"])
        self.assertEqual(previsao["contrato_csv"]["decisoes"], {"revisar": 659})
        self.assertEqual(previsao["publicacoes_por_procedencia"], {
            "selecao_aninhada": 0, "reserva_conhecida_modelo80": 0, "avaliacao_modelo100": 0,
        })
        self.assertEqual(previsao["referencia_selecao_aninhada"]["n"], 80)
        self.assertEqual(previsao["publicadas"], 0)
        self.assertIsNone(previsao["precisao_prevista"])
        self.assertIsNone(previsao["media_confianca_publicadas"])
        self.assertIsNone(previsao["precisao_intervalo"])
        self.assertFalse(previsao["precisao_prevista_e_extrapolacao"])

    def test_publicacao_exclui_100_referencias_do_denominador(self):
        produtos, qs, tax = cenario(habilitada=True, n=20, k=19,
                                   publicadas_avaliacao=7, publicadas_reserva=5)
        entrega = construir_entrega(produtos, qs, tax)
        previsao = json.loads(entrega["previsao.json"])
        self.assertEqual(previsao["universo_csv"], 659)
        self.assertEqual(previsao["avaliacao_total"], 559)
        self.assertEqual(previsao["referencias_excluidas"], 100)
        self.assertEqual(previsao["publicadas"], 7)
        self.assertAlmostEqual(previsao["cobertura_prevista"], 7 / 559)
        self.assertEqual(previsao["cobertura_intervalo"], {"inferior": 7 / 559, "superior": 7 / 559})
        self.assertEqual(previsao["contrato_csv"]["decisoes"], {"publicar": 32, "revisar": 627})
        self.assertEqual(previsao["procedencias_csv"], {
            "selecao_aninhada": 80, "reserva_conhecida_modelo80": 20, "avaliacao_modelo100": 559,
        })

    def test_precisao_observada_extrapolada_e_media_confianca_sao_separadas(self):
        produtos, qs, tax = cenario(habilitada=True, n=20, k=19, publicadas_avaliacao=7)
        previsao = json.loads(construir_entrega(produtos, qs, tax)["previsao.json"])
        self.assertIsNone(previsao["precisao_observada_avaliacao"])
        self.assertEqual(previsao["precisao_prevista"], 0.95)
        self.assertTrue(previsao["precisao_prevista_e_extrapolacao"])
        self.assertAlmostEqual(previsao["media_confianca_publicadas"], 0.63)
        self.assertNotEqual(previsao["media_confianca_publicadas"], previsao["precisao_prevista"])
        self.assertEqual(previsao["precisao_intervalo"], wilson(19, 20))
        self.assertFalse(previsao["meta_95_comprovada"])
        self.assertFalse(previsao["ajuste_final_testado_independentemente"])
        self.assertTrue(previsao["referencias_reutilizadas"])
        self.assertTrue(previsao["criterio_empirico_95_atendido_na_selecao_aninhada"])
        self.assertTrue(any("20" in t and "conhecidas" in t for t in previsao["qualificacoes_avaliacao"]))

    def test_sem_publicacoes_na_avaliacao_precision_permanece_null(self):
        produtos, qs, tax = cenario(habilitada=True, n=10, k=10, publicadas_avaliacao=0)
        previsao = json.loads(construir_entrega(produtos, qs, tax)["previsao.json"])
        self.assertTrue(previsao["politica_habilitada"])
        self.assertEqual(previsao["publicadas"], 0)
        self.assertEqual(previsao["cobertura_prevista"], 0.0)
        self.assertIsNone(previsao["precisao_prevista"])
        self.assertIsNone(previsao["precisao_intervalo"])
        self.assertIsNone(previsao["media_confianca_publicadas"])

    def test_nenhuma_publicacao_externa_nao_inventa_estimativa(self):
        produtos, qs, tax = cenario(n=0, k=0)
        previsao = json.loads(construir_entrega(produtos, qs, tax)["previsao.json"])
        self.assertIsNone(previsao["referencia_selecao_aninhada"]["precision"])
        self.assertIsNone(previsao["referencia_selecao_aninhada"]["wilson95"])
        self.assertFalse(previsao["criterio_empirico_95_atendido_na_selecao_aninhada"])

    def test_qualificacao_distingue_rrf_fixo_de_ranking_ajustado_com100(self):
        for receita in ("large_rrf20", "sinais_small"):
            with self.subTest(receita=receita):
                produtos, qs, tax = cenario(receita=receita)
                entrega = construir_entrega(produtos, qs, tax)
                previsao = json.loads(entrega["previsao.json"])
                texto = entrega["previsao.txt"].decode("utf-8")
                aprendido = receita != "large_rrf20"
                self.assertIs(previsao["ranking_aprendido_com100"], aprendido)
                if aprendido:
                    self.assertIn("ranking reajustado com 100 referências", texto)
                else:
                    self.assertIn("ranking RRF fixo, sem pesos aprendidos", texto)
                    self.assertIn("20 somente no diagnóstico conhecido", texto)
                    self.assertIn("rótulos das 20 não escolhem o RRF", texto)
                    self.assertNotIn("ranking reajustado com 100 referências", texto)

    def test_txt_sem_publicacao_preserva_quatro_linhas_e_explica_sentinela(self):
        produtos, qs, tax = cenario()
        entrega = construir_entrega(produtos, qs, tax)
        texto = entrega["previsao.txt"].decode("utf-8")
        self.assertEqual(texto.splitlines()[:4], [
            "precisao_prevista: 0.00000000", "precisao_intervalo: 0.00000000-1.00000000",
            "cobertura_prevista: 0.00000000", "cobertura_intervalo: 0.00000000-0.00000000",
        ])
        self.assertIn("sentinela", texto)
        self.assertIn("não é um intervalo de confiança estimado", texto)
        previsao = json.loads(entrega["previsao.json"])
        self.assertTrue(previsao["precisao_txt_sentinela_zero"])
        self.assertIsNone(previsao["precisao_prevista"])
        self.assertIsNone(previsao["precisao_intervalo"])

    def test_txt_publicacao_usa_extrapolacao_e_nao_media_das_confiancas(self):
        produtos, qs, tax = cenario(habilitada=True, n=20, k=19, publicadas_avaliacao=7)
        entrega = construir_entrega(produtos, qs, tax)
        texto = entrega["previsao.txt"].decode("utf-8")
        self.assertEqual(texto.splitlines()[0], "precisao_prevista: 0.95000000")
        self.assertIn("19 acertos em 20 publicações", texto)
        self.assertIn("0.63000000", texto)
        self.assertIn("não constituem holdout independente novo", texto)
        self.assertFalse(json.loads(entrega["previsao.json"])["precisao_txt_sentinela_zero"])

    def test_bloqueia_politica_habilitada_sem_suporte_ou_precisao_externa(self):
        for n, k in ((0, 0), (9, 9), (20, 18)):
            produtos, qs, tax = cenario(habilitada=True, n=n, k=k, publicadas_avaliacao=1)
            with self.subTest(n=n, k=k), self.assertRaisesRegex(ValueError, "suporte mínimo"):
                construir_entrega(produtos, qs, tax)

    def test_receitas_aninhadas_podem_variar_mas_finais_devem_corresponder(self):
        produtos, qs, tax = cenario()
        ps = _ler_linhas(produtos["predicoes_aninhadas.jsonl"])
        ps[0]["receita"] = "baseline_m7"
        produtos["predicoes_aninhadas.jsonl"] = _jsonl(ps)
        construir_entrega(produtos, qs, tax)
        for nome in ("predicoes_reserva_conhecida.jsonl", "sugestoes_avaliacao.jsonl"):
            alterados = deepcopy(produtos)
            ps = _ler_linhas(alterados[nome])
            ps[0]["receita"] = "baseline_m7"
            alterados[nome] = _jsonl(ps)
            with self.assertRaisesRegex(ValueError, "diverge da política"):
                construir_entrega(alterados, qs, tax)

    def test_rotulos_metadados_e_extras_nao_decidem_publicacao_ou_fora(self):
        produtos, qs, tax = cenario(habilitada=True, n=10, k=10, publicadas_avaliacao=1)
        esperado = construir_entrega(produtos, qs, tax)
        for nome in ("predicoes_aninhadas.jsonl", "predicoes_reserva_conhecida.jsonl", "sugestoes_avaliacao.jsonl"):
            ps = _ler_linhas(produtos[nome])
            for p in ps:
                p.update({"acertos": {"ramo": False}, "fora_da_taxonomia": True,
                          "tema_central_id": "12", "extras_ids": ["12"], "gabarito": "Z"})
            produtos[nome] = _jsonl(ps)
        for q in qs:
            q.update({"enunciado": "texto ignorado", "tema_central_id": "12", "gabarito": "Z"})
        self.assertEqual(construir_entrega(produtos, qs, tax), esperado)

    def test_ids_duplicados_desconhecidos_e_sobrepostos_sao_recusados(self):
        produtos, qs, tax = cenario()
        for id_substituto in ("desconhecido", qs[0]["id"], qs[100]["id"]):
            alterados = deepcopy(produtos)
            ps = _ler_linhas(alterados["sugestoes_avaliacao.jsonl"])
            ps[1]["id"] = id_substituto
            alterados["sugestoes_avaliacao.jsonl"] = _jsonl(ps)
            with self.assertRaisesRegex(ValueError, "IDs conhecidos"):
                construir_entrega(alterados, qs, tax)

    def test_quantidades_exatas_das_tres_procedencias_sao_obrigatorias(self):
        produtos, qs, tax = cenario()
        for nome in ("predicoes_aninhadas.jsonl", "predicoes_reserva_conhecida.jsonl", "sugestoes_avaliacao.jsonl"):
            alterados = deepcopy(produtos)
            alterados[nome] = _jsonl(_ler_linhas(alterados[nome])[:-1])
            with self.assertRaisesRegex(ValueError, "exatamente"):
                construir_entrega(alterados, qs, tax)
        with self.assertRaisesRegex(ValueError, "659"):
            construir_entrega(produtos, qs[:-1], tax)
        qs[-1]["id"] = qs[0]["id"]
        with self.assertRaisesRegex(ValueError, "659"):
            construir_entrega(produtos, qs, tax)

    def test_tema_sugerido_inativo_raiz_ausente_ou_desconhecido_e_recusado(self):
        produtos, qs, tax = cenario()
        for tema in ("12", "0", "999", None):
            alterados = deepcopy(produtos)
            ps = _ler_linhas(alterados["sugestoes_avaliacao.jsonl"])
            ps[0]["tema_sugerido_id"] = tema
            alterados["sugestoes_avaliacao.jsonl"] = _jsonl(ps)
            with self.assertRaisesRegex(ValueError, "Tema central"):
                construir_entrega(alterados, qs, tax)

    def test_confianças_invalidas_sao_recusadas(self):
        produtos, qs, tax = cenario()
        for valor in (float("nan"), float("inf"), True, -0.1, 1.1, None):
            alterados = deepcopy(produtos)
            ps = _ler_linhas(alterados["sugestoes_avaliacao.jsonl"])
            ps[0]["confianca"] = valor
            alterados["sugestoes_avaliacao.jsonl"] = _jsonl(ps)
            with self.subTest(valor=valor), self.assertRaises(ValueError):
                construir_entrega(alterados, qs, tax)

    def test_flags_de_publicacao_e_habilitacao_devem_ser_booleanos(self):
        produtos, qs, tax = cenario()
        for valor in (1, "true", None):
            alterados = deepcopy(produtos)
            ps = _ler_linhas(alterados["predicoes_aninhadas.jsonl"])
            ps[0]["publicaria"] = valor
            alterados["predicoes_aninhadas.jsonl"] = _jsonl(ps)
            with self.assertRaisesRegex(ValueError, "booleano"):
                construir_entrega(alterados, qs, tax)
            alterados = deepcopy(produtos)
            alterados["politica.json"] = _json({"habilitada": valor, "receita": "sinais_small"})
            with self.assertRaisesRegex(ValueError, "booleano"):
                construir_entrega(alterados, qs, tax)

    def test_decisoes_aninhadas_devem_corresponder_ao_suporte_das_metricas(self):
        produtos, qs, tax = cenario()
        ps = _ler_linhas(produtos["predicoes_aninhadas.jsonl"])
        ps[0]["publicaria"] = False
        produtos["predicoes_aninhadas.jsonl"] = _jsonl(ps)
        with self.assertRaisesRegex(ValueError, "divergem das contagens"):
            construir_entrega(produtos, qs, tax)

    def test_metricas_com_contagens_taxas_ou_intervalos_inconsistentes_sao_recusadas(self):
        produtos, qs, tax = cenario()
        for campo, valor in (("count", 100), ("n", True), ("k", 11), ("coverage", 0.9),
                             ("precision", 0.95), ("wilson95", {"inferior": 0.0, "superior": 1.0})):
            alterados = deepcopy(produtos)
            metrica = json.loads(alterados["metricas.json"])
            metrica["selecao_aninhada"]["publicacao"][campo] = valor
            alterados["metricas.json"] = _json(metrica)
            with self.subTest(campo=campo), self.assertRaises(ValueError):
                construir_entrega(alterados, qs, tax)

    def test_produtos_ausentes_nao_utf8_json_invalido_e_tipos_errados_falham(self):
        produtos, qs, tax = cenario()
        for valor in (None, "texto", b"\xff", b"{} lixo", b"[]"):
            alterados = deepcopy(produtos)
            alterados["politica.json"] = valor
            with self.assertRaises(ValueError):
                construir_entrega(alterados, qs, tax)
        del produtos["sugestoes_avaliacao.jsonl"]
        with self.assertRaises(ValueError):
            construir_entrega(produtos, qs, tax)

    def test_sem_escrita_sem_mutacao_e_bytes_deterministicos(self):
        produtos, qs, tax = cenario(habilitada=True, n=20, k=19, publicadas_avaliacao=7)
        originais = deepcopy((produtos, qs, tax))
        esperado = construir_entrega(produtos, qs, tax)
        self.assertEqual((produtos, qs, tax), originais)
        self.assertEqual(construir_entrega(produtos, qs, tax), esperado)
        for nome in ("predicoes_aninhadas.jsonl", "predicoes_reserva_conhecida.jsonl", "sugestoes_avaliacao.jsonl"):
            produtos[nome] = _jsonl(list(reversed(_ler_linhas(produtos[nome]))))
        self.assertEqual(construir_entrega(produtos, list(reversed(qs)), tax), esperado)


if __name__ == "__main__":
    unittest.main()
