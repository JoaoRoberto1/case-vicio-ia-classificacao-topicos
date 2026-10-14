"""Integridade do lote completo e preservação dos casos de desenvolvimento."""

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from classificacao_topicos.lote import preparar_lote
from classificacao_topicos.piloto import preparar_piloto
from classificacao_topicos.preparacao import executar_preparacao


RAIZ = Path(__file__).resolve().parents[1]


def gravar_preparacao(pasta: Path) -> list[str]:
    pasta.mkdir()
    ids = [f"Q{i:04d}" for i in range(35, 0, -1)]
    questoes = [
        {
            "id": identificador, "enunciado": f"Enunciado {identificador} com ação.",
            "comando": "Considere o conteúdo completo.",
            "alternativas": {"A": "Primeira hipótese.", "B": "Segunda hipótese."},
            "disciplina_origem": f"ORIGEM NÃO DEVE APARECER {indice % 3}",
        }
        for indice, identificador in enumerate(ids)
    ]
    temas = [
        {"tema_id": "T0", "parent_id": "", "nivel": "0", "titulo": "Raiz", "caminho": "Raiz", "descricao": "Disciplina (root). Histórico 123", "status": "active"},
        {"tema_id": "T1", "parent_id": "T0", "nivel": "1", "titulo": "Tema", "caminho": "Raiz > Tema", "descricao": "Descrição substantiva.", "status": "active"},
        {"tema_id": "T2", "parent_id": "T0", "nivel": "1", "titulo": "Antigo", "caminho": "Raiz > Antigo", "descricao": "Descrição antiga.", "status": "inactive"},
    ]
    produtos = {
        "questoes_preparadas.jsonl": "".join(json.dumps(q, ensure_ascii=False) + "\n" for q in questoes).encode("utf-8"),
        "temas_preparados.json": json.dumps(temas, ensure_ascii=False).encode("utf-8"),
        "diagnostico.json": b'{"total":35}\n',
    }
    for nome, conteudo in produtos.items():
        (pasta / nome).write_bytes(conteudo)
    manifesto = {
        "schema_version": 1, "procedimento": "preparacao-v1",
        "produtos_sha256": {nome: hashlib.sha256(conteudo).hexdigest() for nome, conteudo in produtos.items()},
    }
    (pasta / "manifesto.json").write_text(json.dumps(manifesto), encoding="utf-8")
    return ids


def ler_entradas(pasta: Path) -> list[dict]:
    with (pasta / "entradas.jsonl").open(encoding="utf-8") as arquivo:
        return [json.loads(linha) for linha in arquivo if linha.strip()]


