import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from classificacao_topicos.analise_piloto import _consumo, _tentativas
from classificacao_topicos.execucao import _canonico, _fingerprint, _gravar_atomico, _hash_bytes
from classificacao_topicos.piloto import esquema_resposta
from classificacao_topicos.revalidacao import (
    carregar_revalidacao, caminho_revalidacao, revalidar_recibo,
    status_efetivo, sugestao_efetiva,
)


class RevalidacaoTests(unittest.TestCase):
    def setUp(self):
        temporaria = tempfile.TemporaryDirectory()
        self.addCleanup(temporaria.cleanup)
        self.pasta = Path(temporaria.name)
        self.caminho = self.pasta / "Q0001.json"
        self.derivado = caminho_revalidacao(self.caminho)
        self.model = "gemini-3.5-flash-lite"
        self.schema_hash = _hash_bytes(_canonico(esquema_resposta()))
        self.preparacao_hash = "a" * 64
        self.entrada = {"id": "Q0001", "prompt": "Analise Q0001",
                        "sha256_prompt": _hash_bytes(b"Analise Q0001")}
        self.temas = {"T001": {"tema_id": "T001", "status": "active"},
                      "T002": {"tema_id": "T002", "status": "active"}}
        self.questao = {"id": "Q0001", "enunciado": "Uma questão de FURTO.\nOs fatos.",
                        "comando": "Julgue.", "alternativas": {"A": "Certo", "B": "Errado"}}
        self.tentativas = [self.tentativa(i, "uma  questão de furto." if i == 1 else "Paráfrase dos fatos.")
                           for i in range(1, 5)]
        self.gravar()

    def sugestao(self, evidencia):
        return {"id": "Q0001", "tema_central_id": "T001", "extras_ids": [],
                "temas_alternativos": [], "sem_tema": False, "confianca_autodeclarada": 0.9,
                "motivo": "A questão aborda furto.", "evidencia": evidencia, "requer_revisao": False}

    def tentativa(self, numero, evidencia):
        item = {"schema_version": 1, "id": "Q0001", "model": self.model,
                "timestamp_utc": "2026-10-15T12:00:00+00:00", "sha256_prompt": self.entrada["sha256_prompt"],
                "sha256_schema": self.schema_hash, "sha256_preparacao": self.preparacao_hash,
                "thinking_level": "MEDIUM",
                "fingerprint": _fingerprint(self.entrada, self.model, self.schema_hash, self.preparacao_hash),
                "numero_tentativa": numero, "duracao_segundos": 0.5,
                "usage_metadata": {"totalTokenCount": 150}, "status": "erro",
                "erro": {"tipo": "ErroValidacaoLocal", "mensagem": "Falhou na validação original."},
                "resposta_bruta": {"modelVersion": self.model, "usageMetadata": {"totalTokenCount": 150},
                                   "candidates": [{"finishReason": "STOP", "content": {"parts": [
                                       {"text": json.dumps(self.sugestao(evidencia))}]}}]}}
        self.assinar(item)
        return item

    def assinar(self, objeto):
        objeto.pop("sha256_registro", None)
        objeto["sha256_registro"] = _hash_bytes(_canonico(objeto))

    def gravar(self):
        self.registro = copy.deepcopy(self.tentativas[-1])
        self.registro["tentativas_anteriores"] = copy.deepcopy(self.tentativas[:-1])
        _gravar_atomico(self.caminho, self.registro)

    def argumentos(self):
        return (self.caminho, self.registro, self.entrada, self.model, self.schema_hash,
                self.preparacao_hash, self.temas, self.questao)

    def revalidar(self):
        return revalidar_recibo(*self.argumentos())

    def carregar(self):
        return carregar_revalidacao(*self.argumentos())

    def alterar_derivado(self, **campos):
        item = json.loads(self.derivado.read_text(encoding="utf-8"))
        item.update(campos)
        _gravar_atomico(self.derivado, item)

    def test_derivacao_offline_preserva_recibo_tentativas_consumo_e_idempotencia(self):
        original = self.caminho.read_bytes()
        consumo = _consumo(_tentativas(self.registro))
        with patch("classificacao_topicos.execucao.gerar_json") as api, patch(
                "classificacao_topicos.execucao.carregar_configuracao") as config:
            derivado = self.revalidar()
            gravado = self.derivado.read_bytes()
            self.assertEqual(self.revalidar(), derivado)
            self.assertEqual(self.carregar(), derivado)
        api.assert_not_called()
        config.assert_not_called()
        self.assertEqual(self.caminho.read_bytes(), original)
        self.assertEqual(self.derivado.read_bytes(), gravado)
        self.assertEqual(_consumo(_tentativas(self.registro)), consumo)
        self.assertEqual((consumo["tentativas"], consumo["tokens_observados"]["totalTokenCount"]), (4, 600))
        self.assertEqual(derivado["numero_tentativa_selecionada"], 1)
        self.assertEqual(derivado["validacao_evidencia"], "caixa_e_espacos_normalizados")
        self.assertEqual(derivado["sugestao"]["evidencia"], "uma  questão de furto.")
        self.assertEqual(status_efetivo(self.registro, derivado), "sucesso")
        self.assertEqual(sugestao_efetiva(self.registro, derivado), derivado["sugestao"])
        self.assertEqual(self.registro["status"], "erro")
        self.assertFalse((self.pasta / ".execucao.lock").exists())

    def test_ausencia_nao_muda_estado_ou_sugestao_original(self):
        self.assertIsNone(self.carregar())
        self.assertEqual(status_efetivo(self.registro), "erro")
        self.assertIsNone(sugestao_efetiva(self.registro))
        sucesso = {"status": "sucesso", "sugestao": self.sugestao("FURTO")}
        self.assertEqual(sugestao_efetiva(sucesso), sucesso["sugestao"])

    def test_selecao_cronologica_nao_pode_ser_trocada_por_outra_tentativa_valida(self):
        self.tentativas[1] = self.tentativa(2, "FURTO")
        self.gravar()
        self.assertEqual(self.revalidar()["numero_tentativa_selecionada"], 1)
        self.alterar_derivado(numero_tentativa_selecionada=2,
                             sha256_tentativa_selecionada=self.tentativas[1]["sha256_registro"],
                             sugestao=self.sugestao("FURTO"), validacao_evidencia="literal")
        with self.assertRaisesRegex(ValueError, "primeira tentativa"):
            self.carregar()

    def test_rejeita_troca_de_sugestao_mesmo_com_checksum_refeito(self):
        derivado = self.revalidar()
        trocada = dict(derivado["sugestao"], tema_central_id="T002")
        self.alterar_derivado(sugestao=trocada)
        with self.assertRaisesRegex(ValueError, "primeira tentativa"):
            self.carregar()

    def test_erro_de_esquema_na_primeira_tentativa_nao_e_relaxado(self):
        bruto = self.tentativas[0]["resposta_bruta"]["candidates"][0]["content"]["parts"][0]
        item = self.sugestao("FURTO")
        item["extras_ids"] = ["T001"]
        bruto["text"] = json.dumps(item)
        self.assinar(self.tentativas[0])
        self.tentativas[1] = self.tentativa(2, "FURTO")
        self.gravar()
        self.assertEqual(self.revalidar()["numero_tentativa_selecionada"], 2)

    def test_parafrases_ou_json_ambiguo_nao_produzem_derivado(self):
        for defeito in ("parafrase", "chave_duplicada", "sem_stop"):
            with self.subTest(defeito=defeito):
                self.tentativas[0] = self.tentativa(1, "FURTO" if defeito != "parafrase" else "Texto inventado")
                candidato = self.tentativas[0]["resposta_bruta"]["candidates"][0]
                if defeito == "chave_duplicada":
                    candidato["content"]["parts"][0]["text"] = '{"id":"Q0001","id":"Q0001"}'
                elif defeito == "sem_stop":
                    candidato["finishReason"] = "MAX_TOKENS"
                self.assinar(self.tentativas[0])
                self.gravar()
                with self.assertRaisesRegex(ValueError, "Nenhuma tentativa"):
                    self.revalidar()
                self.assertFalse(self.derivado.exists())
                self.assertFalse((self.pasta / ".execucao.lock").exists())

    def test_historico_corrompido_ou_identidade_divergente_interrompe(self):
        self.tentativas[1]["sha256_registro"] = "0" * 64
        self.gravar()
        with self.assertRaisesRegex(ValueError, "Checksum de tentativa"):
            self.revalidar()
        self.tentativas[1]["model"] = "gemini-outro"
        self.assinar(self.tentativas[1])
        self.gravar()
        with self.assertRaisesRegex(ValueError, "identidade incompatível"):
            self.revalidar()

    def test_recibo_sucesso_ou_erro_api_nao_e_sobreposto(self):
        self.tentativas[-1]["erro"]["tipo"] = "ErroGemini"
        self.assinar(self.tentativas[-1])
        self.gravar()
        with self.assertRaisesRegex(ValueError, "falha de validação local"):
            self.revalidar()
        self.tentativas[-1]["status"] = "sucesso"
        self.tentativas[-1]["sugestao"] = self.sugestao("FURTO")
        self.assinar(self.tentativas[-1])
        self.gravar()
        with self.assertRaisesRegex(ValueError, "falha de validação local"):
            self.revalidar()

    def test_recibo_alterado_invalida_derivado_sem_reescrever(self):
        self.revalidar()
        derivado = self.derivado.read_bytes()
        self.caminho.write_bytes(self.caminho.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "outro recibo"):
            self.revalidar()
        self.assertEqual(self.derivado.read_bytes(), derivado)

    def test_derivado_divergente_ou_checksum_corrompido_nunca_e_sobrescrito(self):
        self.revalidar()
        self.alterar_derivado(criterio_selecao="maior_confianca")
        divergente = self.derivado.read_bytes()
        with self.assertRaisesRegex(ValueError, "critério"):
            self.revalidar()
        self.assertEqual(self.derivado.read_bytes(), divergente)
        item = json.loads(divergente)
        item["sha256_registro"] = "0" * 64
        self.derivado.write_text(json.dumps(item), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Checksum"):
            self.carregar()

    def test_lock_bloqueia_escrita_mas_nao_leitura(self):
        derivado = self.revalidar()
        lock = self.pasta / ".execucao.lock"
        lock.write_text("outro processo", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "execução ativa"):
            self.revalidar()
        self.assertEqual(self.carregar(), derivado)
        self.assertEqual(lock.read_text(encoding="utf-8"), "outro processo")

    def test_mudanca_da_origem_antes_da_gravacao_interrompe(self):
        from classificacao_topicos import revalidacao
        original = revalidacao._primeira_valida

        def mudar(*args):
            resposta = original(*args)
            self.caminho.write_bytes(self.caminho.read_bytes() + b"\n")
            return resposta

        with patch.object(revalidacao, "_primeira_valida", side_effect=mudar):
            with self.assertRaisesRegex(ValueError, "mudou durante"):
                self.revalidar()
        self.assertFalse(self.derivado.exists())
        self.assertFalse((self.pasta / ".execucao.lock").exists())

    def test_consumo_inconsistente_na_origem_nao_e_aceito(self):
        self.tentativas[1]["usage_metadata"]["totalTokenCount"] = 999
        self.assinar(self.tentativas[1])
        self.gravar()
        with self.assertRaisesRegex(ValueError, "Consumo resumido"):
            self.revalidar()


if __name__ == "__main__":
    unittest.main()
