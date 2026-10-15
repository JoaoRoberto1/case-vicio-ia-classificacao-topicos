import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from classificacao_topicos.execucao import executar_lote, executar_piloto
from classificacao_topicos.gemini import ErroGemini
from classificacao_topicos.piloto import preparar_piloto
from classificacao_topicos.preparacao import executar_preparacao


def hash_bytes(dados):
    return hashlib.sha256(dados).hexdigest()


def escrever_json(caminho, objeto):
    caminho.write_text(json.dumps(objeto, ensure_ascii=False), encoding="utf-8")


def sugestao(identificador="Q0001"):
    return {"id": identificador, "tema_central_id": "T001", "extras_ids": [],
            "temas_alternativos": [], "sem_tema": False,
            "confianca_autodeclarada": 0.9, "motivo": "O texto cobra furto.",
            "evidencia": "furto", "requer_revisao": False}


def retorno(identificador="Q0001", *, resposta=None):
    resultado = resposta if resposta is not None else sugestao(identificador)
    return {"resultado": resultado,
            "resposta": {"usageMetadata": {"promptTokenCount": 100, "totalTokenCount": 150},
                         "modelVersion": "gemini-3.8-flash",
                         "candidates": [{"content": {"parts": [{"text": json.dumps(resultado)}]},
                                         "finishReason": "STOP"}]},
            "duracao_segundos": 0.25}


