"""Integridade do cache e fronteira entre textos permitidos e codificador."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from classificacao_experimentos.entradas import (
    carregar_cache, construir_registros, hash_texto, validar_cache,
)
from classificacao_topicos.pipeline import _json


RAIZ = Path(__file__).resolve().parents[1]


def fixture():
    questoes = [
        {"id": "D1", "enunciado": "Pigmento âmbar.", "comando": "Leia.",
         "alternativas": {"a": "Amarelo", "b": "Azul"}},
        {"id": "R1", "enunciado": "Texto reservado.", "comando": "Leia.",
         "alternativas": {"a": "Exemplo"}},
    ]
    temas = [
        {"tema_id": "T1", "titulo": "Pigmento", "caminho": "Catálogo > Pigmento",
         "descricao": "Cor de tinta.", "status": "active", "nivel": "1"},
        {"tema_id": "RAIZ", "titulo": "Catálogo", "caminho": "Catálogo",
         "descricao": "", "status": "active", "nivel": "0"},
        {"tema_id": "INATIVO", "titulo": "Histórico", "caminho": "Catálogo > Histórico",
         "descricao": "Antigo.", "status": "inactive", "nivel": "1"},
    ]
    registros = construir_registros(questoes, temas, {"D1"})
    cache = {"schema": "embeddings_e5_v1", "dimensoes": 2, "questoes": {}, "temas": {}}
    for r in registros:
        campo = "questoes" if r["tipo"] == "questao" else "temas"
        cache[campo][r["id"]] = {
            "vetor": [0.6, 0.8], "texto_sha256": r["texto_sha256"],
            "tokens": 10, "janelas": 1,
        }
    return questoes, temas, registros, cache


class TestEntradasM3(unittest.TestCase):
    def test_construcao_exclui_reserva_raiz_e_inativo_sem_metadados(self):
        questoes, temas, registros, _ = fixture()
        alteradas = deepcopy(questoes)
        alteradas[0].update({"disciplina_origem": "Segredo", "coorte": "Oculta",
                             "assunto_origem": "Privado"})
        alteradas[1]["enunciado"] = "Outro conteúdo reservado."
        self.assertEqual(registros, construir_registros(alteradas, temas, {"D1"}))
        self.assertEqual([(r["tipo"], r["id"]) for r in registros],
                         [("questao", "D1"), ("tema", "T1")])
        self.assertNotIn("Segredo", json.dumps(registros))

    def test_hash_nao_depende_de_id_ou_ordem_das_alternativas(self):
        questoes, _, _, _ = fixture()
        original = questoes[0]
        alterada = deepcopy(original)
        alterada["id"] = "OUTRO"
        alterada["alternativas"] = {"x": "Azul", "y": "Amarelo"}
        self.assertEqual(hash_texto("questao", original), hash_texto("questao", alterada))
        alterada["comando"] = "Comando diferente."
        self.assertNotEqual(hash_texto("questao", original), hash_texto("questao", alterada))

    def test_ids_ausentes_ou_duplicados_recusados(self):
        questoes, temas, _, _ = fixture()
        for qs, ts, permitidos in (
            (questoes, temas, {"ausente"}),
            (questoes + [questoes[0]], temas, {"D1"}),
            (questoes, temas + [temas[0]], {"D1"}),
        ):
            with self.subTest(permitidos=permitidos), self.assertRaises(ValueError):
                construir_registros(qs, ts, permitidos)

    def test_cache_precisa_cobertura_exata_texto_e_vetores_validos(self):
        _, _, registros, original = fixture()
        validar_cache(original, registros, 2)
        corrompidos = []
        for campo, valor in (
            ("vetor", [float("nan"), 1]), ("vetor", [0, 0]),
            ("vetor", [True, 0]), ("vetor", [0.6, 0.8, 0]),
            ("texto_sha256", "errado"), ("tokens", -1), ("janelas", 0),
        ):
            c = deepcopy(original)
            c["questoes"]["D1"][campo] = valor
            corrompidos.append(c)
        c = deepcopy(original)
        c["questoes"]["R1"] = c["questoes"]["D1"]
        corrompidos.append(c)
        c = deepcopy(original)
        c["temas"] = {}
        corrompidos.append(c)
        for cache in corrompidos:
            with self.subTest(cache=str(cache)[:60]), self.assertRaises(ValueError):
                validar_cache(cache, registros, 2)

    def test_carregador_confere_hash_configuracao_e_conteudo(self):
        _, _, registros, cache = fixture()
        pasta_tmp = RAIZ / "tmp"
        pasta_tmp.mkdir(exist_ok=True)
        temporaria = tempfile.TemporaryDirectory(prefix="teste-cache-m3-", dir=pasta_tmp)
        pasta = Path(temporaria.name).resolve()
        self.assertTrue(pasta.is_relative_to(pasta_tmp.resolve()))
        try:
            config = {"preparacao": {"dimensoes": 2}, "modelo": "sintetico"}
            conteudo = _json(cache)
            sha = hashlib.sha256(conteudo).hexdigest()
            (pasta / "vetores.json").write_bytes(conteudo)
            (pasta / "manifesto.json").write_bytes(_json({
                "produtos_sha256": {"vetores.json": sha}, "configuracao": config,
            }))
            carregado, _ = carregar_cache(pasta, registros, config)
            self.assertEqual(carregado["sha256"], sha)
            with self.assertRaisesRegex(ValueError, "Configuração"):
                carregar_cache(pasta, registros, {**config, "modelo": "outro"})
            (pasta / "vetores.json").write_bytes(conteudo + b"\n")
            with self.assertRaisesRegex(ValueError, "adulterado"):
                carregar_cache(pasta, registros, config)
        finally:
            if not pasta.resolve().is_relative_to(pasta_tmp.resolve()):
                raise AssertionError("Limpeza fora da pasta temporária permitida.")
            temporaria.cleanup()


if __name__ == "__main__":
    unittest.main()