class PrepararLoteTest(unittest.TestCase):
    def setUp(self):
        self.temporaria = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporaria.cleanup)
        self.pasta = Path(self.temporaria.name)
        self.preparacao = self.pasta / "preparacao"
        self.piloto = self.pasta / "desenvolvimento"
        self.saida = self.pasta / "lote"
        self.ids = gravar_preparacao(self.preparacao)
        self.prompt = self.pasta / "prompt.txt"
        self.prompt.write_text("Contrato\n${ESQUEMA_JSON}\nCatálogo\n${CATALOGO_JSONL}\nQuestão\n${QUESTAO_JSON}\n", encoding="utf-8")
        self.manifesto_piloto = preparar_piloto(
            self.preparacao, self.piloto, prompt_path=self.prompt, prompt_version="teste-v2"
        )

    def preparar(self, saida=None):
        return preparar_lote(
            self.preparacao, self.piloto, saida or self.saida,
            prompt_path=self.prompt, prompt_version="teste-v2",
        )

    def test_todos_ids_na_ordem_original_e_desenvolvimento_congelado(self):
        manifesto = self.preparar()
        entradas = ler_entradas(self.saida)
        self.assertEqual(manifesto["procedimento"], "lote-v1")
        self.assertEqual(manifesto["schema_version"], 1)
        self.assertEqual(manifesto["ids"], self.ids)
        self.assertEqual([e["id"] for e in entradas], self.ids)
        self.assertEqual(len(set(manifesto["ids"])), 35)
        self.assertEqual(manifesto["desenvolvimento_ids"], self.manifesto_piloto["ids"])
        self.assertEqual(len(manifesto["desenvolvimento_ids"]), 20)
        restante = [q for q in self.ids if q not in self.manifesto_piloto["ids"]]
        self.assertEqual(manifesto["restante_ids"], restante)
        self.assertFalse(set(restante) & set(manifesto["desenvolvimento_ids"]))
        self.assertEqual(set(restante) | set(manifesto["desenvolvimento_ids"]), set(self.ids))
        self.assertNotIn("motivos", manifesto)
        self.assertIn("não cria um novo conjunto de desenvolvimento", manifesto["data_exposure"])
        self.assertIn("já foram inspecionados", manifesto["data_exposure"])
        self.assertIn("não é conjunto nunca visto", manifesto["restante_uso"])

    def test_catalogo_e_prompts_do_desenvolvimento_sao_identicos_byte_a_byte(self):
        manifesto = self.preparar()
        lote_por_id = {entrada["id"]: entrada for entrada in ler_entradas(self.saida)}
        for anterior in ler_entradas(self.piloto):
            atual = lote_por_id[anterior["id"]]
            self.assertEqual(atual, anterior)
            self.assertEqual(atual["prompt"].encode("utf-8"), anterior["prompt"].encode("utf-8"))
        self.assertEqual(manifesto["prompt_sha256"], self.manifesto_piloto["prompt_sha256"])
        self.assertEqual(manifesto["prompt_version"], self.manifesto_piloto["prompt_version"])
        self.assertEqual(manifesto["total_temas_ativos_no_prompt"], 2)
        for entrada in lote_por_id.values():
            self.assertIn('"id": "T0"', entrada["prompt"])
            self.assertIn('"id": "T1"', entrada["prompt"])
            self.assertNotIn('"id": "T2"', entrada["prompt"])
            self.assertNotIn("ORIGEM NÃO DEVE APARECER", entrada["prompt"])
            self.assertNotIn("Histórico 123", entrada["prompt"])

    def test_hashes_reproducao_e_entradas_preservadas(self):
        arquivos_fontes = [*self.preparacao.iterdir(), *self.piloto.iterdir(), self.prompt]
        fontes_antes = {caminho: caminho.read_bytes() for caminho in arquivos_fontes}
        manifesto = self.preparar()
        primeira = {p.name: p.read_bytes() for p in self.saida.iterdir()}
        self.assertEqual(manifesto, self.preparar())
        self.assertEqual(primeira, {p.name: p.read_bytes() for p in self.saida.iterdir()})
        self.assertEqual(fontes_antes, {p: p.read_bytes() for p in arquivos_fontes})
        self.assertEqual(manifesto["produtos_sha256"]["entradas.jsonl"], hashlib.sha256((self.saida / "entradas.jsonl").read_bytes()).hexdigest())
        self.assertEqual(manifesto["desenvolvimento_manifesto_sha256"], hashlib.sha256((self.piloto / "manifesto_piloto.json").read_bytes()).hexdigest())
        self.assertEqual(manifesto["preparacao_sha256"], hashlib.sha256((self.preparacao / "manifesto.json").read_bytes()).hexdigest())

    def test_piloto_vinculado_a_outra_preparacao_e_rejeitado(self):
        caminho = self.preparacao / "manifesto.json"
        manifesto = json.loads(caminho.read_text(encoding="utf-8"))
        manifesto["observacao"] = "Outra revisão do manifesto"
        caminho.write_text(json.dumps(manifesto), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "outra preparação"):
            self.preparar()
        self.assertFalse(self.saida.exists())

    def test_todos_produtos_de_preparacao_e_desenvolvimento_tem_hash_validado(self):
        produto = self.preparacao / "diagnostico.json"
        original = produto.read_bytes()
        produto.write_bytes(b"adulterado")
        with self.assertRaisesRegex(ValueError, "Hash divergente"):
            self.preparar()
        produto.write_bytes(original)
        (self.piloto / "entradas.jsonl").write_bytes(b"adulterado")
        with self.assertRaisesRegex(ValueError, "Hash divergente"):
            self.preparar()
        self.assertFalse(self.saida.exists())

    def test_hash_individual_e_conferido_mesmo_quando_hash_do_arquivo_confere(self):
        entradas = ler_entradas(self.piloto)
        entradas[0]["sha256_prompt"] = "0" * 64
        conteudo = "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entradas).encode("utf-8")
        (self.piloto / "entradas.jsonl").write_bytes(conteudo)
        manifesto = dict(self.manifesto_piloto)
        manifesto["produtos_sha256"] = {"entradas.jsonl": hashlib.sha256(conteudo).hexdigest()}
        (self.piloto / "manifesto_piloto.json").write_text(json.dumps(manifesto), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Hash individual"):
            self.preparar()

    def test_particao_invalida_do_desenvolvimento_e_rejeitada(self):
        caminho = self.piloto / "manifesto_piloto.json"
        for mutacao in (
            {"ids": [self.ids[0]] * 20},
            {"ids": ["Q9999"] + self.manifesto_piloto["ids"][1:]},
            {"restante_ids": []}, {"tamanho": True},
        ):
            caminho.write_text(json.dumps({**self.manifesto_piloto, **mutacao}), encoding="utf-8")
            with self.subTest(mutacao=mutacao), self.assertRaises(ValueError):
                self.preparar()
        self.assertFalse(self.saida.exists())

    def test_saida_separada_e_pastas_protegidas(self):
        for destino in (
            self.preparacao, self.preparacao / "filho", self.piloto,
            self.piloto / "filho", self.pasta, self.pasta / ".git" / "lote",
            self.pasta / "contexto_local" / "lote", RAIZ / "prompts" / "lote",
        ):
            with self.subTest(destino=destino), self.assertRaises(ValueError):
                self.preparar(destino)
        self.saida.mkdir()
        (self.saida / "manifesto_piloto.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "contém um piloto"):
            self.preparar()

    def test_template_nao_pode_ser_sobrescrito_por_produto(self):
        self.saida.mkdir()
        caminho = self.saida / "entradas.jsonl"
        caminho.write_bytes(self.prompt.read_bytes())
        antes = caminho.read_bytes()
        with self.assertRaisesRegex(ValueError, "coincidir"):
            preparar_lote(self.preparacao, self.piloto, self.saida, prompt_path=caminho, prompt_version="v2")
        self.assertEqual(caminho.read_bytes(), antes)

    def test_manifesto_nao_permanece_completo_se_substituicao_final_falhar(self):
        self.preparar()
        substituir = os.replace

        def falhar_no_manifesto(origem, destino):
            if Path(destino).name == "manifesto_lote.json":
                raise OSError("Falha simulada de gravação final.")
            substituir(origem, destino)

        with patch("classificacao_topicos.lote.os.replace", side_effect=falhar_no_manifesto):
            with self.assertRaisesRegex(OSError, "Falha simulada"):
                self.preparar()
        self.assertFalse((self.saida / "manifesto_lote.json").exists())
        self.assertTrue((self.saida / "entradas.jsonl").is_file())

    def test_manifesto_de_saida_sinalizado_como_link_e_rejeitado(self):
        alvo = (self.saida / "manifesto_lote.json").resolve()
        original = Path.is_symlink
        with patch.object(Path, "is_symlink", lambda caminho: caminho == alvo or original(caminho)):
            with self.assertRaisesRegex(ValueError, "arquivo comum"):
                self.preparar()
        self.assertFalse(self.saida.exists())

    def test_lote_real_v2_preserva_359_ids_e_20_prompts_do_piloto(self):
        preparacao = self.pasta / "preparacao_real"
        piloto = self.pasta / "piloto_real"
        saida = self.pasta / "lote_real"
        prompt = RAIZ / "prompts" / "classificacao_v2.txt"
        self.assertTrue(prompt.is_file())
        executar_preparacao(RAIZ, preparacao)
        desenvolvimento = preparar_piloto(preparacao, piloto, prompt_path=prompt, prompt_version="classificacao-v2")
        manifesto = preparar_lote(preparacao, piloto, saida, prompt_path=prompt, prompt_version="classificacao-v2")
        self.assertEqual(len(manifesto["ids"]), 359)
        self.assertEqual(len(manifesto["restante_ids"]), 339)
        self.assertEqual(manifesto["total_temas_ativos_no_prompt"], 375)
        self.assertEqual(manifesto["desenvolvimento_ids"], desenvolvimento["ids"])
        por_id = {e["id"]: e for e in ler_entradas(saida)}
        self.assertEqual(len(por_id), 359)
        for entrada in ler_entradas(piloto):
            self.assertEqual(entrada, por_id[entrada["id"]])
            self.assertEqual(entrada["prompt"].encode("utf-8"), por_id[entrada["id"]]["prompt"].encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
