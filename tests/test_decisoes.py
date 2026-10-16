import copy
import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from classificacao_topicos.decisoes import preparar_decisoes
from classificacao_topicos.analise_piloto import _tentativas
from classificacao_topicos.execucao import executar_lote, _canonico, _validar_entradas, _validar_evidencia
from classificacao_topicos.piloto import esquema_resposta
from classificacao_topicos.politica import aplicar_politica
from classificacao_topicos.revalidacao import revalidar_recibo


def sha(conteudo):
    return hashlib.sha256(conteudo).hexdigest()


def escrever_json(caminho, objeto):
    caminho.write_text(json.dumps(objeto, ensure_ascii=False), encoding="utf-8")


def sugestao(identificador, **alteracoes):
    resposta = {"id": identificador, "tema_central_id": "T001", "extras_ids": [],
                "temas_alternativos": [], "sem_tema": False, "confianca_autodeclarada": 0.97,
                "motivo": "O texto menciona furto.", "evidencia": "furto", "requer_revisao": False}
    resposta.update(alteracoes)
    return resposta


def retorno(resposta):
    return {"resultado": resposta, "duracao_segundos": 0.25,
            "resposta": {"modelVersion": "gemini-3.5-flash-lite",
                         "usageMetadata": {"totalTokenCount": 150},
                         "candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(resposta)}]}}]}}


def confirmacao(**alteracoes):
    item = {"id": "Q0003", "sem_tema": True, "situacao": "confirmado",
            "justificativa": "Revisão separada confirmou ausência de tema adequado.",
            "responsavel": "Revisor de teste", "tipo_referencia": "IA"}
    item.update(alteracoes)
    return item


def revisao_com_tema(**alteracoes):
    item = confirmacao(sem_tema=False, situacao="tema_encontrado",
                      justificativa="A revisão identificou tema ativo adequado ao enunciado.",
                      sugestao_corrigida=sugestao("Q0003", requer_revisao=True, confianca_autodeclarada=0.88))
    item.update(alteracoes)
    return item


class DecisoesTests(unittest.TestCase):
    def setUp(self):
        temporaria = tempfile.TemporaryDirectory()
        self.addCleanup(temporaria.cleanup)
        self.raiz = Path(temporaria.name)
        self.preparacao, self.lote, self.execucao, self.saida = (
            self.raiz / "artefatos" / nome for nome in ("preparacao", "lote", "execucao", "decisoes"))
        self.config_dir = self.raiz / "config"
        for pasta in (self.preparacao, self.lote, self.config_dir):
            pasta.mkdir(parents=True)
        for nome in ("questoes.jsonl", "temas.csv"):
            (self.raiz / nome).write_text("Fonte fictícia para teste.\n", encoding="utf-8")
        questoes = [{"id": f"Q{i:04d}", "enunciado": "Uma questão de furto.",
                     "comando": "Julgue.", "alternativas": {"A": "Certo", "B": "Errado"}} for i in range(1, 4)]
        (self.preparacao / "questoes_preparadas.jsonl").write_text(
            "".join(json.dumps(q) + "\n" for q in questoes), encoding="utf-8")
        temas = [{"tema_id": f"T{i:03d}", "nivel": "0" if i == 0 else "1",
                  "parent_id": "" if i == 0 else "T000",
                  "status": "inactive" if i == 4 else "active"} for i in range(5)]
        escrever_json(self.preparacao / "temas_preparados.json", temas)
        manifesto_preparacao = {
            "schema_version": 1, "procedimento": "preparacao-v1",
            "fontes_sha256": {nome: sha((self.raiz / nome).read_bytes()) for nome in ("questoes.jsonl", "temas.csv")},
            "produtos_sha256": {nome: sha((self.preparacao / nome).read_bytes())
                                for nome in ("questoes_preparadas.jsonl", "temas_preparados.json")}}
        escrever_json(self.preparacao / "manifesto.json", manifesto_preparacao)
        # Ordem do lote distinta da original para testar a ordenação final exigida.
        entradas = [{"id": q["id"], "prompt": "Analise " + q["id"],
                     "sha256_prompt": sha(("Analise " + q["id"]).encode())} for q in reversed(questoes)]
        (self.lote / "entradas.jsonl").write_text("".join(json.dumps(e) + "\n" for e in entradas), encoding="utf-8")
        escrever_json(self.lote / "manifesto_lote.json", {
            "schema_version": 1, "procedimento": "lote-v1", "ids": [e["id"] for e in entradas],
            "prompt_version": "classificacao-v2",
            "preparacao_sha256": sha((self.preparacao / "manifesto.json").read_bytes()),
            "preparacao_produtos_sha256": manifesto_preparacao["produtos_sha256"],
            "produtos_sha256": {"entradas.jsonl": sha((self.lote / "entradas.jsonl").read_bytes())}})
        self.ambiguidades = self.config_dir / "ambiguidades.json"
        escrever_json(self.ambiguidades, {"schema_version": 1,
                      "fonte_sha256": sha((self.preparacao / "temas_preparados.json").read_bytes()),
                      "grupos_exatos": [{"ids": ["T002", "T003"]}], "grupos_semanticos_possiveis": []})
        self.politica = self.config_dir / "politica_v1.json"
        self.config = {"schema_version": 1, "versao": "politica-v1", "modelo": "gemini-3.5-flash-lite",
                       "prompt_version": "classificacao-v2", "confianca_minima": 0.95, "max_extras_publicar": 1,
                       "revisar_quando": ["modelo_requer_revisao", "confianca_abaixo_limiar", "candidatos_concorrentes",
                                          "central_disciplina_nivel_0", "central_em_colisao_de_ramos", "extras_acima_limite"],
                       "ids_ambiguos": ["T002", "T003"], "ambiguidades_fonte": "config/ambiguidades.json",
                       "ambiguidades_sha256": sha(self.ambiguidades.read_bytes())}
        escrever_json(self.politica, self.config)
        self.respostas = {"Q0001": sugestao("Q0001", extras_ids=["T003"]),
                          "Q0002": sugestao("Q0002", tema_central_id="T002", confianca_autodeclarada=0.949),
                          "Q0003": sugestao("Q0003", tema_central_id="", sem_tema=True)}
        self.gravar_recibos()
        self.confirmacoes = self.raiz / "confirmacoes_fora.jsonl"

    def gravar_recibos(self):
        def gerar(prompt, *_args, **_kwargs):
            return retorno(self.respostas[prompt.split()[-1]])
        with patch("classificacao_topicos.execucao.carregar_configuracao",
                   return_value={"api_key": "segredo-ficticio", "model": "gemini-3.5-flash-lite"}), \
             patch("classificacao_topicos.execucao.gerar_json", side_effect=gerar):
            executar_lote(self.lote, self.preparacao, self.execucao, limite=3,
                          intervalo_segundos=0, continuar_erros_validacao=True)

    def gravar_confirmacoes(self, itens=None):
        self.confirmacoes.write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in
                                             ([confirmacao()] if itens is None else itens)), encoding="utf-8")
        return self.confirmacoes

    def preparar(self, *, confirmacoes=None, saida=None):
        with patch("classificacao_topicos.execucao.carregar_configuracao", side_effect=AssertionError("credencial")), \
             patch("classificacao_topicos.execucao.gerar_json", side_effect=AssertionError("modelo")), \
             patch("urllib.request.urlopen", side_effect=AssertionError("rede")):
            return preparar_decisoes(self.lote, self.preparacao, self.execucao, self.politica,
                                      saida or self.saida, confirmacoes_fora=confirmacoes)

    def gravar_revalidacao_de_erro_antigo(self):
        self.execucao = self.raiz / "artefatos" / "execucao-revalidavel"
        self.respostas["Q0001"]["evidencia"] = "FURTO"

        def validador_antigo(resposta, questao):
            if resposta["id"] == "Q0001":
                raise ValueError("Validador antigo rejeitou diferença de caixa.")
            return _validar_evidencia(resposta, questao)

        with patch("classificacao_topicos.execucao._validar_evidencia", side_effect=validador_antigo):
            self.gravar_recibos()
        # A última tentativa continua inválida. O derivado deve recuperar a
        # primeira apenas por validação técnica, mantendo ambas no histórico.
        self.respostas["Q0001"]["evidencia"] = "Trecho inventado."
        self.gravar_recibos()
        arquivo = self.execucao / "Q0001.json"
        original = arquivo.read_bytes()
        registro = json.loads(original)
        entradas, temas, questoes, hash_preparacao, _ = _validar_entradas(
            self.lote, self.preparacao, procedimento_esperado="lote-v1")
        entrada = next(e for e in entradas if e["id"] == "Q0001")
        derivado = revalidar_recibo(arquivo, registro, entrada, self.config["modelo"],
                                    sha(_canonico(esquema_resposta())), hash_preparacao,
                                    temas, questoes["Q0001"])
        return arquivo, original, self.execucao / "Q0001.revalidacao.json", derivado

    def test_pendente_nao_gera_csv_e_preserva_sugestao_e_politica_na_trilha(self):
        resumo = self.preparar()
        self.assertFalse(resumo["completo"])
        self.assertEqual(resumo["decisoes"], {"publicar": 1, "revisar": 1, "fora": 0})
        self.assertEqual(resumo["ids_pendentes"], ["Q0003"])
        self.assertFalse((self.saida / "publicacao.csv").exists())
        trilha = [json.loads(linha) for linha in (self.saida / "trilha_decisoes.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([r["id"] for r in trilha], ["Q0001", "Q0002", "Q0003"])
        self.assertEqual(trilha[2]["politica"]["estado"], "pendente_confirmacao_fora")
        self.assertIsNone(trilha[2]["decisao"]["decisao"])
        self.assertEqual(trilha[2]["sugestao"]["confianca_autodeclarada"], 0.97)
        self.assertEqual(trilha[0]["decisao"]["decisao"], "publicar")
        for nome, esperado in resumo["produtos_sha256"].items():
            self.assertEqual(sha((self.saida / nome).read_bytes()), esperado)
        self.assertNotIn("segredo-ficticio", (self.saida / "trilha_decisoes.jsonl").read_text(encoding="utf-8"))

    def test_confirmacao_gera_csv_oficial_com_sent_inaplicavel_e_ordem_original(self):
        resumo = self.preparar(confirmacoes=self.gravar_confirmacoes())
        self.assertTrue(resumo["completo"])
        self.assertEqual(resumo["decisoes"], {"publicar": 1, "revisar": 1, "fora": 1})
        self.assertEqual(resumo["pendentes_fora"], 0)
        self.assertEqual(resumo["confirmacoes_fora"], {"total": 1, "tipos_referencia": {"IA": 1}})
        with (self.saida / "publicacao.csv").open(encoding="utf-8", newline="") as arquivo:
            leitor = csv.DictReader(arquivo)
            linhas = list(leitor)
        self.assertEqual(leitor.fieldnames, ["id", "decisao", "tema_central_id", "extras_ids", "confianca", "motivo"])
        self.assertEqual([r["id"] for r in linhas], ["Q0001", "Q0002", "Q0003"])
        self.assertEqual(linhas[0]["motivo"], "")
        self.assertEqual(linhas[0]["extras_ids"], "T003")
        self.assertTrue(linhas[1]["motivo"])
        self.assertEqual(linhas[2], {"id": "Q0003", "decisao": "fora", "tema_central_id": "",
                                   "extras_ids": "", "confianca": "0", "motivo": confirmacao()["justificativa"]})
        self.assertEqual(resumo["confianca"]["fora"]["natureza"], "sentinela_nao_aplicavel")
        self.assertEqual(resumo["fontes_sha256"]["confirmacoes_fora.jsonl"], sha(self.confirmacoes.read_bytes()))
        self.assertEqual((self.saida / "pendentes_fora.jsonl").read_bytes(), b"")

    def test_confirmacoes_duplicadas_nao_candidatas_ou_incompletas_falham(self):
        casos = [[confirmacao(), confirmacao()], [confirmacao(id="Q0001")], [confirmacao(id="Q9999")],
                 [confirmacao(sem_tema=False)], [confirmacao(sem_tema=1)], [confirmacao(situacao="provisorio")],
                 [confirmacao(justificativa=" ")], [confirmacao(responsavel="")],
                 [confirmacao(tipo_referencia="ia")], [confirmacao(tipo_referencia=[])]]
        for itens in casos:
            with self.subTest(itens=itens), self.assertRaises(ValueError):
                self.preparar(confirmacoes=self.gravar_confirmacoes(itens))
            self.assertFalse(self.saida.exists())

    def test_confirma_especialista_preserva_tipo_sem_transformar_confianca(self):
        resumo = self.preparar(confirmacoes=self.gravar_confirmacoes([confirmacao(tipo_referencia="especialista")]))
        self.assertEqual(resumo["confirmacoes_fora"]["tipos_referencia"], {"especialista": 1})
        trilha = [json.loads(linha) for linha in (self.saida / "trilha_decisoes.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(trilha[2]["decisao"]["confianca"], 0)
        self.assertEqual(trilha[2]["sugestao"]["confianca_autodeclarada"], 0.97)

    def test_tema_encontrado_gera_revisar_e_preserva_original_historico_e_confiancas(self):
        self.execucao = self.raiz / "artefatos" / "execucao-com-historico"
        self.respostas["Q0003"]["evidencia"] = "Evidência inventada."
        self.gravar_recibos()
        self.respostas["Q0003"]["evidencia"] = "furto"
        self.gravar_recibos()
        recibos = {p.name: p.read_bytes() for p in self.execucao.iterdir()}
        revisao = revisao_com_tema()
        resumo = self.preparar(confirmacoes=self.gravar_confirmacoes([revisao]))
        self.assertTrue(resumo["completo"])
        self.assertEqual(resumo["decisoes"], {"publicar": 1, "revisar": 2, "fora": 0})
        self.assertEqual(resumo["confirmacoes_fora"], {"total": 1, "tipos_referencia": {"IA": 1}})
        self.assertEqual(resumo["revisoes_fora"], {"confirmadas_sem_tema": 0, "ids_confirmadas_sem_tema": [],
                                                  "temas_encontrados": 1, "ids_temas_encontrados": ["Q0003"]})
        self.assertIn("revisor", resumo["confianca"]["revisar_apos_rejeicao_fora"])
        self.assertEqual(recibos, {p.name: p.read_bytes() for p in self.execucao.iterdir()})
        historico = _tentativas(json.loads(recibos["Q0003.json"]))
        self.assertEqual(len(historico), 2)
        self.assertEqual(sum(t["usage_metadata"]["totalTokenCount"] for t in historico), 300)
        trilha = [json.loads(linha) for linha in (self.saida / "trilha_decisoes.jsonl").read_text(encoding="utf-8").splitlines()]
        corrigida = trilha[2]
        self.assertEqual(corrigida["sugestao"], self.respostas["Q0003"])
        self.assertEqual(corrigida["status_recibo"], "sucesso")
        self.assertEqual(corrigida["politica"]["estado"], "pendente_confirmacao_fora")
        self.assertEqual(corrigida["confirmacao_fora"], revisao)
        self.assertEqual(corrigida["sugestao_corrigida"], revisao["sugestao_corrigida"])
        self.assertEqual(corrigida["politica_apos_revisao"]["decisao"], "revisar")
        self.assertEqual(corrigida["origem_confianca"], "sugestao_corrigida_da_revisao")
        self.assertEqual(corrigida["sugestao"]["confianca_autodeclarada"], 0.97)
        self.assertEqual(corrigida["decisao"]["confianca"], 0.88)
        self.assertIn("fora_rejeitado_por_revisao", corrigida["decisao"]["sinais"])
        self.assertNotIn("fora_rejeitado_por_revisao", corrigida["politica_apos_revisao"]["sinais"])
        self.assertIsNone(trilha[0]["sugestao_corrigida"])
        self.assertIsNone(trilha[0]["politica_apos_revisao"])
        self.assertEqual(trilha[0]["origem_confianca"], "sugestao_original_do_modelo")
        with (self.saida / "publicacao.csv").open(encoding="utf-8", newline="") as arquivo:
            linha = list(csv.DictReader(arquivo))[2]
        self.assertEqual(linha["decisao"], "revisar")
        self.assertEqual(linha["tema_central_id"], "T001")
        self.assertEqual(linha["confianca"], "0.88")
        self.assertEqual(linha["motivo"], "Revisão encontrou tema: " + revisao["justificativa"])

    def test_revisoes_positiva_e_negativa_compartilham_arquivo_sem_confundir_contagens(self):
        self.execucao = self.raiz / "artefatos" / "execucao-dois-candidatos"
        self.respostas["Q0002"] = sugestao("Q0002", tema_central_id="", sem_tema=True)
        self.gravar_recibos()
        confirmacoes = self.gravar_confirmacoes([revisao_com_tema(), confirmacao(id="Q0002")])
        resumo = self.preparar(confirmacoes=confirmacoes)
        self.assertEqual(resumo["decisoes"], {"publicar": 1, "revisar": 1, "fora": 1})
        self.assertEqual(resumo["confirmacoes_fora"], {"total": 2, "tipos_referencia": {"IA": 2}})
        self.assertEqual(resumo["revisoes_fora"], {"confirmadas_sem_tema": 1, "ids_confirmadas_sem_tema": ["Q0002"],
                                                  "temas_encontrados": 1, "ids_temas_encontrados": ["Q0003"]})
        trilha = [json.loads(linha) for linha in (self.saida / "trilha_decisoes.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(trilha[1]["decisao"]["confianca"], 0)
        self.assertEqual(trilha[1]["origem_confianca"], "sentinela_nao_aplicavel")
        self.assertIsNone(trilha[1]["sugestao_corrigida"])
        self.assertIsNone(trilha[1]["politica_apos_revisao"])
        antes = {p.name: p.read_bytes() for p in self.saida.iterdir()}
        with patch("classificacao_topicos.decisoes.os.replace", side_effect=AssertionError("regravação")):
            self.assertEqual(resumo, self.preparar(confirmacoes=confirmacoes))
        self.assertEqual(antes, {p.name: p.read_bytes() for p in self.saida.iterdir()})

    def test_correcao_com_confianca_maxima_segue_para_revisar_com_motivo_curto(self):
        justificativa = "Tema encontrado na revisão independente. " * 20
        revisao = revisao_com_tema(justificativa=justificativa)
        revisao["sugestao_corrigida"]["confianca_autodeclarada"] = 1.0
        resumo = self.preparar(confirmacoes=self.gravar_confirmacoes([revisao]))
        self.assertEqual(resumo["decisoes"], {"publicar": 1, "revisar": 2, "fora": 0})
        trilha = [json.loads(linha) for linha in (self.saida / "trilha_decisoes.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(trilha[2]["politica_apos_revisao"]["sinais"], ["revisao_solicitada"])
        self.assertEqual(trilha[2]["confirmacao_fora"]["justificativa"], justificativa)
        with (self.saida / "publicacao.csv").open(encoding="utf-8", newline="") as arquivo:
            linha = list(csv.DictReader(arquivo))[2]
        self.assertEqual(linha["decisao"], "revisar")
        self.assertEqual(linha["confianca"], "1.0")
        self.assertLessEqual(len(linha["motivo"]), 280)
        self.assertTrue(linha["motivo"].endswith("..."))

    def test_revisao_negativa_rejeita_sugestao_invalida_e_campos_inconsistentes(self):
        casos = []
        for campo, valor in [("requer_revisao", False), ("id", "Q0002"),
                             ("tema_central_id", "T004"), ("tema_central_id", "T000"),
                             ("evidencia", "Texto que não existe."), ("extras_ids", ["T004"]),
                             ("confianca_autodeclarada", 1.01)]:
            item = revisao_com_tema()
            item["sugestao_corrigida"][campo] = valor
            casos.append(item)
        casos.extend([
            revisao_com_tema(sugestao_corrigida=sugestao("Q0003", tema_central_id="", sem_tema=True, requer_revisao=True)),
            revisao_com_tema(sugestao_corrigida=None), revisao_com_tema(situacao="confirmado"),
            revisao_com_tema(sem_tema=True), revisao_com_tema(sem_tema=0),
            revisao_com_tema(responsavel=" "), revisao_com_tema(justificativa=""),
            revisao_com_tema(tipo_referencia="ia"), revisao_com_tema(id="Q0001"),
        ])
        incompleto = revisao_com_tema()
        incompleto.pop("sugestao_corrigida")
        casos.append(incompleto)
        for item in casos:
            with self.subTest(item=item), self.assertRaises(ValueError):
                self.preparar(confirmacoes=self.gravar_confirmacoes([item]))
            self.assertFalse(self.saida.exists())

    def test_saida_completa_com_correcao_nao_aceita_troca_por_confirmacao_fora(self):
        revisao = revisao_com_tema()
        self.preparar(confirmacoes=self.gravar_confirmacoes([revisao]))
        antes = {p.name: p.read_bytes() for p in self.saida.iterdir()}
        with self.assertRaisesRegex(ValueError, "congelada.*nova pasta"):
            self.preparar(confirmacoes=self.gravar_confirmacoes())
        self.assertEqual(antes, {p.name: p.read_bytes() for p in self.saida.iterdir()})
        nova = self.preparar(confirmacoes=self.confirmacoes, saida=self.saida.with_name("decisoes-outra-revisao"))
        self.assertEqual(nova["decisoes"]["fora"], 1)

    def test_falta_recibo_checksum_divergente_ou_lock_impedem_saida(self):
        arquivo = self.execucao / "Q0001.json"
        original = arquivo.read_bytes()
        arquivo.unlink()
        with self.assertRaisesRegex(ValueError, "cada questão"):
            self.preparar()
        arquivo.write_bytes(original)
        registro = json.loads(original)
        registro["sugestao"]["motivo"] = "alterado"
        escrever_json(arquivo, registro)
        with self.assertRaisesRegex(ValueError, "Checksum"):
            self.preparar()
        arquivo.write_bytes(original)
        (self.execucao / ".execucao.lock").write_text("em execução", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "ativa"):
            self.preparar()
        self.assertFalse(self.saida.exists())

    def test_recibo_de_erro_nao_se_converte_em_decisao(self):
        self.execucao = self.raiz / "artefatos" / "execucao-com-erro"
        self.respostas["Q0001"]["evidencia"] = "Paráfrase inventada."
        self.gravar_recibos()
        self.assertEqual(len(list(self.execucao.glob("Q*.json"))), 3)
        with self.assertRaisesRegex(ValueError, "sucesso técnico"):
            self.preparar()
        self.assertFalse(self.saida.exists())

    def test_revalidacao_recupera_tentativa_antiga_com_trilha_sem_alterar_consumo(self):
        arquivo, original, sidecar, derivado = self.gravar_revalidacao_de_erro_antigo()
        resumo = self.preparar(confirmacoes=self.gravar_confirmacoes())
        self.assertTrue(resumo["completo"])
        self.assertEqual(resumo["decisoes"], {"publicar": 1, "revisar": 1, "fora": 1})
        self.assertEqual(arquivo.read_bytes(), original)
        tentativas = _tentativas(json.loads(arquivo.read_bytes()))
        self.assertEqual(len(tentativas), 2)
        self.assertEqual(sum(t["usage_metadata"]["totalTokenCount"] for t in tentativas), 300)
        self.assertEqual(resumo["fontes_sha256"]["recibos"][arquivo.name], sha(original))
        self.assertEqual(resumo["fontes_sha256"]["revalidacoes"], {sidecar.name: sha(sidecar.read_bytes())})
        trilha = [json.loads(linha) for linha in (self.saida / "trilha_decisoes.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(trilha[0]["revalidacao"], derivado)
        self.assertEqual(trilha[0]["sha256_revalidacao"], sha(sidecar.read_bytes()))
        self.assertEqual(trilha[0]["status_recibo"], "erro")
        self.assertEqual(trilha[0]["status_efetivo"], "sucesso")
        self.assertEqual(trilha[0]["sugestao"]["evidencia"], "FURTO")
        self.assertEqual(trilha[0]["revalidacao"]["numero_tentativa_selecionada"], 1)
        self.assertIsNone(trilha[1]["revalidacao"])
        self.assertIsNone(trilha[1]["sha256_revalidacao"])

    def test_revalidacao_adulterada_mesmo_com_checksum_refeito_e_rejeitada(self):
        arquivo, original, sidecar, derivado = self.gravar_revalidacao_de_erro_antigo()
        derivado["sugestao"]["tema_central_id"] = "T002"
        derivado.pop("sha256_registro")
        derivado["sha256_registro"] = sha(_canonico(derivado))
        escrever_json(sidecar, derivado)
        with self.assertRaisesRegex(ValueError, "primeira tentativa"):
            self.preparar()
        self.assertEqual(arquivo.read_bytes(), original)
        self.assertFalse(self.saida.exists())

    def test_revalidacao_nao_substitui_recibo_ausente_nem_aceita_id_alheio(self):
        arquivo, original, sidecar, _ = self.gravar_revalidacao_de_erro_antigo()
        alheio = self.execucao / "Q9999.revalidacao.json"
        alheio.write_bytes(sidecar.read_bytes())
        with self.assertRaisesRegex(ValueError, "cada questão"):
            self.preparar()
        alheio.unlink()
        arquivo.unlink()
        with self.assertRaisesRegex(ValueError, "cada questão"):
            self.preparar()
        arquivo.write_bytes(original)
        self.assertFalse(self.saida.exists())

    def test_revalidacao_modificada_durante_calculo_impede_saida(self):
        _, _, sidecar, _ = self.gravar_revalidacao_de_erro_antigo()

        def aplicar_e_alterar(*args, **kwargs):
            resultado = aplicar_politica(*args, **kwargs)
            if args[0]["id"] == "Q0001":
                sidecar.write_bytes(sidecar.read_bytes() + b" ")
            return resultado

        with patch("classificacao_topicos.decisoes.aplicar_politica", side_effect=aplicar_e_alterar):
            with self.assertRaisesRegex(ValueError, "fonte mudou"):
                self.preparar()
        self.assertFalse(self.saida.exists())

    def test_politica_incompativel_hash_ambiguidades_e_grupos_sao_rejeitados(self):
        alteracoes = [("versao", "politica-v2"), ("schema_version", True), ("modelo", "gemini-outro"),
                      ("prompt_version", "classificacao-v1"), ("ambiguidades_sha256", "0" * 64),
                      ("ids_ambiguos", ["T002"]), ("confianca_minima", True), ("revisar_quando", [])]
        for campo, valor in alteracoes:
            config = copy.deepcopy(self.config)
            config[campo] = valor
            escrever_json(self.politica, config)
            with self.subTest(campo=campo), self.assertRaises(ValueError):
                self.preparar()
            self.assertFalse(self.saida.exists())
        escrever_json(self.politica, self.config)
        self.ambiguidades.write_bytes(self.ambiguidades.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "Hash"):
            self.preparar()

    def test_destino_protegido_e_arquivos_alheios_sao_preservados(self):
        for pasta in (self.raiz, self.preparacao, self.lote, self.execucao, self.config_dir,
                      self.raiz / ".git" / "decisoes"):
            with self.subTest(pasta=pasta), self.assertRaises(ValueError):
                self.preparar(saida=pasta)
        self.saida.mkdir()
        arquivo = self.saida / "importante.txt"
        arquivo.write_text("preservar", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "incompatíveis"):
            self.preparar()
        self.assertEqual(arquivo.read_text(), "preservar")

    def test_saida_completa_e_reutilizada_sem_regravar(self):
        confirmacoes = self.gravar_confirmacoes()
        primeiro = self.preparar(confirmacoes=confirmacoes)
        antes = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.saida.iterdir()}
        with patch("classificacao_topicos.decisoes.os.replace", side_effect=AssertionError("regravação")):
            segundo = self.preparar(confirmacoes=confirmacoes)
        self.assertEqual(primeiro, segundo)
        self.assertEqual(antes, {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.saida.iterdir()})

    def test_regeneracao_com_pendencia_preserva_saida_completa(self):
        self.preparar(confirmacoes=self.gravar_confirmacoes())
        antes = {p.name: p.read_bytes() for p in self.saida.iterdir()}
        with self.assertRaisesRegex(ValueError, "congelada.*nova pasta"):
            self.preparar()
        self.assertEqual(antes, {p.name: p.read_bytes() for p in self.saida.iterdir()})

    def test_saida_preliminar_pode_avancar_para_completa(self):
        preliminar = self.preparar()
        self.assertFalse(preliminar["completo"])
        final = self.preparar(confirmacoes=self.gravar_confirmacoes())
        self.assertTrue(final["completo"])
        self.assertEqual(final["pendentes_fora"], 0)
        self.assertTrue((self.saida / "publicacao.csv").exists())

    def test_confirmacao_alterada_exige_nova_pasta_e_preserva_versao_anterior(self):
        self.preparar(confirmacoes=self.gravar_confirmacoes())
        antes = {p.name: p.read_bytes() for p in self.saida.iterdir()}
        confirmacoes = self.gravar_confirmacoes([confirmacao(justificativa="Nova justificativa da revisão.")])
        with self.assertRaisesRegex(ValueError, "congelada.*nova pasta"):
            self.preparar(confirmacoes=confirmacoes)
        nova_saida = self.saida.with_name("decisoes-v2")
        nova = self.preparar(confirmacoes=confirmacoes, saida=nova_saida)
        self.assertTrue(nova["completo"])
        self.assertEqual(antes, {p.name: p.read_bytes() for p in self.saida.iterdir()})
        self.assertNotEqual(antes["publicacao.csv"], (nova_saida / "publicacao.csv").read_bytes())

    def test_politica_alterada_exige_nova_pasta(self):
        confirmacoes = self.gravar_confirmacoes()
        self.preparar(confirmacoes=confirmacoes)
        antes = {p.name: p.read_bytes() for p in self.saida.iterdir()}
        self.config["confianca_minima"] = 0.98
        escrever_json(self.politica, self.config)
        with self.assertRaisesRegex(ValueError, "congelada.*nova pasta"):
            self.preparar(confirmacoes=confirmacoes)
        nova = self.preparar(confirmacoes=confirmacoes, saida=self.saida.with_name("decisoes-politica-v2"))
        self.assertEqual(nova["decisoes"], {"publicar": 0, "revisar": 2, "fora": 1})
        self.assertEqual(antes, {p.name: p.read_bytes() for p in self.saida.iterdir()})

    def test_csv_existente_com_manifesto_ausente_invalido_ou_rebaixado_e_preservado(self):
        confirmacoes = self.gravar_confirmacoes()
        manifesto = self.preparar(confirmacoes=confirmacoes)
        caminho = self.saida / "manifesto_decisoes.json"
        rebaixado = copy.deepcopy(manifesto)
        rebaixado.update(completo=False, pendentes_fora=1, ids_pendentes=["Q0003"])
        rebaixado["decisoes"]["fora"] = 0
        rebaixado["produtos_sha256"].pop("publicacao.csv")
        contagens_adulteradas = copy.deepcopy(manifesto)
        contagens_adulteradas["decisoes"] = {"publicar": 2, "revisar": 0, "fora": 1}
        casos = [None, b"{invalido", json.dumps(rebaixado).encode(), json.dumps(contagens_adulteradas).encode()]
        for conteudo in casos:
            with self.subTest(conteudo=conteudo):
                if conteudo is None:
                    caminho.unlink()
                else:
                    caminho.write_bytes(conteudo)
                antes = {p.name: p.read_bytes() for p in self.saida.iterdir()}
                with self.assertRaisesRegex(ValueError, "manifesto ou produtos inválidos.*nova pasta"):
                    self.preparar(confirmacoes=confirmacoes)
                self.assertEqual(antes, {p.name: p.read_bytes() for p in self.saida.iterdir()})

    def test_csv_adulterado_mesmo_com_hash_refeito_nao_e_sobrescrito(self):
        confirmacoes = self.gravar_confirmacoes()
        manifesto = self.preparar(confirmacoes=confirmacoes)
        arquivo = self.saida / "publicacao.csv"
        arquivo.write_bytes(arquivo.read_bytes().replace(b"Q0001,publicar,T001", b"Q0001,publicar,T002"))
        for refazer_hash in (False, True):
            with self.subTest(refazer_hash=refazer_hash):
                if refazer_hash:
                    manifesto["produtos_sha256"]["publicacao.csv"] = sha(arquivo.read_bytes())
                    escrever_json(self.saida / "manifesto_decisoes.json", manifesto)
                antes = {p.name: p.read_bytes() for p in self.saida.iterdir()}
                with self.assertRaisesRegex(ValueError, "nova pasta"):
                    self.preparar(confirmacoes=confirmacoes)
                self.assertEqual(antes, {p.name: p.read_bytes() for p in self.saida.iterdir()})

    def test_saida_modificada_durante_calculo_nao_e_sobrescrita(self):
        confirmacoes = self.gravar_confirmacoes()
        self.preparar(confirmacoes=confirmacoes)
        manifesto = self.saida / "manifesto_decisoes.json"
        original = manifesto.read_bytes()

        def aplicar_e_alterar(*args, **kwargs):
            if args[0]["id"] == "Q0001":
                manifesto.write_bytes(original + b" ")
            return aplicar_politica(*args, **kwargs)

        with patch("classificacao_topicos.decisoes.aplicar_politica", side_effect=aplicar_e_alterar):
            with self.assertRaisesRegex(ValueError, "saída de decisões mudou"):
                self.preparar(confirmacoes=confirmacoes)
        self.assertEqual(manifesto.read_bytes(), original + b" ")


if __name__ == "__main__":
    unittest.main()
