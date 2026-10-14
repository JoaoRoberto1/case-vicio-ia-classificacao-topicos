import copy
import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from classificacao_topicos.decisoes import preparar_decisoes
from classificacao_topicos.execucao import executar_lote


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
                  "parent_id": "" if i == 0 else "T000", "status": "active"} for i in range(4)]
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

    def test_regeneracao_com_pendencia_remove_csv_anterior_para_nao_expor_incompleto(self):
        self.preparar(confirmacoes=self.gravar_confirmacoes())
        self.assertTrue((self.saida / "publicacao.csv").exists())
        resumo = self.preparar()
        self.assertFalse((self.saida / "publicacao.csv").exists())
        self.assertNotIn("publicacao.csv", resumo["produtos_sha256"])
        self.assertFalse(resumo["completo"])


if __name__ == "__main__":
    unittest.main()