class ExecucaoTests(unittest.TestCase):
    def setUp(self):
        self.temporaria = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporaria.cleanup)
        self.raiz = Path(self.temporaria.name)
        self.preparacao = self.raiz / "artefatos" / "preparacao"
        self.piloto = self.raiz / "artefatos" / "piloto"
        self.saida = self.raiz / "artefatos" / "execucao"
        self.preparacao.mkdir(parents=True)
        self.piloto.mkdir()
        (self.raiz / "questoes.jsonl").write_text("fontes-ficticias\n", encoding="utf-8")
        (self.raiz / "temas.csv").write_text("taxonomia-ficticia\n", encoding="utf-8")
        questoes = [{"id": f"Q{i:04d}", "enunciado": "Uma questão de furto.",
                     "comando": "Julgue.", "alternativas": {"A": "Certo", "B": "Errado"}}
                    for i in range(1, 4)]
        (self.preparacao / "questoes_preparadas.jsonl").write_text(
            "".join(json.dumps(q) + "\n" for q in questoes), encoding="utf-8")
        escrever_json(self.preparacao / "temas_preparados.json", [{"tema_id": "T001", "status": "active"}])
        self.manifesto_preparacao = {
            "schema_version": 1, "procedimento": "preparacao-v1",
            "fontes_sha256": {nome: hash_bytes((self.raiz / nome).read_bytes())
                              for nome in ("questoes.jsonl", "temas.csv")},
            "produtos_sha256": {nome: hash_bytes((self.preparacao / nome).read_bytes())
                                for nome in ("questoes_preparadas.jsonl", "temas_preparados.json")},
        }
        escrever_json(self.preparacao / "manifesto.json", self.manifesto_preparacao)
        self.entradas = [{"id": q["id"], "prompt": "Analise " + q["id"],
                          "sha256_prompt": hash_bytes(("Analise " + q["id"]).encode())}
                         for q in questoes]
        self.gravar_piloto()
        self.config = patch("classificacao_topicos.execucao.carregar_configuracao",
                            return_value={"api_key": "segredo-ficticio", "model": "gemini-3.8-flash"})
        self.config.start()
        self.addCleanup(self.config.stop)

    def gravar_piloto(self):
        (self.piloto / "entradas.jsonl").write_text(
            "".join(json.dumps(e) + "\n" for e in self.entradas), encoding="utf-8")
        manifesto = {"schema_version": 1, "procedimento": "piloto-v1",
                     "ids": [e["id"] for e in self.entradas],
                     "preparacao_sha256": hash_bytes((self.preparacao / "manifesto.json").read_bytes()),
                     "preparacao_produtos_sha256": self.manifesto_preparacao["produtos_sha256"],
                     "produtos_sha256": {"entradas.jsonl": hash_bytes((self.piloto / "entradas.jsonl").read_bytes())}}
        escrever_json(self.piloto / "manifesto_piloto.json", manifesto)

    def executar(self, **opcoes):
        return executar_piloto(self.piloto, self.preparacao, self.saida,
                               intervalo_segundos=0, **opcoes)

    def converter_para_lote(self):
        caminho = self.piloto / "manifesto_piloto.json"
        manifesto = json.loads(caminho.read_text(encoding="utf-8"))
        manifesto["procedimento"] = "lote-v1"
        manifesto["desenvolvimento_ids"] = manifesto["ids"][:20]
        manifesto["restante_ids"] = manifesto["ids"][20:]
        escrever_json(self.piloto / "manifesto_lote.json", manifesto)
        caminho.unlink()

    def ampliar_conjunto(self, quantidade):
        questoes = [{"id": f"Q{i:04d}", "enunciado": "Uma questão de furto.",
                     "comando": "Julgue.", "alternativas": {"A": "Certo", "B": "Errado"}}
                    for i in range(1, quantidade + 1)]
        caminho = self.preparacao / "questoes_preparadas.jsonl"
        caminho.write_text("".join(json.dumps(q) + "\n" for q in questoes), encoding="utf-8")
        self.manifesto_preparacao["produtos_sha256"][caminho.name] = hash_bytes(caminho.read_bytes())
        escrever_json(self.preparacao / "manifesto.json", self.manifesto_preparacao)
        self.entradas = [{"id": q["id"], "prompt": "Analise " + q["id"],
                          "sha256_prompt": hash_bytes(("Analise " + q["id"]).encode())}
                         for q in questoes]
        self.gravar_piloto()

    def executar_lote(self, **opcoes):
        return executar_lote(self.piloto, self.preparacao, self.saida,
                             intervalo_segundos=0, **opcoes)

    def test_padrao_uma_chamada_e_retomada_pula_sucessos(self):
        with patch("classificacao_topicos.execucao.gerar_json", return_value=retorno()) as gerar:
            resumo = self.executar()
        gerar.assert_called_once()
        self.assertEqual((resumo["novas"], resumo["cache"], resumo["sucesso"], resumo["pendencia"]), (1, 0, 1, 2))
        primeiro = (self.saida / "Q0001.json").read_bytes()
        self.assertNotIn(b"segredo-ficticio", primeiro)
        self.assertNotIn("thoughtsTokenCount", resumo["tokens_observados"])
        with patch("classificacao_topicos.execucao.gerar_json", return_value=retorno("Q0002")) as gerar:
            resumo = self.executar()
        self.assertEqual((resumo["novas"], resumo["cache"], resumo["sucesso"], resumo["pendencia"]), (1, 1, 2, 1))
        self.assertIn("Q0002", gerar.call_args.args[0])
        self.assertEqual(primeiro, (self.saida / "Q0001.json").read_bytes())
        self.assertEqual(resumo["tokens_observados"]["totalTokenCount"], 300)
        self.assertFalse((self.saida / ".execucao.lock").exists())

    def test_lote_reutiliza_revalidacao_sem_alterar_recibo_ou_duplicar_consumo(self):
        from classificacao_topicos.execucao import _validar_entradas, _hash_bytes, _canonico
        from classificacao_topicos.piloto import esquema_resposta
        from classificacao_topicos.revalidacao import revalidar_recibo
        self.converter_para_lote()
        resposta = sugestao()
        resposta["evidencia"] = "FURTO"
        with patch("classificacao_topicos.execucao.gerar_json", return_value=retorno(resposta=resposta)), \
                patch("classificacao_topicos.execucao._validar_evidencia", side_effect=ValueError("Validador anterior estrito")):
            self.executar_lote(limite=1)
        invalida = sugestao()
        invalida["evidencia"] = "texto que não está na questão"
        with patch("classificacao_topicos.execucao.gerar_json", return_value=retorno(resposta=invalida)):
            self.executar_lote(limite=1)
        caminho = self.saida / "Q0001.json"
        original = caminho.read_bytes()
        registro = json.loads(original)
        entradas, temas, questoes, hash_preparacao, _ = _validar_entradas(self.piloto, self.preparacao)
        revalidacao = revalidar_recibo(caminho, registro, entradas[0], "gemini-3.8-flash",
                                      _hash_bytes(_canonico(esquema_resposta())), hash_preparacao,
                                      temas, questoes["Q0001"])
        self.assertEqual(revalidacao["numero_tentativa_selecionada"], 1)
        with patch("classificacao_topicos.execucao.gerar_json", return_value=retorno("Q0002")) as gerar:
            resumo = self.executar_lote(limite=1)
        gerar.assert_called_once()
        self.assertIn("Q0002", gerar.call_args.args[0])
        self.assertEqual((resumo["cache"], resumo["novas"], resumo["sucesso"]), (1, 1, 2))
        self.assertEqual(resumo["revalidacoes_ids"], ["Q0001"])
        self.assertEqual(resumo["erros_validacao_ids"], [])
        self.assertEqual(resumo["tentativas_registradas"], 3)
        self.assertEqual(resumo["tokens_observados"]["totalTokenCount"], 450)
        self.assertEqual(caminho.read_bytes(), original)
        (self.saida / "Q0001.revalidacao.json").write_text("{}", encoding="utf-8")
        with patch("classificacao_topicos.execucao.gerar_json") as gerar, self.assertRaises(ValueError):
            self.executar_lote(limite=1)
        gerar.assert_not_called()

    def test_lote_rejeita_revalidacao_sem_recibo_antes_da_api(self):
        self.converter_para_lote()
        self.saida.mkdir()
        (self.saida / "Q0001.revalidacao.json").write_text("{}", encoding="utf-8")
        with patch("classificacao_topicos.execucao.gerar_json") as gerar, self.assertRaises(ValueError):
            self.executar_lote(limite=1)
        gerar.assert_not_called()

    def test_piloto_completo_em_cache_nao_chama_modelo(self):
        with patch("classificacao_topicos.execucao.gerar_json", side_effect=[retorno(f"Q{i:04d}") for i in range(1, 4)]):
            self.executar(limite=3)
        with patch("classificacao_topicos.execucao.gerar_json") as gerar:
            resumo = self.executar()
        gerar.assert_not_called()
        self.assertEqual((resumo["novas"], resumo["cache"], resumo["pendencia"]), (0, 3, 0))

    def test_falha_tecnica_para_sem_fallback_e_pode_retomar(self):
        with patch("classificacao_topicos.execucao.gerar_json", side_effect=ErroGemini("HTTP 429 segredo-ficticio")) as gerar:
            resumo = self.executar(limite=3)
        gerar.assert_called_once()
        self.assertEqual(resumo["parou_em_erro"], "Q0001")
        self.assertEqual(resumo["tokens_observados"], {})
        registro = json.loads((self.saida / "Q0001.json").read_text(encoding="utf-8"))
        self.assertEqual(registro["status"], "erro")
        self.assertNotIn("sugestao", registro)
        self.assertNotIn("segredo-ficticio", json.dumps(registro))
        self.assertEqual(len(list(self.saida.glob("Q*.json"))), 1)
        with patch("classificacao_topicos.execucao.gerar_json", return_value=retorno()):
            self.assertEqual(self.executar()["sucesso"], 1)

    def test_falha_gemini_com_recibo_preserva_consumo_e_resposta(self):
        bruto = {"usageMetadata": {"thoughtsTokenCount": 700}, "candidates": [{"finishReason": "MAX_TOKENS"}]}
        erro = ErroGemini("Truncada por MAX_TOKENS", resposta=bruto, duracao_segundos=1.25)
        with patch("classificacao_topicos.execucao.gerar_json", side_effect=erro):
            resumo = self.executar()
        registro = json.loads((self.saida / "Q0001.json").read_text(encoding="utf-8"))
        self.assertEqual(registro["resposta_bruta"], bruto)
        self.assertEqual(registro["duracao_segundos"], 1.25)
        self.assertEqual(resumo["tokens_observados"], {"thoughtsTokenCount": 700})

    def test_retomada_preserva_tentativas_e_soma_consumo_sem_duplicar(self):
        bruto = {"usageMetadata": {"promptTokenCount": 80, "totalTokenCount": 200},
                 "candidates": [{"finishReason": "MAX_TOKENS"}]}
        erro = ErroGemini("MAX_TOKENS", resposta=bruto, duracao_segundos=1.25)
        with patch("classificacao_topicos.execucao.gerar_json", side_effect=erro):
            self.executar()
            self.executar()
        with patch("classificacao_topicos.execucao.gerar_json", return_value=retorno()):
            resumo = self.executar()
        registro = json.loads((self.saida / "Q0001.json").read_text(encoding="utf-8"))
        self.assertEqual(registro["numero_tentativa"], 3)
        self.assertEqual(len(registro["tentativas_anteriores"]), 2)
        self.assertEqual([r["resposta_bruta"] for r in registro["tentativas_anteriores"]], [bruto, bruto])
        self.assertEqual(resumo["tokens_observados"], {"promptTokenCount": 260, "totalTokenCount": 550})
        self.assertEqual(resumo["tokens_registros_informados"]["totalTokenCount"], 3)
        self.assertEqual(resumo["tentativas_registradas"], 3)
        self.assertNotIn("tentativas_anteriores", registro["tentativas_anteriores"][1])
        for item in [registro, *registro["tentativas_anteriores"]]:
            sem_hash = {k: v for k, v in item.items() if k != "sha256_registro"}
            canonico = json.dumps(sem_hash, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
            self.assertEqual(item["sha256_registro"], hash_bytes(canonico))

    def test_resposta_invalida_mantem_recibo_e_interrompe(self):
        resultado = sugestao()
        resultado["tema_central_id"] = "INEXISTENTE"
        bruto = retorno(resposta=resultado)
        with patch("classificacao_topicos.execucao.gerar_json", return_value=bruto) as gerar:
            resumo = self.executar(limite=3)
        gerar.assert_called_once()
        registro = json.loads((self.saida / "Q0001.json").read_text(encoding="utf-8"))
        self.assertEqual(registro["resposta_bruta"], bruto["resposta"])
        self.assertEqual(registro["erro"]["tipo"], "ErroValidacaoLocal")
        self.assertEqual(resumo["sucesso"], 0)
        self.assertNotIn("sugestao", registro)

    def test_evidencia_inventada_nao_vira_sucesso(self):
        resultado = sugestao()
        resultado["evidencia"] = "texto que existe somente na imaginação"
        with patch("classificacao_topicos.execucao.gerar_json", return_value=retorno(resposta=resultado)):
            self.assertEqual(self.executar()["sucesso"], 0)

    def test_evidencia_com_caixa_e_espacos_diferentes_preserva_texto_e_registra_normalizacao(self):
        resultado = sugestao()
        resultado["evidencia"] = "uma  QUESTÃO\nde furto."
        with patch("classificacao_topicos.execucao.gerar_json", return_value=retorno(resposta=resultado)):
            self.assertEqual(self.executar()["sucesso"], 1)
        registro = json.loads((self.saida / "Q0001.json").read_text(encoding="utf-8"))
        self.assertEqual(registro["sugestao"]["evidencia"], resultado["evidencia"])
        self.assertEqual(registro["validacao_evidencia"], "caixa_e_espacos_normalizados")

    def test_normalizacao_de_evidencia_nao_corrige_palavras_acentos_ou_pontuacao(self):
        from classificacao_topicos.execucao import _validar_evidencia
        questao = {"enunciado": "Não há furto.", "comando": "", "alternativas": {}}
        for evidencia in ("Nao há furto.", "Não existe furto.", "Não há: furto."):
            with self.subTest(evidencia=evidencia), self.assertRaises(ValueError):
                _validar_evidencia({"evidencia": evidencia}, questao)

    def test_manifesto_ou_fonte_alterada_falha_antes_da_api(self):
        for arquivo in (self.preparacao / "temas_preparados.json", self.raiz / "questoes.jsonl",
                        self.piloto / "entradas.jsonl", self.preparacao / "manifesto.json"):
            original = arquivo.read_bytes()
            arquivo.write_bytes(original + b" ")
            try:
                with self.subTest(arquivo=arquivo.name), patch("classificacao_topicos.execucao.gerar_json") as gerar:
                    with self.assertRaises(ValueError):
                        self.executar()
                    gerar.assert_not_called()
            finally:
                arquivo.write_bytes(original)

    def test_prompt_com_hash_incorreto_e_id_inseguro_falham(self):
        self.entradas[0]["prompt"] = "modificado"
        self.gravar_piloto()
        with patch("classificacao_topicos.execucao.gerar_json") as gerar:
            with self.assertRaisesRegex(ValueError, "Hash do prompt"):
                self.executar()
            gerar.assert_not_called()
        self.entradas[0]["id"] = "../arquivo"
        self.gravar_piloto()
        with patch("classificacao_topicos.execucao.gerar_json") as gerar:
            with self.assertRaisesRegex(ValueError, "IDs inválidos"):
                self.executar()
            gerar.assert_not_called()

    def test_limite_invalido_e_rejeitado_antes_da_api(self):
        for limite in (0, 4, 21, -1, True, 1.5):
            with self.subTest(limite=limite), patch("classificacao_topicos.execucao.gerar_json") as gerar:
                with self.assertRaisesRegex(ValueError, "limite"):
                    self.executar(limite=limite)
                gerar.assert_not_called()

    def test_cache_de_outro_modelo_ou_prompt_nao_e_sobrescrito(self):
        with patch("classificacao_topicos.execucao.gerar_json", return_value=retorno()):
            self.executar()
        original = (self.saida / "Q0001.json").read_bytes()
        self.entradas[0]["prompt"] = "novo prompt"
        self.entradas[0]["sha256_prompt"] = hash_bytes(b"novo prompt")
        self.gravar_piloto()
        with patch("classificacao_topicos.execucao.gerar_json") as gerar:
            with self.assertRaisesRegex(ValueError, "nova pasta"):
                self.executar()
            gerar.assert_not_called()
        self.assertEqual((self.saida / "Q0001.json").read_bytes(), original)

    def test_cache_adulterado_e_rejeitado_antes_da_api(self):
        with patch("classificacao_topicos.execucao.gerar_json", return_value=retorno()):
            self.executar()
        arquivo = self.saida / "Q0001.json"
        registro = json.loads(arquivo.read_text(encoding="utf-8"))
        registro["sugestao"]["motivo"] = "alterado"
        escrever_json(arquivo, registro)
        with patch("classificacao_topicos.execucao.gerar_json") as gerar:
            with self.assertRaisesRegex(ValueError, "Checksum"):
                self.executar()
            gerar.assert_not_called()

    def test_destino_protegido_ou_arquivo_estranho_nao_recebe_escritas(self):
        for saida in (self.raiz, self.preparacao, self.piloto, self.raiz / "contexto_local" / "resultado"):
            with self.subTest(saida=saida), patch("classificacao_topicos.execucao.gerar_json") as gerar:
                with self.assertRaises(ValueError):
                    executar_piloto(self.piloto, self.preparacao, saida)
                gerar.assert_not_called()
        self.saida.mkdir(parents=True)
        (self.saida / "importante.txt").write_text("preservar", encoding="utf-8")
        with patch("classificacao_topicos.execucao.gerar_json") as gerar:
            with self.assertRaisesRegex(ValueError, "incompatíveis"):
                self.executar()
            gerar.assert_not_called()
        self.assertEqual((self.saida / "importante.txt").read_text(), "preservar")

    def test_integracao_preparacao_e_piloto_reais_com_provider_simulado(self):
        raiz_projeto = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as pasta:
            temporaria = Path(pasta)
            preparacao, piloto, saida = (temporaria / nome for nome in ("preparacao", "piloto", "recibos"))
            executar_preparacao(raiz_projeto, preparacao)
            manifesto = preparar_piloto(preparacao, piloto)
            questoes = [json.loads(linha) for linha in (preparacao / "questoes_preparadas.jsonl").read_text(encoding="utf-8").split("\n") if linha]
            questao = next(q for q in questoes if q["id"] == manifesto["ids"][0])
            temas = json.loads((preparacao / "temas_preparados.json").read_text(encoding="utf-8"))
            # Simulação de contrato, sem afirmar que o tema abaixo é correto.
            resposta = sugestao(questao["id"])
            resposta["tema_central_id"] = next(t["tema_id"] for t in temas if t["status"] == "active")
            resposta["evidencia"] = questao["enunciado"][:40]
            with patch("classificacao_topicos.execucao.gerar_json", return_value=retorno(resposta=resposta)) as gerar:
                resumo = executar_piloto(piloto, preparacao, saida)
            gerar.assert_called_once()
            self.assertEqual((resumo["total"], resumo["sucesso"], resumo["pendencia"]), (20, 1, 19))

    def test_executor_exige_tipo_de_manifesto_explicitamente(self):
        with patch("classificacao_topicos.execucao.gerar_json") as gerar:
            with self.assertRaisesRegex(ValueError, "tipo de execução"):
                self.executar_lote()
            self.converter_para_lote()
            with self.assertRaisesRegex(ValueError, "tipo de execução"):
                self.executar()
            gerar.assert_not_called()
        self.assertFalse(self.saida.exists())

    def test_manifesto_unico_e_procedimento_correspondente_ao_nome(self):
        manifesto = json.loads((self.piloto / "manifesto_piloto.json").read_text(encoding="utf-8"))
        manifesto["procedimento"] = "lote-v1"
        escrever_json(self.piloto / "manifesto_lote.json", manifesto)
        with patch("classificacao_topicos.execucao.gerar_json") as gerar:
            for executar in (self.executar, self.executar_lote):
                with self.subTest(executar=executar.__name__), self.assertRaisesRegex(ValueError, "exatamente um"):
                    executar()
            (self.piloto / "manifesto_piloto.json").unlink()
            manifesto["procedimento"] = "piloto-v1"
            escrever_json(self.piloto / "manifesto_lote.json", manifesto)
            with self.assertRaisesRegex(ValueError, "procedimento"):
                self.executar_lote()
            gerar.assert_not_called()

    def test_lote_incompleto_nao_processa_nem_grava_recibos(self):
        self.entradas.pop()
        self.gravar_piloto()
        self.converter_para_lote()
        with patch("classificacao_topicos.execucao.gerar_json") as gerar:
            with self.assertRaisesRegex(ValueError, "todas as questões"):
                self.executar_lote()
            gerar.assert_not_called()
        self.assertFalse(self.saida.exists())

    def test_lote_reutiliza_recibo_do_piloto_sem_alterar_fingerprint_ou_historico(self):
        erro = ErroGemini("MAX_TOKENS", resposta={"usageMetadata": {"totalTokenCount": 200}},
                          duracao_segundos=1.25)
        with patch("classificacao_topicos.execucao.gerar_json", side_effect=erro):
            self.executar()
        with patch("classificacao_topicos.execucao.gerar_json", return_value=retorno()):
            self.executar()
        recibo_original = (self.saida / "Q0001.json").read_bytes()
        self.converter_para_lote()
        with patch("classificacao_topicos.execucao.gerar_json", return_value=retorno("Q0002")) as gerar:
            resumo = self.executar_lote()
        gerar.assert_called_once()
        self.assertEqual((resumo["novas"], resumo["cache"], resumo["sucesso"]), (1, 1, 2))
        self.assertEqual((self.saida / "Q0001.json").read_bytes(), recibo_original)
        self.assertEqual(resumo["tentativas_registradas"], 3)
        self.assertEqual(resumo["tokens_observados"]["totalTokenCount"], 500)

    def test_cap_do_piloto_continua_20_e_lote_permite_mais_de_20(self):
        self.ampliar_conjunto(21)
        with patch("classificacao_topicos.execucao.gerar_json") as gerar:
            with self.assertRaisesRegex(ValueError, "1 e 20"):
                self.executar(limite=21)
            gerar.assert_not_called()
        self.converter_para_lote()
        with patch("classificacao_topicos.execucao.gerar_json", side_effect=[retorno(f"Q{i:04d}") for i in range(1, 22)]) as gerar:
            resumo = self.executar_lote(limite=21)
        self.assertEqual(gerar.call_count, 21)
        self.assertEqual((resumo["novas"], resumo["sucesso"], resumo["pendencia"]), (21, 21, 0))

    def test_cap_do_lote_e_500_e_nao_aceita_limites_invalidos(self):
        self.ampliar_conjunto(501)
        self.converter_para_lote()
        with patch("classificacao_topicos.execucao.gerar_json") as gerar:
            for limite in (0, -1, True, 1.5, 501):
                with self.subTest(limite=limite), self.assertRaisesRegex(ValueError, "limite"):
                    self.executar_lote(limite=limite)
            gerar.assert_not_called()
        # Um limite válido não altera a regra de parar na primeira falha.
        with patch("classificacao_topicos.execucao.gerar_json", side_effect=ErroGemini("HTTP 429")) as gerar:
            resumo = self.executar_lote(limite=500)
        gerar.assert_called_once()
        self.assertEqual(resumo["novas"], 1)
        self.assertEqual(resumo["parou_em_erro"], "Q0001")

    def test_lote_continua_erro_local_preservando_historico_consumo_e_sem_repetir_id(self):
        self.converter_para_lote()
        invalida = sugestao()
        invalida["evidencia"] = "Paráfrase que não ocorre na questão."
        with patch("classificacao_topicos.execucao.gerar_json", return_value=retorno(resposta=invalida)):
            primeiro = self.executar_lote(limite=3)
        self.assertEqual(primeiro["parou_em_erro"], "Q0001")
        with patch("classificacao_topicos.execucao.gerar_json", side_effect=[
                retorno(resposta=invalida), retorno("Q0002"), retorno("Q0003")]) as gerar:
            resumo = self.executar_lote(limite=3, continuar_erros_validacao=True)
        self.assertEqual(gerar.call_count, 3)
        self.assertEqual([chamada.args[0] for chamada in gerar.call_args_list],
                         ["Analise Q0001", "Analise Q0002", "Analise Q0003"])
        self.assertEqual((resumo["novas"], resumo["sucesso"], resumo["pendencia"]), (3, 2, 1))
        self.assertIsNone(resumo["parou_em_erro"])
        self.assertEqual(resumo["erros_validacao_ids"], ["Q0001"])
        self.assertTrue(resumo["concluido_com_falhas"])
        self.assertEqual(resumo["tentativas_registradas"], 4)
        self.assertEqual(resumo["tokens_observados"]["totalTokenCount"], 600)
        registro = json.loads((self.saida / "Q0001.json").read_text(encoding="utf-8"))
        self.assertEqual(registro["status"], "erro")
        self.assertNotIn("sugestao", registro)
        self.assertEqual(registro["numero_tentativa"], 2)
        self.assertEqual(len(registro["tentativas_anteriores"]), 1)
        self.assertEqual(registro["resposta_bruta"], retorno(resposta=invalida)["resposta"])
        self.assertEqual(registro["tentativas_anteriores"][0]["resposta_bruta"], registro["resposta_bruta"])
        # Uma retomada posterior pode resolver o erro; o histórico não é uma falha atual.
        with patch("classificacao_topicos.execucao.gerar_json", return_value=retorno()):
            resolvido = self.executar_lote(continuar_erros_validacao=True)
        self.assertEqual(resolvido["erros_validacao_ids"], [])
        self.assertFalse(resolvido["concluido_com_falhas"])
        self.assertEqual(resolvido["tokens_observados"]["totalTokenCount"], 750)

    def test_lote_continuacao_nao_avanca_apos_erro_gemini(self):
        self.converter_para_lote()
        invalida = sugestao()
        invalida["tema_central_id"] = "INEXISTENTE"
        for codigo in (429, 503):
            self.saida = self.raiz / "artefatos" / f"execucao-{codigo}"
            with self.subTest(codigo=codigo), patch("classificacao_topicos.execucao.gerar_json",
                                                  side_effect=[retorno(resposta=invalida), ErroGemini(f"HTTP {codigo}")]) as gerar:
                resumo = self.executar_lote(limite=3, continuar_erros_validacao=True)
            self.assertEqual(gerar.call_count, 2)
            self.assertEqual(resumo["parou_em_erro"], "Q0002")
            self.assertEqual(resumo["erros_validacao_ids"], ["Q0001"])
            self.assertFalse(resumo["concluido_com_falhas"])
            self.assertEqual(resumo["sucesso"], 0)
            self.assertFalse((self.saida / "Q0003.json").exists())
            registro = json.loads((self.saida / "Q0002.json").read_text(encoding="utf-8"))
            self.assertEqual(registro["erro"]["tipo"], "ErroGemini")

    def test_lote_padrao_interrompe_erro_local_e_opcao_exige_booleano(self):
        self.converter_para_lote()
        with patch("classificacao_topicos.execucao.gerar_json") as gerar:
            for valor in (0, 1, "true", None, []):
                with self.subTest(valor=valor), self.assertRaisesRegex(ValueError, "booleano"):
                    self.executar_lote(continuar_erros_validacao=valor)
            gerar.assert_not_called()
        invalida = sugestao()
        invalida["evidencia"] = "Frase inventada."
        with patch("classificacao_topicos.execucao.gerar_json", return_value=retorno(resposta=invalida)) as gerar:
            resumo = self.executar_lote(limite=3)
        gerar.assert_called_once()
        self.assertEqual(resumo["parou_em_erro"], "Q0001")
        self.assertEqual(resumo["erros_validacao_ids"], ["Q0001"])
        self.assertFalse(resumo["concluido_com_falhas"])
        self.assertFalse((self.saida / "Q0002.json").exists())

    def test_lote_parcial_sinaliza_falha_local_sem_alegar_cobertura_total(self):
        self.converter_para_lote()
        invalida = sugestao()
        invalida["evidencia"] = "Frase inventada."
        with patch("classificacao_topicos.execucao.gerar_json", return_value=retorno(resposta=invalida)) as gerar:
            resumo = self.executar_lote(continuar_erros_validacao=True)
        gerar.assert_called_once()
        self.assertTrue(resumo["concluido_com_falhas"])
        self.assertIsNone(resumo["parou_em_erro"])
        self.assertEqual((resumo["total"], resumo["novas"], resumo["pendencia"]), (3, 1, 3))


if __name__ == "__main__":
    unittest.main()
