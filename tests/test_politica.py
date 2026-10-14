import copy
import unittest

from classificacao_topicos.politica import aplicar_politica


def sugestao(**alteracoes):
    resultado = {"id": "Q0001", "tema_central_id": "T001", "extras_ids": [],
                 "temas_alternativos": [], "sem_tema": False,
                 "confianca_autodeclarada": 0.95, "motivo": "O texto sustenta este tema.",
                 "evidencia": "trecho literal", "requer_revisao": False}
    resultado.update(alteracoes)
    return resultado


class PoliticaTests(unittest.TestCase):
    def setUp(self):
        self.temas = {
            "T000": {"tema_id": "T000", "nivel": "0", "parent_id": "", "status": "active"},
            "T001": {"tema_id": "T001", "nivel": "1", "parent_id": "T000", "status": "active"},
            "T002": {"tema_id": "T002", "nivel": "2", "parent_id": "T001", "status": "active"},
            "T003": {"tema_id": "T003", "nivel": "1", "parent_id": "T000", "status": "active"},
            "T004": {"tema_id": "T004", "nivel": "1", "parent_id": "T000", "status": "inactive"},
        }

    def aplicar(self, resposta=None, ambiguos=None, **parametros):
        return aplicar_politica(resposta if resposta is not None else sugestao(), self.temas,
                                ambiguos if ambiguos is not None else set(), **parametros)

    def test_limiar_inclusivo_nao_converte_confianca_em_estimativa_de_precisao(self):
        publicacao = self.aplicar()
        self.assertEqual(publicacao, {"estado": "decidido", "decisao": "publicar",
                                     "tema_central_id": "T001", "extras_ids": [],
                                     "confianca": 0.95, "motivo": "", "sinais": []})
        revisao = self.aplicar(sugestao(confianca_autodeclarada=0.949))
        self.assertEqual(revisao["decisao"], "revisar")
        self.assertEqual(revisao["sinais"], ["confianca_abaixo_limiar"])
        self.assertEqual(revisao["confianca"], 0.949)
        self.assertIn("O texto sustenta este tema.", revisao["motivo"])

    def test_sem_tema_sempre_exige_confirmacao_separada_sem_central_ficticio(self):
        for confianca in (0, 0.949, 0.95, 1):
            for requer_revisao in (False, True):
                resposta = sugestao(tema_central_id="", sem_tema=True,
                                     confianca_autodeclarada=confianca, requer_revisao=requer_revisao)
                with self.subTest(confianca=confianca, requer_revisao=requer_revisao):
                    resultado = self.aplicar(resposta)
                    self.assertEqual(resultado["estado"], "pendente_confirmacao_fora")
                    self.assertIsNone(resultado["decisao"])
                    self.assertEqual(resultado["tema_central_id"], "")
                    self.assertEqual(resultado["extras_ids"], [])
                    self.assertEqual(resultado["sinais"], ["sem_tema_sem_confirmacao"])

    def test_cada_sinal_basta_para_revisar(self):
        casos = (
            (sugestao(requer_revisao=True), set(), "revisao_solicitada"),
            (sugestao(temas_alternativos=["T002"]), set(), "temas_alternativos"),
            (sugestao(tema_central_id="T000"), set(), "tema_raiz"),
            (sugestao(), {"T001"}, "tema_ambiguo"),
            (sugestao(extras_ids=["T002", "T003"]), set(), "excesso_extras"),
        )
        for resposta, ambiguos, sinal in casos:
            with self.subTest(sinal=sinal):
                resultado = self.aplicar(resposta, ambiguos)
                self.assertEqual(resultado["estado"], "decidido")
                self.assertEqual(resultado["decisao"], "revisar")
                self.assertEqual(resultado["sinais"], [sinal])
                self.assertTrue(resultado["motivo"])

    def test_ambiguidade_so_no_central_sem_propagar_ancestrais_ou_extras(self):
        resultado = self.aplicar(sugestao(extras_ids=["T003"]), {"T000", "T002", "T003"})
        self.assertEqual(resultado["decisao"], "publicar")
        self.assertEqual(resultado["extras_ids"], ["T003"])
        self.assertEqual(resultado["sinais"], [])

    def test_extras_preservados_e_limite_configuravel(self):
        resposta = sugestao(extras_ids=["T002"])
        self.assertEqual(self.aplicar(resposta)["decisao"], "publicar")
        restrito = self.aplicar(resposta, max_extras_publicar=0)
        self.assertEqual(restrito["decisao"], "revisar")
        self.assertEqual(restrito["extras_ids"], ["T002"])
        self.assertEqual(self.aplicar(sugestao(extras_ids=["T002", "T003"]),
                                      max_extras_publicar=2)["decisao"], "publicar")

    def test_sinais_combinados_mantem_motivo_original_e_ordem_estavel(self):
        resposta = sugestao(tema_central_id="T000", requer_revisao=True,
                             confianca_autodeclarada=0.7, temas_alternativos=["T001"],
                             extras_ids=["T002", "T003"])
        resultado = self.aplicar(resposta, {"T000"})
        self.assertEqual(resultado["sinais"], ["revisao_solicitada", "confianca_abaixo_limiar",
                                               "temas_alternativos", "tema_raiz", "tema_ambiguo", "excesso_extras"])
        self.assertTrue(resultado["motivo"].endswith(resposta["motivo"]))

    def test_confianca_minima_validacao_estrita_e_limites_validos(self):
        for limiar in (True, False, float("nan"), float("inf"), -float("inf"), -0.1, 1.1, 10 ** 1000, "0.95", None):
            with self.subTest(limiar=limiar), self.assertRaises(ValueError):
                self.aplicar(confianca_minima=limiar)
        self.assertEqual(self.aplicar(sugestao(confianca_autodeclarada=0), confianca_minima=0)["decisao"], "publicar")
        self.assertEqual(self.aplicar(sugestao(confianca_autodeclarada=1), confianca_minima=1)["decisao"], "publicar")

    def test_limite_extras_rejeita_booleano_fracionario_e_nao_finito(self):
        for limite in (True, False, -1, 1.0, 1.5, float("nan"), float("inf"), "1", None):
            with self.subTest(limite=limite), self.assertRaises(ValueError):
                self.aplicar(max_extras_publicar=limite)

    def test_ids_inativos_ou_inexistentes_nao_viram_decisao(self):
        for identificador in ("T004", "INEXISTENTE"):
            for campo in ("tema_central_id", "extras_ids", "temas_alternativos"):
                resposta = sugestao(**{campo: identificador if campo == "tema_central_id" else [identificador]})
                with self.subTest(identificador=identificador, campo=campo), self.assertRaises(ValueError):
                    self.aplicar(resposta)

    def test_configuracao_ambigua_exige_conjunto_de_ids_ativos(self):
        for ambiguos in (["T001"], "T001", {1}, {""}, {"T004"}, {"INEXISTENTE"}):
            with self.subTest(ambiguos=ambiguos), self.assertRaises(ValueError):
                self.aplicar(ambiguos=ambiguos)

    def test_contrato_invalido_rejeitado_antes_das_decisoes(self):
        casos = [sugestao(sem_tema=True), sugestao(tema_central_id=""),
                 sugestao(confianca_autodeclarada=True), sugestao(confianca_autodeclarada=float("nan")),
                 sugestao(extras_ids=["T001"]), sugestao(id=""), sugestao(motivo=" ")]
        for resposta in casos:
            with self.subTest(resposta=resposta), self.assertRaises(ValueError):
                self.aplicar(resposta)
        with self.assertRaises(ValueError):
            aplicar_politica([], self.temas, set())

    def test_nivel_zero_inteiro_e_metadado_invalido(self):
        self.temas["T000"]["nivel"] = 0
        self.assertEqual(self.aplicar(sugestao(tema_central_id="T000"))["sinais"], ["tema_raiz"])
        for nivel in (False, None, -1, "-1", "raiz", 0.5):
            self.temas["T001"]["nivel"] = nivel
            with self.subTest(nivel=nivel), self.assertRaises(ValueError):
                self.aplicar()

    def test_entradas_nao_sao_mutadas_e_extras_retornados_sao_copia(self):
        resposta = sugestao(extras_ids=["T002"])
        original, temas_originais = copy.deepcopy(resposta), copy.deepcopy(self.temas)
        resultado = self.aplicar(resposta)
        resultado["extras_ids"].append("T003")
        self.assertEqual(resposta, original)
        self.assertEqual(self.temas, temas_originais)


if __name__ == "__main__":
    unittest.main()
