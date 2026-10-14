"""Verifica contratos da CLI sem acessar rede nem credenciais locais."""

from contextlib import redirect_stdout, redirect_stderr
import io
import json
import unittest
from unittest.mock import patch

from classificacao_topicos.__main__ import main
from classificacao_topicos.gemini import ErroGemini


class TestCLI(unittest.TestCase):
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
