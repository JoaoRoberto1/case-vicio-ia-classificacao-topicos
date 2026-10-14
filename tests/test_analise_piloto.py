import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from classificacao_topicos.analise_piloto import analisar_piloto
from classificacao_topicos.execucao import executar_piloto
from classificacao_topicos.gemini import ErroGemini


def sha(conteudo):
    return hashlib.sha256(conteudo).hexdigest()


def escrever_json(caminho, objeto):
    caminho.write_text(json.dumps(objeto, ensure_ascii=False), encoding="utf-8")


def sugestao(identificador, central="T002", *, sem_tema=False, requer_revisao=False):
    return {"id": identificador, "tema_central_id": central, "extras_ids": [],
            "temas_alternativos": [], "sem_tema": sem_tema,
            "confianca_autodeclarada": 0.8, "motivo": "O texto menciona furto.",
            "evidencia": "furto", "requer_revisao": requer_revisao}


def retorno(resultado):
    return {"resultado": resultado,
            "resposta": {"modelVersion": "gemini-3.5-flash-lite",
                         "usageMetadata": {"promptTokenCount": 100, "totalTokenCount": 150},
                         "candidates": [{"content": {"parts": [{"text": json.dumps(resultado)}]},
                                         "finishReason": "STOP"}]},
            "duracao_segundos": 0.25}


def revisao(identificador, central="T002", *, situacao="provisorio", sem_tema=False):
    return {"id": identificador, "tema_central_id": central, "extras_ids": [],
            "temas_alternativos": [], "sem_tema": sem_tema, "situacao": situacao,
            "justificativa": "Hipótese prévia construída a partir do texto.",
            "limitacoes": ["Não é uma revisão especialista."],
            "referencia_tipo": "revisao_por_IA_sem_respostas_do_classificador"}


