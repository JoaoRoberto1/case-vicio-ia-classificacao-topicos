"""Auditoria offline com dados sintéticos, sem acesso a resultados reais."""

import copy
import csv
import hashlib
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from classificacao_topicos.auditoria import _carregar_auditoria, preparar_auditoria
from classificacao_topicos.lote import preparar_lote
from classificacao_topicos.piloto import preparar_piloto


COLUNAS = ["id", "decisao", "tema_central_id", "extras_ids", "confianca", "motivo"]


def digest(caminho):
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


class AuditoriaTests(unittest.TestCase):
    def setUp(self):
        self.temporaria = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporaria.cleanup)
        self.pasta = Path(self.temporaria.name)
        self.preparacao = self.pasta / "preparacao"
        self.preparacao.mkdir()
        self.piloto = self.pasta / "piloto"
        self.lote = self.pasta / "lote"
        self.saida = self.pasta / "auditoria"
        self.csv = self.pasta / "publicacao.csv"
        self.politica = self.pasta / "politica.json"
        self.ids = [f"Q{i:04d}" for i in range(1124, 999, -1)]
        questoes = [{"id": identificador, "enunciado": f"Texto integral de {identificador}.",
                     "comando": "Analise as alternativas.", "alternativas": {"A": "Primeira.", "B": "Segunda."},
                     "disciplina_origem": "ORIGEM QUE NÃO PODE VAZAR", "assunto_origem": "RÓTULO HISTÓRICO"}
                    for identificador in self.ids]
        temas = [
            {"tema_id": "T0", "parent_id": "", "nivel": "0", "titulo": "Raiz", "caminho": "Raiz", "descricao": "", "status": "active"},
            {"tema_id": "T1", "parent_id": "T0", "nivel": "1", "titulo": "Tema", "caminho": "Raiz > Tema", "descricao": "Descrição.", "status": "active"},
            {"tema_id": "T2", "parent_id": "T0", "nivel": "1", "titulo": "Extra", "caminho": "Raiz > Extra", "descricao": "Descrição.", "status": "active"},
            {"tema_id": "T3", "parent_id": "T0", "nivel": "1", "titulo": "Inativo", "caminho": "Raiz > Inativo", "descricao": "", "status": "inactive"},
        ]
        produtos = {
            "questoes_preparadas.jsonl": "".join(json.dumps(q, ensure_ascii=False) + "\n" for q in questoes).encode("utf-8"),
            "temas_preparados.json": json.dumps(temas, ensure_ascii=False).encode("utf-8"),
        }
        for nome, conteudo in produtos.items():
            (self.preparacao / nome).write_bytes(conteudo)
        manifesto = {"schema_version": 1, "procedimento": "preparacao-v1",
                     "produtos_sha256": {nome: hashlib.sha256(conteudo).hexdigest() for nome, conteudo in produtos.items()}}
        (self.preparacao / "manifesto.json").write_text(json.dumps(manifesto), encoding="utf-8")
        prompt = self.pasta / "prompt.txt"
        prompt.write_text("${ESQUEMA_JSON}\n${CATALOGO_JSONL}\n${QUESTAO_JSON}", encoding="utf-8")
        desenvolvimento = preparar_piloto(self.preparacao, self.piloto, prompt_path=prompt, prompt_version="teste-v1")
        self.desenvolvimento = desenvolvimento["ids"]
        preparar_lote(self.preparacao, self.piloto, self.lote, prompt_path=prompt, prompt_version="teste-v1")
        self.politica.write_text(json.dumps({"schema_version": 1, "versao": "politica-v1",
                                          "auditoria": {"semente": 2026101401, "nivel_intervalo": 0.95}}), encoding="utf-8")
        self.linhas = [{"id": identificador, "decisao": "publicar", "tema_central_id": "T1", "extras_ids": "",
                        "confianca": "0.99", "motivo": ""} for identificador in self.ids]
        self.gravar_csv(self.linhas)

    def gravar_csv(self, linhas, colunas=COLUNAS):
        with self.csv.open("w", encoding="utf-8", newline="") as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=colunas, lineterminator="\n")
            escritor.writeheader()
            escritor.writerows(linhas)

    def preparar(self, saida=None, decisoes=None):
        return preparar_auditoria(self.preparacao, self.lote, decisoes or self.csv,
                                  self.politica, saida or self.saida)

    def test_sorteio_deterministico_respeita_estratos_e_ordem_original(self):
        manifesto = self.preparar()
        repetido = self.preparar(self.pasta / "auditoria_repetida")
        self.assertEqual(manifesto, repetido)
        self.assertEqual({p.name: p.read_bytes() for p in self.saida.iterdir()},
                         {p.name: p.read_bytes() for p in (self.pasta / "auditoria_repetida").iterdir()})
        d = [identificador for identificador in self.ids if identificador in self.desenvolvimento]
        r = [identificador for identificador in self.ids if identificador not in self.desenvolvimento]
        amostra = random.Random(2026101401).sample(r, 80)
        self.assertEqual(manifesto["estratos"]["desenvolvimento"]["selecionados_ids"], d)
        self.assertEqual(manifesto["estratos"]["restante"]["populacao_ids"], r)
        self.assertEqual(manifesto["estratos"]["restante"]["selecionados_ids"], amostra)
        self.assertEqual(manifesto["ids"], d + amostra)
        self.assertEqual(len(set(manifesto["ids"])), 100)
        self.assertEqual(manifesto["total_publicadas"], 125)

    def test_pacote_cego_nao_inclui_origem_modelo_confianca_ou_tema(self):
        manifesto = self.preparar()
        entradas = [json.loads(linha) for linha in (self.saida / "entradas_cegas.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([e["id"] for e in entradas], manifesto["ids"])
        for entrada in entradas:
            self.assertEqual(set(entrada), {"id", "enunciado", "comando", "alternativas"})
            self.assertEqual(entrada["alternativas"], {"A": "Primeira.", "B": "Segunda."})
        self.assertNotIn("ORIGEM QUE NÃO PODE VAZAR", (self.saida / "entradas_cegas.jsonl").read_text(encoding="utf-8"))
        self.assertEqual((self.saida / "temas_preparados.json").read_bytes(), (self.preparacao / "temas_preparados.json").read_bytes())
        self.assertNotIn("publicacao.csv", manifesto["produtos_sha256"])

    def test_censo_quando_restante_tem_menos_de_80_e_exclui_nao_publicadas(self):
        r = [identificador for identificador in self.ids if identificador not in self.desenvolvimento]
        publicadas = set(self.desenvolvimento[:5] + r[:10])
        linhas = copy.deepcopy(self.linhas)
        for linha in linhas:
            if linha["id"] not in publicadas:
                linha.update(decisao="revisar", motivo="Revisão necessária.")
        self.gravar_csv(linhas)
        manifesto = self.preparar()
        self.assertEqual(set(manifesto["ids"]), publicadas)
        self.assertEqual(manifesto["estratos"]["desenvolvimento"]["N"], 5)
        self.assertEqual(manifesto["estratos"]["restante"]["N"], 10)
        self.assertEqual(manifesto["estratos"]["restante"]["n"], 10)
        self.assertEqual(manifesto["estratos"]["restante"]["metodo"], "censo")

    def test_sem_publicadas_gera_pacote_vazio_sem_inventar_precisao(self):
        linhas = [{**linha, "decisao": "revisar", "motivo": "Revisão necessária."} for linha in self.linhas]
        self.gravar_csv(linhas)
        manifesto = self.preparar()
        self.assertEqual(manifesto["ids"], [])
        self.assertEqual(manifesto["total_publicadas"], 0)
        self.assertEqual((self.saida / "entradas_cegas.jsonl").read_bytes(), b"")
        self.assertNotIn("precisao", manifesto)
        self.assertEqual(_carregar_auditoria(self.preparacao, self.saida, self.csv)[0], manifesto)

    def test_csv_invalido_nao_sorteia_e_nao_cria_pacote(self):
        mutacoes = [
            {"decisao": "pendente"}, {"tema_central_id": "T3"}, {"tema_central_id": ""},
            {"decisao": "fora", "tema_central_id": "T1", "motivo": "Sem tema."},
            {"decisao": "revisar", "motivo": " "},
            {"decisao": "fora", "tema_central_id": "", "motivo": ""},
            {"extras_ids": "T2;T2"}, {"extras_ids": "T1"}, {"extras_ids": "T3"}, {"extras_ids": "T2;"},
            *[{"confianca": valor} for valor in ("NaN", "Infinity", "-0.1", "1.1", "true", "")],
        ]
        casos = []
        for mutacao in mutacoes:
            linhas = copy.deepcopy(self.linhas)
            linhas[0].update(mutacao)
            casos.append(linhas)
        casos.extend([self.linhas[:-1], self.linhas + [self.linhas[0]],
                      [{**self.linhas[0], "id": "Q9999"}] + self.linhas[1:]])
        for indice, linhas in enumerate(casos):
            self.gravar_csv(linhas)
            with self.subTest(caso=indice), patch("classificacao_topicos.auditoria.random.Random.sample") as sortear:
                with self.assertRaises(ValueError):
                    self.preparar()
                sortear.assert_not_called()
                self.assertFalse(self.saida.exists())

    def test_csv_com_coluna_extra_e_rejeitado(self):
        self.gravar_csv([{**linha, "modelo": "modelo"} for linha in self.linhas], COLUNAS + ["modelo"])
        with self.assertRaisesRegex(ValueError, "seis colunas"):
            self.preparar()
        self.assertFalse(self.saida.exists())

    def test_hash_de_preparacao_alterado_impede_sorteio(self):
        arquivo = self.preparacao / "questoes_preparadas.jsonl"
        arquivo.write_bytes(arquivo.read_bytes() + b"\n")
        with patch("classificacao_topicos.auditoria.random.Random.sample") as sortear:
            with self.assertRaisesRegex(ValueError, "Hash divergente"):
                self.preparar()
            sortear.assert_not_called()

    def test_manifesto_de_decisoes_e_pasta_sao_aceitos_e_vinculados(self):
        manifesto_decisoes = {
            "completo": True, "pendentes_fora": 0, "total_questoes": len(self.ids),
            "decisoes": {"publicar": len(self.ids), "revisar": 0, "fora": 0},
            "fontes_sha256": {"manifesto_lote.json": digest(self.lote / "manifesto_lote.json"),
                              "manifesto.json": digest(self.preparacao / "manifesto.json"), "politica.json": digest(self.politica)},
            "produtos_sha256": {"publicacao.csv": digest(self.csv)},
        }
        caminho = self.pasta / "manifesto_decisoes.json"
        caminho.write_text(json.dumps(manifesto_decisoes), encoding="utf-8")
        manifesto = self.preparar(decisoes=self.pasta)
        self.assertEqual(manifesto["fontes_sha256"]["manifesto_decisoes.json"], digest(caminho))
        self.assertEqual(_carregar_auditoria(self.preparacao, self.saida, self.csv)[0], manifesto)
        manifesto_decisoes["pendentes_fora"] = 1
        caminho.write_text(json.dumps(manifesto_decisoes), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "pendentes"):
            self.preparar(self.pasta / "outra_auditoria")
        self.assertFalse((self.pasta / "outra_auditoria").exists())

    def test_helper_revalida_fontes_e_snapshots_sem_lote_original(self):
        manifesto = self.preparar()
        (self.lote / "manifesto_lote.json").unlink()
        self.politica.unlink()
        carregado, temas, questoes, decisoes, hashes = _carregar_auditoria(self.preparacao, self.saida, self.csv)
        self.assertEqual(carregado, manifesto)
        self.assertEqual(set(questoes), set(self.ids))
        self.assertEqual(decisoes[self.ids[0]]["tema_central_id"], "T1")
        self.assertEqual(decisoes[self.ids[0]]["extras_ids"], [])
        self.assertEqual(temas["T1"]["status"], "active")
        self.assertTrue(all(isinstance(p, Path) and digest(p) == h for p, h in hashes.items()))
        self.gravar_csv([{**self.linhas[0], "confianca": "0.98"}] + self.linhas[1:])
        with self.assertRaisesRegex(ValueError, "decisões mudaram"):
            _carregar_auditoria(self.preparacao, self.saida, self.csv)

    def test_helper_rejeita_vazamento_mesmo_com_hash_de_produto_recalculado(self):
        self.preparar()
        arquivo = self.saida / "entradas_cegas.jsonl"
        registros = [json.loads(linha) for linha in arquivo.read_text(encoding="utf-8").splitlines()]
        registros[0]["tema_central_id"] = "T1"
        arquivo.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in registros), encoding="utf-8")
        caminho = self.saida / "manifesto_auditoria.json"
        manifesto = json.loads(caminho.read_text(encoding="utf-8"))
        manifesto["produtos_sha256"]["entradas_cegas.jsonl"] = digest(arquivo)
        caminho.write_text(json.dumps(manifesto), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Conteúdo cego"):
            _carregar_auditoria(self.preparacao, self.saida, self.csv)

    def test_helper_rejeita_selecao_adulterada(self):
        self.preparar()
        caminho = self.saida / "manifesto_auditoria.json"
        manifesto = json.loads(caminho.read_text(encoding="utf-8"))
        manifesto["ids"].reverse()
        caminho.write_text(json.dumps(manifesto), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "sorteio congelado"):
            _carregar_auditoria(self.preparacao, self.saida, self.csv)

    def test_nao_sobrescreve_auditoria_e_rejeita_area_protegida(self):
        self.preparar()
        antes = {p.name: p.read_bytes() for p in self.saida.iterdir()}
        with self.assertRaisesRegex(ValueError, "nova pasta vazia"):
            self.preparar()
        self.assertEqual(antes, {p.name: p.read_bytes() for p in self.saida.iterdir()})
        for caminho in (self.preparacao, self.lote, self.pasta / ".git" / "auditoria", self.pasta / "contexto_local" / "auditoria"):
            with self.subTest(caminho=caminho), self.assertRaises(ValueError):
                self.preparar(caminho)


if __name__ == "__main__":
    unittest.main()
