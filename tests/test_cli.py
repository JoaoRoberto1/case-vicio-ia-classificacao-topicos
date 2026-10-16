"""Verifica contratos da CLI sem acessar rede nem credenciais locais."""

from contextlib import redirect_stdout, redirect_stderr
import io
import json
import unittest
from unittest.mock import patch

from classificacao_topicos.__main__ import main
from classificacao_topicos.gemini import ErroGemini


class TestCLI(unittest.TestCase):
    def test_executar_lote_seleciona_ids_do_arquivo_json(self):
        from tests.test_execucao import ExecucaoTests, retorno
        fixture = ExecucaoTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.converter_para_lote()
        ids_arquivo = fixture.raiz / "ids.json"
        ids_arquivo.write_text('["Q0003", "Q0001"]', encoding="utf-8-sig")
        argumentos = ["classificacao_topicos", "executar-lote", "--lote", str(fixture.piloto),
                      "--preparacao", str(fixture.preparacao), "--saida", str(fixture.saida),
                      "--ids-arquivo", str(ids_arquivo), "--limite", "2", "--intervalo-segundos", "0"]
        saida = io.StringIO()
        with patch("sys.argv", argumentos), redirect_stdout(saida), \
                patch("classificacao_topicos.execucao.gerar_json", side_effect=[retorno(), retorno("Q0003")]) as gerar:
            self.assertEqual(main(), 0)
        self.assertEqual([c.args[0] for c in gerar.call_args_list], ["Analise Q0001", "Analise Q0003"])
        resumo = json.loads(saida.getvalue())
        self.assertEqual(resumo["ids_selecionados"], ["Q0001", "Q0003"])
        self.assertEqual((resumo["total_lote"], resumo["total_escopo"], resumo["novas"]), (3, 2, 2))
        self.assertFalse((fixture.saida / "Q0002.json").exists())

    def test_executar_lote_rejeita_arquivo_ids_invalido_sem_credenciais_ou_api(self):
        from tests.test_execucao import ExecucaoTests
        fixture = ExecucaoTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.converter_para_lote()
        ids_arquivo = fixture.raiz / "ids.json"
        argumentos = ["classificacao_topicos", "executar-lote", "--lote", str(fixture.piloto),
                      "--preparacao", str(fixture.preparacao), "--saida", str(fixture.saida),
                      "--ids-arquivo", str(ids_arquivo)]
        for conteudo in ('null', '{}', '"Q0001"', '[', '[]', '[1]', '["Q0001", "Q0001"]', '["Q9999"]'):
            ids_arquivo.write_text(conteudo, encoding="utf-8")
            with self.subTest(conteudo=conteudo), patch("sys.argv", argumentos), \
                    patch("classificacao_topicos.execucao.carregar_configuracao") as config, \
                    patch("classificacao_topicos.execucao.gerar_json") as gerar, \
                    redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as erro:
                main()
            self.assertEqual(erro.exception.code, 2)
            config.assert_not_called()
            gerar.assert_not_called()
            self.assertFalse(fixture.saida.exists())

    def test_revalidar_recibo_funciona_offline_sem_credencial_e_preserva_original(self):
        from tests.test_execucao import ExecucaoTests, retorno
        # O módulo vincula o validador no import. Carregá-lo antes do patch
        # evita capturar o mock quando este teste roda isoladamente.
        from classificacao_topicos import revalidacao
        fixture = ExecucaoTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.converter_para_lote()
        with patch("classificacao_topicos.execucao.gerar_json", return_value=retorno()), \
                patch("classificacao_topicos.execucao._validar_evidencia", side_effect=ValueError("Validação anterior")):
            fixture.executar_lote(limite=1)
        caminho = fixture.saida / "Q0001.json"
        original = caminho.read_bytes()
        saida = io.StringIO()
        argumentos = ["classificacao_topicos", "revalidar-recibo", "--lote", str(fixture.piloto),
                      "--preparacao", str(fixture.preparacao), "--execucao", str(fixture.saida), "--id", "Q0001"]
        with patch("sys.argv", argumentos), \
                patch("classificacao_topicos.gemini.carregar_configuracao", side_effect=AssertionError("Não carregar credenciais")), \
                patch("classificacao_topicos.execucao.gerar_json", side_effect=AssertionError("Não chamar API")), \
                redirect_stdout(saida):
            self.assertEqual(main(), 0)
        resultado = json.loads(saida.getvalue())
        self.assertEqual(resultado["chamadas_api"], 0)
        self.assertEqual(resultado["numero_tentativa_selecionada"], 1)
        self.assertEqual(caminho.read_bytes(), original)
        self.assertTrue((fixture.saida / "Q0001.revalidacao.json").is_file())

    def test_piloto_limite_conservador_e_falha_retorna_status_nao_zero(self):
        resultado = {"total": 20, "novas": 1, "parou_em_erro": "Q0020"}
        saida = io.StringIO()
        with patch("sys.argv", ["classificacao_topicos", "executar-piloto"]), \
                patch("classificacao_topicos.execucao.executar_piloto", return_value=resultado) as executar, \
                redirect_stdout(saida):
            self.assertEqual(main(), 1)
        self.assertEqual(executar.call_args.kwargs["limite"], 1)
        self.assertEqual(json.loads(saida.getvalue()), resultado)

    def test_verificacao_registra_recibo_sem_configuracao_secreta(self):
        recibo = {"resultado": {"ok": True}, "resposta": {"usageMetadata": {"totalTokenCount": 12}},
                  "duracao_segundos": 0.1}
        saida = io.StringIO()
        with patch("sys.argv", ["classificacao_topicos", "verificar-api"]), \
                patch("classificacao_topicos.gemini.carregar_configuracao", return_value={"api_key": "segredo-teste", "model": "gemini-3.8-flash"}), \
                patch("classificacao_topicos.gemini.gerar_json", return_value=recibo), \
                patch("classificacao_topicos.__main__._registrar_verificacao_api") as registrar, \
                redirect_stdout(saida):
            self.assertEqual(main(), 0)
        self.assertNotIn("segredo-teste", saida.getvalue())
        self.assertNotIn("segredo-teste", json.dumps(registrar.call_args.args[0]))
        self.assertEqual(registrar.call_args.args[0]["resposta"], recibo["resposta"])

    def test_verificacao_rejeita_numero_no_lugar_de_booleano(self):
        recibo = {"resultado": {"ok": 1}, "resposta": {}, "duracao_segundos": 0.1}
        with patch("sys.argv", ["classificacao_topicos", "verificar-api"]), \
                patch("classificacao_topicos.gemini.carregar_configuracao", return_value={"api_key": "segredo-teste", "model": "gemini-3.8-flash"}), \
                patch("classificacao_topicos.gemini.gerar_json", return_value=recibo), \
                patch("classificacao_topicos.__main__._registrar_verificacao_api") as registrar, \
                redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as erro:
            main()
        self.assertEqual(erro.exception.code, 2)
        self.assertEqual(registrar.call_args.args[0]["status"], "resposta_inesperada")

    def test_verificacao_preserva_uso_de_resposta_bloqueada(self):
        falha = ErroGemini("Resposta bloqueada.", resposta={"usageMetadata": {"totalTokenCount": 9}}, duracao_segundos=0.2)
        with patch("sys.argv", ["classificacao_topicos", "verificar-api"]), \
                patch("classificacao_topicos.gemini.carregar_configuracao", return_value={"api_key": "segredo-teste", "model": "gemini-3.8-flash"}), \
                patch("classificacao_topicos.gemini.gerar_json", side_effect=falha), \
                patch("classificacao_topicos.__main__._registrar_verificacao_api") as registrar, \
                redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as erro:
            main()
        self.assertEqual(erro.exception.code, 2)
        self.assertEqual(registrar.call_args.args[0]["resposta"], falha.resposta)


if __name__ == "__main__":
    unittest.main()
