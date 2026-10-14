import io
import json
import os
from pathlib import Path
import tempfile
import traceback
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from classificacao_topicos.gemini import (
    ErroGemini, MODELO_PADRAO, _SemRedirecionamento, carregar_configuracao, gerar_json,
)


CHAVE = "chave-ficticia-exclusiva-dos-testes"
SCHEMA = {"type": "object", "properties": {"tema_id": {"type": "string"}},
          "required": ["tema_id"]}


def recibo(texto='{"tema_id":"T001"}', *, motivo="STOP"):
    return {"candidates": [{"content": {"parts": [{"text": texto}]},
                            "finishReason": motivo}],
            "usageMetadata": {"promptTokenCount": 42, "totalTokenCount": 50},
            "modelVersion": MODELO_PADRAO, "responseId": "resposta-ficticia"}


class GeminiTests(unittest.TestCase):
    def chamar(self, **opcoes):
        argumentos = {"api_key": CHAVE, "model": MODELO_PADRAO}
        argumentos.update(opcoes)
        return gerar_json("Classifique a questão de teste.", SCHEMA, **argumentos)

    def resposta_mock(self, dados):
        return patch("classificacao_topicos.gemini.urlopen",
                     return_value=io.BytesIO(json.dumps(dados).encode("utf-8")))

    def test_rest_envia_schema_e_preserva_recibo_sem_inventar_consumo(self):
        bruto = recibo()
        bruto["candidates"][0]["content"]["parts"] = [
            {"thought": True, "text": "Isto não pertence ao JSON final."},
            {"text": '{"tema_id":'}, {"text": '"T001"}'},
        ]
        with self.resposta_mock(bruto) as abrir:
            saida = self.chamar()
        self.assertEqual(saida["resultado"], {"tema_id": "T001"})
        self.assertEqual(saida["resposta"], bruto)
        self.assertNotIn("thoughtsTokenCount", saida["resposta"]["usageMetadata"])
        self.assertGreaterEqual(saida["duracao_segundos"], 0)
        self.assertNotIn(CHAVE, json.dumps(saida))
        abrir.assert_called_once()
        request = abrir.call_args.args[0]
        self.assertEqual(request.full_url, "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("X-goog-api-key"), CHAVE)
        corpo = json.loads(request.data)
        self.assertEqual(corpo["generationConfig"]["responseFormat"]["text"]["schema"], SCHEMA)
        self.assertEqual(corpo["generationConfig"]["responseFormat"]["text"]["mimeType"], "APPLICATION_JSON")
        self.assertEqual(corpo["generationConfig"]["thinkingConfig"], {"thinkingLevel": "MEDIUM"})
        self.assertNotIn(CHAVE, request.data.decode("utf-8"))

    def test_http_429_e_403_sem_retry_e_sem_expor_detalhes(self):
        for status in (429, 403):
            with self.subTest(status=status):
                falha = HTTPError("https://exemplo.invalid/?key=" + CHAVE, status,
                                  CHAVE, {"x-goog-api-key": CHAVE}, io.BytesIO(CHAVE.encode()))
                with patch("classificacao_topicos.gemini.urlopen", side_effect=falha) as abrir:
                    try:
                        self.chamar()
                    except ErroGemini as erro:
                        self.assertIn(str(status), str(erro))
                        self.assertNotIn(CHAVE, "".join(traceback.format_exception(erro)))
                    else:
                        self.fail("A falha HTTP deveria interromper a execução.")
                abrir.assert_called_once()

    def test_erro_rede_nao_expoe_url_ou_chave(self):
        with patch("classificacao_topicos.gemini.urlopen", side_effect=URLError(CHAVE)):
            try:
                self.chamar()
            except ErroGemini as erro:
                self.assertNotIn(CHAVE, "".join(traceback.format_exception(erro)))
            else:
                self.fail("A falha de rede deveria interromper a execução.")

    def test_diagnostico_http_preserva_causa_sem_segredo_ou_url(self):
        documento = {"error": {"status": "INVALID_ARGUMENT", "message":
                    "Campo recusado responseFormat " + CHAVE + " https://exemplo.invalid/?key=" + CHAVE,
                    "details": [{"key": CHAVE}]}}
        falha = HTTPError("https://exemplo.invalid/", 400, CHAVE, {},
                          io.BytesIO(json.dumps(documento).encode()))
        with patch("classificacao_topicos.gemini.urlopen", side_effect=falha):
            with self.assertRaises(ErroGemini) as resultado:
                self.chamar()
        diagnostico = resultado.exception.resposta
        self.assertEqual(diagnostico["erro_http"]["status"], "INVALID_ARGUMENT")
        self.assertIn("responseFormat", diagnostico["erro_http"]["mensagem"])
        self.assertNotIn(CHAVE, json.dumps(diagnostico))
        self.assertNotIn("https://", json.dumps(diagnostico))
        self.assertNotIn("details", json.dumps(diagnostico))
        self.assertGreaterEqual(resultado.exception.duracao_segundos, 0)

    def test_recusa_json_final_invalido_ou_nao_objeto(self):
        for texto in ("{invalido", "[]", '"texto"', '{"valor": NaN}', "```json\n{}\n```", ""):
            with self.subTest(texto=texto), self.resposta_mock(recibo(texto)):
                with self.assertRaisesRegex(ErroGemini, "JSON"):
                    self.chamar()

    def test_json_invalido_no_documento_http(self):
        with patch("classificacao_topicos.gemini.urlopen", return_value=io.BytesIO(b"<html>erro</html>")):
            with self.assertRaisesRegex(ErroGemini, "documento JSON"):
                self.chamar()

    def test_chaves_duplicadas_no_envelope_sao_rejeitadas(self):
        casos = (
            '{"candidates": [], "candidates": []}',
            '{"usageMetadata": {"totalTokenCount": 50, "totalTokenCount": 0}}',
        )
        for documento in casos:
            with self.subTest(documento=documento), patch(
                "classificacao_topicos.gemini.urlopen", return_value=io.BytesIO(documento.encode())
            ):
                with self.assertRaisesRegex(ErroGemini, "documento JSON inválido"):
                    self.chamar()

    def test_chaves_duplicadas_no_json_final_preservam_recibo_de_erro(self):
        casos = (
            '{"tema_central_id": "INEXISTENTE", "tema_central_id": "T001"}',
            '{"objeto": {"tema_id": "INEXISTENTE", "tema_id": "T001"}}',
        )
        for texto in casos:
            bruto = recibo(texto)
            with self.subTest(texto=texto), self.resposta_mock(bruto):
                with self.assertRaisesRegex(ErroGemini, "texto final.*JSON válido") as falha:
                    self.chamar()
            self.assertEqual(falha.exception.resposta, bruto)
            self.assertEqual(falha.exception.resposta["usageMetadata"]["totalTokenCount"], 50)
            self.assertGreaterEqual(falha.exception.duracao_segundos, 0)
            self.assertNotIn("INEXISTENTE", str(falha.exception))

    def test_recusa_safety_max_tokens_e_fim_ausente(self):
        for motivo, mensagem in (("SAFETY", "SAFETY"), ("MAX_TOKENS", "MAX_TOKENS"),
                                 (None, "sem STOP"), ("RECITATION", "sem STOP")):
            with self.subTest(motivo=motivo), self.resposta_mock(recibo(motivo=motivo)):
                with self.assertRaisesRegex(ErroGemini, mensagem) as falha:
                    self.chamar()
                self.assertEqual(falha.exception.resposta["usageMetadata"]["totalTokenCount"], 50)
                self.assertGreaterEqual(falha.exception.duracao_segundos, 0)
                self.assertNotIn("usageMetadata", str(falha.exception))

    def test_recusa_prompt_bloqueado_antes_de_ler_candidatos(self):
        dados = {"promptFeedback": {"blockReason": "SAFETY"}}
        with self.resposta_mock(dados):
            with self.assertRaisesRegex(ErroGemini, "bloqueou o prompt"):
                self.chamar()

    def test_recusa_recibo_incompleto_ou_ambiguo(self):
        for dados in ({}, {"candidates": []}, {"candidates": [None]},
                      {"candidates": [{}, {}]},
                      {"candidates": [{"finishReason": "STOP", "content": {"parts": [3]}}]}):
            with self.subTest(dados=dados), self.resposta_mock(dados):
                with self.assertRaises(ErroGemini):
                    self.chamar()

    def test_valida_modelo_antes_da_rede(self):
        for modelo in ("", "models/gemini-3.8-flash", "../segredo", "gemini-x?key=segredo",
                       "https://outro.invalid/gemini-x", "gemini-x\n", "gemini-..", None):
            with self.subTest(modelo=modelo), patch("classificacao_topicos.gemini.urlopen") as abrir:
                with self.assertRaisesRegex(ErroGemini, "Modelo Gemini inválido"):
                    self.chamar(model=modelo)
                abrir.assert_not_called()

    def test_valida_chave_nivel_e_timeout_antes_da_rede(self):
        casos = ({"api_key": ""}, {"api_key": "chave\r\ncabecalho"},
                 {"thinking_level": "MINIMAL"}, {"timeout": 0},
                 {"timeout": float("inf")}, {"timeout": True})
        for opcoes in casos:
            with self.subTest(opcoes=opcoes), patch("classificacao_topicos.gemini.urlopen") as abrir:
                with self.assertRaises(ErroGemini):
                    self.chamar(**opcoes)
                abrir.assert_not_called()

    def test_nao_encaminha_chave_em_redirecionamento(self):
        self.assertIsNone(_SemRedirecionamento().redirect_request(
            None, None, 302, "Found", {}, "https://outro.invalid"))

    def test_env_utf8_com_aspas_sem_expandir_comandos(self):
        with tempfile.TemporaryDirectory() as pasta, patch.dict(os.environ, {}, clear=True):
            arquivo = Path(pasta) / ".env"
            arquivo.write_text("\ufeff# configuração local\nGEMINI_API_KEY='$(comando)'\nGEMINI_MODEL=gemini-3.8-flash\n", encoding="utf-8")
            config = carregar_configuracao(arquivo)
            self.assertEqual(config, {"api_key": "$(comando)", "model": MODELO_PADRAO})

    def test_env_do_processo_tem_precedencia_e_modelo_tem_padrao(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / ".env"
            arquivo.write_text("GEMINI_API_KEY=chave-arquivo\nGEMINI_MODEL=gemini-3.5-flash-lite\n", encoding="utf-8")
            with patch.dict(os.environ, {"GEMINI_API_KEY": CHAVE}, clear=True):
                self.assertEqual(carregar_configuracao(arquivo),
                                 {"api_key": CHAVE, "model": "gemini-3.5-flash-lite"})
            with patch.dict(os.environ, {"GEMINI_API_KEY": CHAVE, "GEMINI_MODEL": MODELO_PADRAO}, clear=True):
                self.assertEqual(carregar_configuracao(Path(pasta) / "inexistente"),
                                 {"api_key": CHAVE, "model": MODELO_PADRAO})
            arquivo.write_text("GEMINI_API_KEY=chave-arquivo\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(carregar_configuracao(arquivo)["model"], MODELO_PADRAO)

    def test_env_vazio_nao_cai_silenciosamente_para_chave_do_arquivo(self):
        with tempfile.TemporaryDirectory() as pasta, patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=True):
            arquivo = Path(pasta) / ".env"
            arquivo.write_text("GEMINI_API_KEY=chave-arquivo\n", encoding="utf-8")
            with self.assertRaisesRegex(ErroGemini, "ausente ou inválida"):
                carregar_configuracao(arquivo)

    def test_env_malformado_nao_expoe_conteudo(self):
        with tempfile.TemporaryDirectory() as pasta, patch.dict(os.environ, {}, clear=True):
            arquivo = Path(pasta) / ".env"
            for conteudo in (CHAVE, "GEMINI_API_KEY='" + CHAVE):
                arquivo.write_text(conteudo, encoding="utf-8")
                with self.subTest(conteudo=conteudo):
                    try:
                        carregar_configuracao(arquivo)
                    except ErroGemini as erro:
                        self.assertNotIn(CHAVE, str(erro))
                    else:
                        self.fail("O arquivo inválido deveria ser recusado.")


if __name__ == "__main__":
    unittest.main()
