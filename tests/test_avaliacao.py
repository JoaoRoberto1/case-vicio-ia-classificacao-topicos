"""Avaliação com dados exclusivamente sintéticos, sem recibos ou modelos."""

import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from classificacao_topicos.auditoria import preparar_auditoria
from classificacao_topicos.avaliacao import (
    _ancestrais, _carregar_revisoes, _comparar, avaliar_auditoria,
)
from classificacao_topicos.estatistica import estimar_precisao


def dados_json(valor):
    return (json.dumps(valor, ensure_ascii=False) + "\n").encode("utf-8")


def digest(conteudo):
    return hashlib.sha256(conteudo).hexdigest()


def temas_sinteticos():
    definicoes = [("RA", "", 0), ("P", "RA", 1), ("C", "P", 2),
                  ("S", "P", 2), ("RB", "", 0), ("T", "RB", 1), ("I", "RB", 1)]
    return {identificador: {
        "tema_id": identificador, "parent_id": pai, "nivel": str(nivel),
        "titulo": identificador, "caminho": identificador, "descricao": "Descrição sintética.",
        "status": "inactive" if identificador == "I" else "active",
    } for identificador, pai, nivel in definicoes}


def referencia(identificador, centrais=None, **ajustes):
    return {"id": identificador, "temas_centrais_aceitaveis": ["C"] if centrais is None else centrais,
            "sem_tema": False, "situacao": "provisorio", "justificativa": "Referência sintética.",
            "limitacoes": "Sem avaliação especialista.", "tipo_referencia": "IA_sem_especialista",
            "responsavel": "Teste", **ajustes}


class ComparacaoCentralTest(unittest.TestCase):
    def setUp(self):
        self.temas = temas_sinteticos()
        self.ancestrais = _ancestrais(self.temas)

    def comparar(self, central, **revisao):
        return _comparar(central, referencia("Q0001", **revisao), self.temas, self.ancestrais)

    def test_exata_e_parentesco_imediato_nas_duas_direcoes(self):
        self.assertEqual(self.comparar("C")[0], "exata")
        self.assertEqual(self.comparar("P")[0], "pai_filho_direto")
        self.assertEqual(self.comparar("C", centrais=["P"])[0], "pai_filho_direto")
        self.assertEqual(self.comparar("RA", centrais=["P"])[0], "pai_filho_direto")

    def test_irmaos_e_avo_neto_nao_sao_aceitos(self):
        self.assertEqual(self.comparar("S")[:2], ("divergencia", "temas_irmaos"))
        self.assertEqual(self.comparar("RA")[:2], ("divergencia", "ancestralidade_distante"))
        self.assertEqual(self.comparar("C", centrais=["RA"])[:2], ("divergencia", "ancestralidade_distante"))
        self.assertEqual(self.comparar("T")[:2], ("divergencia", "ramos_distintos"))

    def test_varios_aceitaveis_priorizam_exato_e_relacao_imediata(self):
        self.assertEqual(self.comparar("C", centrais=["T", "P", "C"])[0], "exata")
        self.assertEqual(self.comparar("C", centrais=["RA", "P"])[0], "pai_filho_direto")

    def test_inconclusivo_nunca_se_torna_acerto_mesmo_com_id_igual(self):
        self.assertEqual(self.comparar("C", situacao="inconclusivo")[0], "inconclusivo")
        self.assertEqual(self.comparar("C", situacao="inconclusivo", sem_tema=None)[0], "inconclusivo")

    def test_referencia_fora_contra_publicada_e_erro(self):
        self.assertEqual(self.comparar("C", centrais=[], sem_tema=True)[:2],
                         ("divergencia", "referencia_sem_tema"))

    def test_hierarquia_reconstruida_rejeita_pai_ausente_ciclo_e_nivel(self):
        for campo, valor in (("parent_id", "ausente"), ("parent_id", "C"), ("nivel", "0")):
            with self.subTest(campo=campo, valor=valor):
                temas = temas_sinteticos()
                temas["P"][campo] = valor
                with self.assertRaises(ValueError):
                    _ancestrais(temas)