class AnalisePilotoTests(unittest.TestCase):
    def setUp(self):
        temporaria = tempfile.TemporaryDirectory()
        self.addCleanup(temporaria.cleanup)
        self.raiz = Path(temporaria.name)
        self.preparacao, self.piloto, self.execucao, self.revisoes, self.saida = (
            self.raiz / "artefatos" / nome
            for nome in ("preparacao", "piloto", "execucao", "revisoes", "analise"))
        for pasta in (self.preparacao, self.piloto, self.execucao, self.revisoes):
            pasta.mkdir(parents=True)
        for nome in ("questoes.jsonl", "temas.csv"):
            (self.raiz / nome).write_text("Fonte fictícia para testes.\n", encoding="utf-8")
        questoes = [{"id": f"Q{i:04d}", "enunciado": "Uma questão de furto.",
                     "comando": "Julgue.", "alternativas": {"A": "Certo", "B": "Errado"}}
                    for i in range(1, 7)]
        (self.preparacao / "questoes_preparadas.jsonl").write_text(
            "".join(json.dumps(q) + "\n" for q in questoes), encoding="utf-8")
        temas = [{"tema_id": i, "parent_id": pai, "caminho_calculado": caminho, "status": "active"}
                 for i, pai, caminho in (("T001", "", "Raiz"), ("T002", "T001", "Raiz > A"),
                                        ("T003", "T001", "Raiz > B"), ("T004", "T002", "Raiz > A > Neto"))]
        escrever_json(self.preparacao / "temas_preparados.json", temas)
        manifesto_preparacao = {
            "schema_version": 1, "procedimento": "preparacao-v1",
            "fontes_sha256": {nome: sha((self.raiz / nome).read_bytes()) for nome in ("questoes.jsonl", "temas.csv")},
            "produtos_sha256": {nome: sha((self.preparacao / nome).read_bytes())
                                for nome in ("questoes_preparadas.jsonl", "temas_preparados.json")}}
        escrever_json(self.preparacao / "manifesto.json", manifesto_preparacao)
        entradas = [{"id": q["id"], "prompt": "Analise " + q["id"],
                     "sha256_prompt": sha(("Analise " + q["id"]).encode())} for q in questoes]
        (self.piloto / "entradas.jsonl").write_text(
            "".join(json.dumps(e) + "\n" for e in entradas), encoding="utf-8")
        escrever_json(self.piloto / "manifesto_piloto.json", {
            "schema_version": 1, "procedimento": "piloto-v1", "ids": [q["id"] for q in questoes],
            "preparacao_sha256": sha((self.preparacao / "manifesto.json").read_bytes()),
            "preparacao_produtos_sha256": manifesto_preparacao["produtos_sha256"],
            "produtos_sha256": {"entradas.jsonl": sha((self.piloto / "entradas.jsonl").read_bytes())}})

    def gravar_revisoes(self, propostas):
        (self.revisoes / "proposta_teste.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in propostas), encoding="utf-8")

    def executar_simulado(self, retornos, *, limite=1):
        with patch("classificacao_topicos.execucao.carregar_configuracao",
                   return_value={"api_key": "segredo-ficticio", "model": "gemini-3.5-flash-lite"}), \
             patch("classificacao_topicos.execucao.gerar_json", side_effect=retornos):
            return executar_piloto(self.piloto, self.preparacao, self.execucao,
                                  limite=limite, intervalo_segundos=0)

    def analisar(self, *, saida=None):
        # A análise deve funcionar inclusive em ambiente sem credenciais e sem rede.
        with patch("classificacao_topicos.execucao.carregar_configuracao", side_effect=AssertionError("credencial")), \
             patch("classificacao_topicos.execucao.gerar_json", side_effect=AssertionError("modelo")), \
             patch("urllib.request.urlopen", side_effect=AssertionError("rede")):
            return analisar_piloto(self.piloto, self.preparacao, self.execucao,
                                   self.revisoes, saida or self.saida)

    def linhas(self):
        with (self.saida / "comparacao_piloto.csv").open(encoding="utf-8-sig", newline="") as arquivo:
            return {r["id"]: r for r in csv.DictReader(arquivo)}

    def test_comparacao_preserva_inconclusivos_e_distingue_ancestral_de_irmaos(self):
        propostas = [revisao("Q0001"), revisao("Q0002", "T001"), revisao("Q0003", "T003"),
                     revisao("Q0004", situacao="inconclusivo"), revisao("Q0006")]
        propostas[0]["extras_ids"] = ["T003"]
        self.gravar_revisoes(propostas)
        self.executar_simulado([retorno(sugestao(f"Q{i:04d}", "T004" if i == 2 else "T002",
                                                 requer_revisao=i == 4)) for i in range(1, 6)], limite=5)
        resumo = self.analisar()
        self.assertEqual(resumo["comparacao_central"], {
            "exata": 1, "diferenca_mesmo_ramo": 1, "divergencia": 1, "inconclusivo": 2, "sem_resposta": 1})
        self.assertEqual(resumo["status_tecnico"], {"sem_recibo": 1, "sucesso": 5})
        self.assertEqual(resumo["flags_sugestoes_validas"], {"total": 5, "requer_revisao": 1, "sem_tema": 0})
        self.assertEqual(resumo["revisoes"]["ausentes"], 1)
        linhas = self.linhas()
        self.assertEqual(linhas["Q0002"]["modelo_caminho_central"], "Raiz > A > Neto")
        self.assertEqual(linhas["Q0001"]["revisao_extras_ids"], "T003")
        self.assertEqual(linhas["Q0004"]["comparacao_central"], "inconclusivo")
        self.assertEqual(linhas["Q0005"]["revisao_situacao"], "ausente")
        self.assertEqual(linhas["Q0006"]["total_tokens_observados"], "")
        self.assertEqual(resumo["produtos_sha256"]["comparacao_piloto.csv"],
                         sha((self.saida / "comparacao_piloto.csv").read_bytes()))
        self.assertTrue(any("não estimam precisão" in s for s in resumo["limites"]))
        self.assertEqual(resumo, json.loads((self.saida / "resumo_piloto.json").read_text(encoding="utf-8")))

    def test_sem_tema_so_e_concordancia_quando_revisao_nao_e_inconclusiva(self):
        self.gravar_revisoes([revisao("Q0001", "", sem_tema=True),
                             revisao("Q0002", "", sem_tema=None, situacao="inconclusivo"),
                             revisao("Q0003")])
        self.executar_simulado([retorno(sugestao(f"Q{i:04d}", "", sem_tema=True)) for i in range(1, 4)], limite=3)
        resumo = self.analisar()
        self.assertEqual(resumo["ids_por_comparacao"]["exata"], ["Q0001"])
        self.assertEqual(resumo["ids_por_comparacao"]["inconclusivo"], ["Q0002"])
        self.assertEqual(resumo["ids_por_comparacao"]["divergencia"], ["Q0003"])
        self.assertEqual(resumo["flags_sugestoes_validas"]["sem_tema"], 3)

    def test_consumo_inclui_todas_tentativas_uma_vez_e_nao_inventa_campos(self):
        bruto = {"usageMetadata": {"promptTokenCount": 80, "totalTokenCount": 200},
                 "candidates": [{"finishReason": "MAX_TOKENS"}]}
        for _ in range(2):
            self.executar_simulado([ErroGemini("MAX_TOKENS", resposta=bruto, duracao_segundos=1.25)])
        sucesso = retorno(sugestao("Q0001"))
        sucesso["resposta"]["usageMetadata"]["candidatesTokenCount"] = 0
        self.executar_simulado([sucesso])
        sem_uso = retorno(sugestao("Q0002"))
        sem_uso["resposta"].pop("usageMetadata")
        sem_uso["duracao_segundos"] = 0.0
        self.executar_simulado([sem_uso])
        consumo = self.analisar()["consumo"]
        self.assertEqual(consumo["tentativas"], 4)
        self.assertEqual(consumo["tokens_observados"], {"promptTokenCount": 260, "totalTokenCount": 550, "candidatesTokenCount": 0})
        self.assertEqual(consumo["tentativas_sem_campo"]["totalTokenCount"], 1)
        self.assertEqual(consumo["tentativas_sem_campo"]["candidatesTokenCount"], 3)
        self.assertEqual(consumo["tentativas_sem_campo"]["thoughtsTokenCount"], 4)
        self.assertNotIn("thoughtsTokenCount", consumo["tokens_observados"])
        self.assertEqual(consumo["tentativas_sem_usage_metadata"], 1)
        self.assertEqual(consumo["duracao_chamadas_segundos_observada"], 2.75)
        self.assertEqual(consumo["versoes_retornadas"], {"gemini-3.5-flash-lite": 2})
        self.assertEqual(consumo["tentativas_sem_versao"], 2)
        self.assertEqual(self.linhas()["Q0001"]["tentativas"], "3")
        self.assertEqual(self.linhas()["Q0002"]["total_tokens_observados"], "")

    def test_erro_tecnico_e_sem_resposta_mesmo_com_recibo_e_tokens(self):
        self.gravar_revisoes([revisao("Q0001")])
        self.executar_simulado([ErroGemini("MAX_TOKENS", resposta={"usageMetadata": {"totalTokenCount": 20}},
                                          duracao_segundos=0.5)])
        resumo = self.analisar()
        self.assertEqual(resumo["status_tecnico"], {"erro": 1, "sem_recibo": 5})
        self.assertEqual(resumo["comparacao_central"]["sem_resposta"], 6)
        self.assertEqual(resumo["consumo"]["tokens_observados"], {"totalTokenCount": 20})
        linha = self.linhas()["Q0001"]
        self.assertEqual(linha["erro_tipo"], "ErroGemini")
        self.assertEqual(linha["modelo_tema_central_id"], "")

    def test_hash_de_fonte_e_checksum_recibo_adulterados_impedem_saida(self):
        self.executar_simulado([retorno(sugestao("Q0001"))])
        arquivos = (self.preparacao / "temas_preparados.json", self.piloto / "entradas.jsonl",
                    self.raiz / "questoes.jsonl", self.execucao / "Q0001.json")
        for arquivo in arquivos:
            original = arquivo.read_bytes()
            if arquivo.parent == self.execucao:
                registro = json.loads(original)
                registro["sugestao"]["tema_central_id"] = "T003"
                escrever_json(arquivo, registro)
            else:
                arquivo.write_bytes(original + b" ")
            try:
                with self.subTest(arquivo=arquivo), self.assertRaises(ValueError):
                    self.analisar()
                self.assertFalse(self.saida.exists())
            finally:
                arquivo.write_bytes(original)

    def test_revisao_duplicada_ou_com_id_inexistente_e_rejeitada(self):
        for propostas in ([revisao("Q0001"), revisao("Q0001")],
                          [revisao("Q0001", "INEXISTENTE")], [revisao("Q9999")]):
            self.gravar_revisoes(propostas)
            with self.subTest(propostas=propostas), self.assertRaises(ValueError):
                self.analisar()
            self.assertFalse(self.saida.exists())

    def test_execucao_ativa_e_destinos_protegidos_nao_recebem_saida(self):
        lock = self.execucao / ".execucao.lock"
        lock.write_text("Em execução", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "ativa"):
            self.analisar()
        lock.unlink()
        for pasta in (self.raiz, self.preparacao, self.piloto, self.execucao,
                      self.revisoes, self.revisoes / "filha", self.raiz / "contexto_local" / "analise"):
            with self.subTest(pasta=pasta), self.assertRaises(ValueError):
                self.analisar(saida=pasta)
        self.saida.mkdir()
        (self.saida / "importante.txt").write_text("preservar", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "incompatíveis"):
            self.analisar()
        self.assertEqual((self.saida / "importante.txt").read_text(), "preservar")


if __name__ == "__main__":
    unittest.main()
