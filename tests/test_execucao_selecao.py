"""Escopo opcional de lote, com manifesto completo e provedor simulado."""

import json
import unittest
from unittest.mock import patch

from tests import test_execucao


class ExecucaoSelecaoTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_execucao.ExecucaoTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_selecao_preserva_ordem_do_manifesto_e_artefatos_completos(self):
        f = self.fixture
        f.entradas = [f.entradas[2], f.entradas[0], f.entradas[1]]
        f.gravar_piloto()
        f.converter_para_lote()
        originais = {p: p.read_bytes() for pasta in (f.preparacao, f.piloto)
                     for p in pasta.iterdir()}
        ids = ["Q0002", "Q0003"]
        with patch("classificacao_topicos.execucao.gerar_json", side_effect=[
                test_execucao.retorno("Q0003"), test_execucao.retorno("Q0002")]) as gerar:
            resumo = f.executar_lote(ids_selecionados=ids, limite=2)
        self.assertEqual([c.args[0] for c in gerar.call_args_list], ["Analise Q0003", "Analise Q0002"])
        self.assertEqual(ids, ["Q0002", "Q0003"])
        self.assertEqual(resumo["ids_selecionados"], ["Q0003", "Q0002"])
        self.assertEqual((resumo["total_lote"], resumo["total_escopo"], resumo["total"]), (3, 2, 2))
        self.assertEqual((resumo["novas"], resumo["sucesso"], resumo["pendencia"]), (2, 2, 0))
        self.assertEqual({p.name for p in f.saida.iterdir()}, {"Q0002.json", "Q0003.json"})
        self.assertEqual({p: p.read_bytes() for p in originais}, originais)

    def test_limite_e_pendencias_se_referem_apenas_ao_escopo(self):
        f = self.fixture
        f.converter_para_lote()
        with patch("classificacao_topicos.execucao.gerar_json", return_value=test_execucao.retorno()) as gerar:
            resumo = f.executar_lote(ids_selecionados=["Q0003", "Q0001"])
        gerar.assert_called_once()
        self.assertEqual((resumo["total"], resumo["novas"], resumo["cache"], resumo["pendencia"]), (2, 1, 0, 1))
        self.assertFalse((f.saida / "Q0002.json").exists())
        self.assertFalse((f.saida / "Q0003.json").exists())

    def test_cache_completo_no_escopo_nao_repete_erro_fora_dele(self):
        f = self.fixture
        f.converter_para_lote()
        invalida = test_execucao.sugestao("Q0002")
        invalida["evidencia"] = "Frase ausente."
        with patch("classificacao_topicos.execucao.gerar_json", side_effect=[
                test_execucao.retorno(), test_execucao.retorno(resposta=invalida),
                test_execucao.retorno("Q0003")]):
            f.executar_lote(limite=3, continuar_erros_validacao=True)
        originais = {p: p.read_bytes() for p in f.saida.iterdir()}
        with patch("classificacao_topicos.execucao.gerar_json") as gerar:
            resumo = f.executar_lote(ids_selecionados=["Q0001", "Q0003"], limite=2)
        gerar.assert_not_called()
        self.assertEqual((resumo["novas"], resumo["cache"], resumo["pendencia"]), (0, 2, 0))
        self.assertEqual(resumo["erros_validacao_ids"], [])
        self.assertFalse(resumo["concluido_com_falhas"])
        self.assertEqual(resumo["tentativas_registradas"], 2)
        self.assertEqual(resumo["tokens_observados"]["totalTokenCount"], 300)
        self.assertEqual({p: p.read_bytes() for p in originais}, originais)

    def test_retomada_de_erro_selecionado_preserva_historico_e_recibos_fora_do_escopo(self):
        f = self.fixture
        f.converter_para_lote()
        invalida = test_execucao.sugestao("Q0002")
        invalida["evidencia"] = "Frase ausente."
        with patch("classificacao_topicos.execucao.gerar_json", side_effect=[
                test_execucao.retorno(), test_execucao.retorno(resposta=invalida),
                test_execucao.retorno("Q0003")]):
            f.executar_lote(limite=3, continuar_erros_validacao=True)
        originais = {p.name: p.read_bytes() for p in f.saida.iterdir()}
        with patch("classificacao_topicos.execucao.gerar_json", return_value=test_execucao.retorno("Q0002")) as gerar:
            resumo = f.executar_lote(ids_selecionados=["Q0002"])
        gerar.assert_called_once()
        self.assertEqual(gerar.call_args.args[0], "Analise Q0002")
        registro = json.loads((f.saida / "Q0002.json").read_bytes())
        self.assertEqual(registro["numero_tentativa"], 2)
        self.assertEqual(registro["tentativas_anteriores"], [json.loads(originais["Q0002.json"])])
        for nome in ("Q0001.json", "Q0003.json"):
            self.assertEqual((f.saida / nome).read_bytes(), originais[nome])
        self.assertEqual((resumo["cache"], resumo["novas"], resumo["sucesso"], resumo["pendencia"]), (0, 1, 1, 0))
        self.assertEqual(resumo["tentativas_registradas"], 2)
        self.assertEqual(resumo["tokens_observados"]["totalTokenCount"], 300)

    def test_pedido_invalido_falha_antes_de_credenciais_api_ou_saida(self):
        f = self.fixture
        f.converter_para_lote()
        pedidos = ([], {}, "Q0001", ("Q0001",), [None], [1], [True], [["Q0001"]],
                   ["Q0001", "Q0001"], ["Q9999"], ["../Q0001"], ["q0001"])
        for ids in pedidos:
            with self.subTest(ids=ids), patch("classificacao_topicos.execucao.carregar_configuracao") as config, \
                    patch("classificacao_topicos.execucao.gerar_json") as gerar:
                with self.assertRaisesRegex(ValueError, "ids_selecionados"):
                    f.executar_lote(ids_selecionados=ids)
                config.assert_not_called()
                gerar.assert_not_called()
                self.assertFalse(f.saida.exists())

    def test_limite_nao_pode_exceder_escopo(self):
        f = self.fixture
        f.converter_para_lote()
        with patch("classificacao_topicos.execucao.carregar_configuracao") as config, \
                patch("classificacao_topicos.execucao.gerar_json") as gerar:
            with self.assertRaisesRegex(ValueError, "escopo selecionado"):
                f.executar_lote(ids_selecionados=["Q0002"], limite=2)
            config.assert_not_called()
            gerar.assert_not_called()
        self.assertFalse(f.saida.exists())

    def test_selecao_nao_permite_manifesto_de_lote_incompleto(self):
        f = self.fixture
        f.entradas.pop()
        f.gravar_piloto()
        f.converter_para_lote()
        with patch("classificacao_topicos.execucao.gerar_json") as gerar:
            with self.assertRaisesRegex(ValueError, "todas as questões"):
                f.executar_lote(ids_selecionados=["Q0001"])
            gerar.assert_not_called()
        self.assertFalse(f.saida.exists())

    def test_cache_adulterado_fora_do_escopo_ainda_bloqueia_chamada(self):
        f = self.fixture
        f.converter_para_lote()
        with patch("classificacao_topicos.execucao.gerar_json", return_value=test_execucao.retorno()):
            f.executar_lote()
        caminho = f.saida / "Q0001.json"
        registro = json.loads(caminho.read_bytes())
        registro["sugestao"]["motivo"] = "Adulterado."
        test_execucao.escrever_json(caminho, registro)
        original = caminho.read_bytes()
        with patch("classificacao_topicos.execucao.gerar_json") as gerar:
            with self.assertRaisesRegex(ValueError, "Checksum"):
                f.executar_lote(ids_selecionados=["Q0002"])
            gerar.assert_not_called()
        self.assertEqual(caminho.read_bytes(), original)
        self.assertFalse((f.saida / "Q0002.json").exists())
        self.assertFalse((f.saida / ".execucao.lock").exists())

    def test_revalidacao_reutilizada_e_contada_somente_dentro_do_escopo(self):
        from classificacao_topicos.execucao import _validar_entradas, _hash_bytes, _canonico
        from classificacao_topicos.piloto import esquema_resposta
        from classificacao_topicos.revalidacao import revalidar_recibo
        f = self.fixture
        f.converter_para_lote()
        with patch("classificacao_topicos.execucao.gerar_json", return_value=test_execucao.retorno()), \
                patch("classificacao_topicos.execucao._validar_evidencia", side_effect=ValueError("Validação anterior")):
            f.executar_lote()
        caminho = f.saida / "Q0001.json"
        registro = json.loads(caminho.read_bytes())
        entradas, temas, questoes, hash_preparacao, _ = _validar_entradas(f.piloto, f.preparacao)
        revalidar_recibo(caminho, registro, entradas[0], "gemini-3.8-flash",
                        _hash_bytes(_canonico(esquema_resposta())), hash_preparacao, temas, questoes["Q0001"])
        originais = {p: p.read_bytes() for p in f.saida.iterdir()}
        with patch("classificacao_topicos.execucao.gerar_json") as gerar:
            resumo = f.executar_lote(ids_selecionados=["Q0001"])
        gerar.assert_not_called()
        self.assertEqual((resumo["cache"], resumo["novas"], resumo["pendencia"]), (1, 0, 0))
        self.assertEqual(resumo["revalidacoes_ids"], ["Q0001"])
        self.assertEqual(resumo["tentativas_registradas"], 1)
        self.assertEqual(resumo["tokens_observados"]["totalTokenCount"], 150)
        with patch("classificacao_topicos.execucao.gerar_json", return_value=test_execucao.retorno("Q0002")) as gerar:
            resumo = f.executar_lote(ids_selecionados=["Q0002"])
        gerar.assert_called_once()
        self.assertEqual(resumo["revalidacoes_ids"], [])
        self.assertEqual((resumo["cache"], resumo["novas"], resumo["tentativas_registradas"]), (0, 1, 1))
        self.assertEqual(resumo["tokens_observados"]["totalTokenCount"], 150)
        self.assertEqual({p: p.read_bytes() for p in originais}, originais)

    def test_sem_selecao_preserva_contrato_do_resumo(self):
        f = self.fixture
        f.converter_para_lote()
        with patch("classificacao_topicos.execucao.gerar_json", return_value=test_execucao.retorno()):
            resumo = f.executar_lote()
            f.saida = f.raiz / "artefatos" / "outra-execucao"
            explicito = f.executar_lote(ids_selecionados=None)
        self.assertEqual(resumo, explicito)
        self.assertEqual(resumo["total"], 3)
        self.assertNotIn("total_lote", resumo)
        self.assertNotIn("total_escopo", resumo)
        self.assertNotIn("ids_selecionados", resumo)


if __name__ == "__main__":
    unittest.main()