class ContratoRevisoesTest(unittest.TestCase):
    def setUp(self):
        self.temporaria = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporaria.cleanup)
        self.pasta = Path(self.temporaria.name)
        self.arquivo = self.pasta / "revisoes.jsonl"

    def carregar(self, registros):
        self.arquivo.write_bytes(b"".join(dados_json(r) for r in registros))
        return _carregar_revisoes(self.arquivo, {"Q0001"}, temas_sinteticos())

    def test_contrato_invalido_ids_duplicados_faltantes_e_extras(self):
        casos = [[], [referencia("Q0002")], [referencia("Q0001"), referencia("Q0001")],
                 [referencia("Q0001", centrais=["I"])], [referencia("Q0001", centrais=["ausente"])],
                 [referencia("Q0001", centrais=["C", "C"])],
                 [referencia("Q0001", sem_tema=1)], [referencia("Q0001", sem_tema=None)],
                 [referencia("Q0001", sem_tema=True)], [referencia("Q0001", centrais=[])],
                 [referencia("Q0001", tipo_referencia="especialista")],
                 [referencia("Q0001", limitacoes=[])], [referencia("Q0001", situacao=[])],
                 [referencia("Q0001", inesperado="não permitido")]]
        for registros in casos:
            with self.subTest(registros=registros), self.assertRaises(ValueError):
                self.carregar(registros)

    def test_chaves_json_duplicadas_rejeitadas(self):
        self.arquivo.write_text('{"id":"Q0001","id":"Q0001"}', encoding="utf-8")
        with self.assertRaises(ValueError):
            _carregar_revisoes(self.arquivo, {"Q0001"}, temas_sinteticos())

    def test_jsonl_preserva_separadores_unicode_e_hash(self):
        revisao = referencia("Q0001", justificativa="Trecho A\u2028Trecho B\u0085Trecho C")
        registros, hashes = self.carregar([revisao])
        self.assertEqual(registros["Q0001"], revisao)
        self.assertEqual(hashes[self.arquivo], digest(self.arquivo.read_bytes()))


class AvaliacaoAuditoriaTest(unittest.TestCase):
    def setUp(self):
        self.temporaria = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporaria.cleanup)
        self.raiz = Path(self.temporaria.name)
        self.preparacao, self.lote = self.raiz / "preparacao", self.raiz / "lote"
        self.auditoria, self.saida = self.raiz / "auditoria", self.raiz / "avaliacao"
        self.decisoes, self.revisoes = self.raiz / "publicacao.csv", self.raiz / "revisoes.jsonl"
        self.preparacao.mkdir()
        self.lote.mkdir()
        self.ids = [f"Q{i:04d}" for i in range(1, 123)]
        questoes = [{"id": i, "enunciado": "Enunciado sintético.", "comando": "Comando.",
                     "alternativas": {"A": "Hipótese A.", "B": "Hipótese B."},
                     "disciplina_origem": "Origem sintética"} for i in self.ids]
        produtos = {"questoes_preparadas.jsonl": b"".join(dados_json(q) for q in questoes),
                    "temas_preparados.json": dados_json(list(temas_sinteticos().values()))}
        for nome, conteudo in produtos.items():
            (self.preparacao / nome).write_bytes(conteudo)
        m_prep = {"schema_version": 1, "procedimento": "preparacao-v1",
                  "produtos_sha256": {nome: digest(conteudo) for nome, conteudo in produtos.items()}}
        prep_bytes = dados_json(m_prep)
        (self.preparacao / "manifesto.json").write_bytes(prep_bytes)
        entradas = b"".join(dados_json({"id": i, "prompt": "Prompt sintético.",
                                       "sha256_prompt": digest("Prompt sintético.".encode("utf-8"))}) for i in self.ids)
        (self.lote / "entradas.jsonl").write_bytes(entradas)
        m_lote = {"schema_version": 1, "procedimento": "lote-v1", "ids": self.ids,
                  "desenvolvimento_ids": self.ids[:20], "restante_ids": self.ids[20:],
                  "preparacao_sha256": digest(prep_bytes), "preparacao_produtos_sha256": m_prep["produtos_sha256"],
                  "produtos_sha256": {"entradas.jsonl": digest(entradas)}}
        (self.lote / "manifesto_lote.json").write_bytes(dados_json(m_lote))
        self.politica = self.raiz / "politica.json"
        self.politica.write_bytes(dados_json({"schema_version": 1, "versao": "politica-v1",
                                              "auditoria": {"semente": 2026101401, "nivel_intervalo": 0.9}}))
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=("id", "decisao", "tema_central_id", "extras_ids", "confianca", "motivo"), lineterminator="\n")
        writer.writeheader()
        for indice, identificador in enumerate(self.ids):
            writer.writerow({"id": identificador, "decisao": "publicar" if indice < 120 else "revisar",
                             "tema_central_id": "C", "extras_ids": "", "confianca": "0.99",
                             "motivo": "" if indice < 120 else "Revisão sintética."})
        self.decisoes.write_text(buffer.getvalue(), encoding="utf-8")
        self.manifesto = preparar_auditoria(self.preparacao, self.lote, self.decisoes, self.politica, self.auditoria)
        self.referencias = {i: referencia(i) for i in self.manifesto["ids"]}
        self.gravar_referencias()

    def gravar_referencias(self):
        self.revisoes.write_bytes(b"".join(dados_json(r) for r in self.referencias.values()))

    def avaliar(self, saida=None):
        return avaliar_auditoria(self.preparacao, self.auditoria, self.decisoes,
                                  self.revisoes, saida or self.saida)

    def test_integracao_ponderada_intervalo_condicional_e_cobertura_observada(self):
        erros = self.manifesto["estratos"]["restante"]["selecionados_ids"][:8]
        for identificador in erros:
            self.referencias[identificador] = referencia(identificador, ["T"])
        self.gravar_referencias()
        relatorio = self.avaliar()
        esperado = estimar_precisao(20, 0, 0, 100, 80, 8, 0, nivel=0.9)
        self.assertEqual(relatorio["precisao_condicional"], esperado)
        self.assertEqual(esperado["cenarios"]["conservador"]["ponto_exato"], "11/12")
        self.assertNotEqual(esperado["cenarios"]["conservador"]["ponto"], 92 / 100)
        self.assertEqual(relatorio["cobertura"]["intervalo"], [120 / 122] * 2)
        self.assertFalse(relatorio["cobertura"]["inferencia_futura"])
        self.assertFalse(esperado["inclui_incerteza_referencia"])
        self.assertEqual(relatorio["comparacao_central"], {"exata": 92, "pai_filho_direto": 0, "divergencia": 8, "inconclusivo": 0})
        self.assertEqual(relatorio["produtos_sha256"]["comparacao_auditoria.csv"], digest((self.saida / "comparacao_auditoria.csv").read_bytes()))
        self.assertEqual(set(p.name for p in self.saida.iterdir()), {"comparacao_auditoria.csv", "relatorio_avaliacao.json"})

    def test_inconclusivo_e_fora_entram_nos_estratos_sem_virar_acerto(self):
        self.referencias["Q0001"] = referencia("Q0001", situacao="inconclusivo")
        self.referencias["Q0002"] = referencia("Q0002", [], sem_tema=True)
        self.referencias["Q0003"] = referencia("Q0003", ["P"])
        self.gravar_referencias()
        relatorio = self.avaliar()
        self.assertEqual(relatorio["precisao_condicional"], estimar_precisao(20, 1, 1, 100, 80, 0, 0, nivel=0.9))
        self.assertEqual(relatorio["estratos"]["desenvolvimento"]["acertos"], 18)
        with (self.saida / "comparacao_auditoria.csv").open(encoding="utf-8-sig", newline="") as arquivo:
            linhas = {linha["id"]: linha for linha in csv.DictReader(arquivo)}
        self.assertEqual(linhas["Q0001"]["comparacao_central"], "inconclusivo")
        self.assertEqual(linhas["Q0001"]["acerto_condicional"], "")
        self.assertEqual(linhas["Q0002"]["detalhe_comparacao"], "referencia_sem_tema")
        self.assertEqual(linhas["Q0003"]["comparacao_central"], "pai_filho_direto")

    def test_determinismo_preservacao_fontes_e_referencias_fora_de_ordem(self):
        fontes = [p for p in self.raiz.rglob("*") if p.is_file()]
        antes = {p: p.read_bytes() for p in fontes}
        primeiro = self.avaliar()
        produtos = {p.name: p.read_bytes() for p in self.saida.iterdir()}
        self.assertEqual(primeiro, self.avaliar())
        self.assertEqual(produtos, {p.name: p.read_bytes() for p in self.saida.iterdir()})
        self.assertEqual(antes, {p: p.read_bytes() for p in fontes})
        self.referencias = dict(reversed(list(self.referencias.items())))
        self.gravar_referencias()
        outro = self.avaliar()
        self.assertEqual(primeiro["precisao_condicional"], outro["precisao_condicional"])
        self.assertEqual(produtos["comparacao_auditoria.csv"], (self.saida / "comparacao_auditoria.csv").read_bytes())

    def test_hashes_fonte_e_pacote_alterados_rejeitados_sem_saida(self):
        caminhos = [self.decisoes, self.preparacao / "questoes_preparadas.jsonl", self.auditoria / "politica.json"]
        for caminho in caminhos:
            with self.subTest(caminho=caminho):
                original = caminho.read_bytes()
                caminho.write_bytes(original + b"\n")
                try:
                    with self.assertRaises(ValueError):
                        self.avaliar()
                    self.assertFalse(self.saida.exists())
                finally:
                    caminho.write_bytes(original)

    def test_revisao_ausente_rejeitada_sem_saida(self):
        self.referencias.pop(next(iter(self.referencias)))
        self.gravar_referencias()
        with self.assertRaisesRegex(ValueError, "todos e somente"):
            self.avaliar()
        self.assertFalse(self.saida.exists())

    def test_fonte_alterada_durante_calculo_rejeitada_sem_saida(self):
        def calcular(*args, **kwargs):
            self.revisoes.write_bytes(self.revisoes.read_bytes() + b"\n")
            return estimar_precisao(*args, **kwargs)
        with patch("classificacao_topicos.avaliacao.estimar_precisao", side_effect=calcular):
            with self.assertRaisesRegex(ValueError, "mudou durante"):
                self.avaliar()
        self.assertFalse(self.saida.exists())

    def test_destinos_protegidos_e_diretorio_com_outros_arquivos(self):
        for destino in (self.preparacao, self.auditoria / "resultado", self.raiz / ".git" / "resultado",
                        self.raiz / "contexto_local" / "resultado"):
            with self.subTest(destino=destino), self.assertRaises(ValueError):
                self.avaliar(destino)
        self.saida.mkdir()
        protegido = self.saida / "anotacao.txt"
        protegido.write_bytes(b"preservar")
        with self.assertRaisesRegex(ValueError, "incompatíveis"):
            self.avaliar()
        self.assertEqual(protegido.read_bytes(), b"preservar")

    def test_sem_publicadas_precisao_indefinida_csv_so_com_cabecalho(self):
        conteudo = self.decisoes.read_text(encoding="utf-8").replace(",publicar,C,,0.99,\n", ",revisar,C,,0.99,Revisão sintética.\n")
        self.decisoes.write_text(conteudo, encoding="utf-8")
        self.auditoria = self.raiz / "auditoria_sem_publicadas"
        preparar_auditoria(self.preparacao, self.lote, self.decisoes, self.politica, self.auditoria)
        self.revisoes.write_bytes(b"")
        relatorio = self.avaliar()
        self.assertEqual(relatorio["total_revisadas"], 0)
        self.assertEqual(relatorio["cobertura"]["intervalo"], [0, 0])
        self.assertIsNone(relatorio["precisao_condicional"]["cenarios"]["conservador"]["ponto"])
        with (self.saida / "comparacao_auditoria.csv").open(encoding="utf-8-sig", newline="") as arquivo:
            self.assertEqual(list(csv.DictReader(arquivo)), [])


if __name__ == "__main__":
    unittest.main()
