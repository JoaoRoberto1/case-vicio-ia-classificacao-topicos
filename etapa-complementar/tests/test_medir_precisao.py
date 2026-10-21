"""Benchmark M8: integridade e fronteiras usando apenas dados sintéticos."""

from contextlib import ExitStack
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


_SPEC = importlib.util.spec_from_file_location(
    "medir_precisao_testado", Path(__file__).resolve().parents[1] / "scripts/medir_precisao.py")
bench = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(bench)


def sinteticos():
    ids = [f"sintetica-{n:03}" for n in range(659)]
    contexto = {"questoes": [{"id": i, "texto": "Conteúdo exclusivamente sintético."} for i in ids],
                "protocolo": {"desenvolvimento_ids": ids[:80], "reserva_ids": ids[80:100], "avaliacao_ids": ids[100:]},
                "cache": {}}
    modelo = {"treino_ids": ids[:100], "receitas": ["sinais_small"]}
    politica = {"receita": "sinais_small", "habilitada": True}
    esperados = [{"id": i, "receita": "sinais_small", "score": .4, "confianca": .8,
                  "top_candidatos": [{"tema_id": "sintetico", "score": .4}],
                  "publicaria_politica_candidata": True} for i in ids[100:]]
    return contexto, modelo, politica, esperados


class MotorSintetico:
    def __init__(self):
        self.ids = []

    def predizer(self, q, modelo, receita):
        if q["id"] in modelo["treino_ids"]:
            raise AssertionError("Treino entrou na inferência.")
        self.ids.append(q["id"])
        return {"id": q["id"], "receita": receita, "score": .4,
                "top_candidatos": [{"tema_id": "sintetico", "score": .4}]}

    def treinar(self, *args):
        raise AssertionError("Benchmark não deve treinar.")


class BenchmarkPrecisaoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        self.contexto, self.modelo, self.politica, self.esperados = sinteticos()

    def escrever(self, nome, valor):
        path = self.raiz / nome
        path.parent.mkdir(parents=True, exist_ok=True)
        conteudo = valor if isinstance(valor, bytes) else bench.m5._json(valor)
        path.write_bytes(conteudo)
        return bench._sha(conteudo)

    def bundle(self):
        fontes = {"fonte-sintetica.json": self.escrever("fonte-sintetica.json", {"origem": "sintética"})}
        nome = f"{bench.ARTEFATOS}/sugestoes_avaliacao.jsonl"
        produtos = {nome: self.escrever(nome, bench._jsonl(self.esperados))}
        return {"motor": MotorSintetico(), "modelo": self.modelo, "politica": self.politica,
                "calibrador": {"origem": "final80OOF"}, "fontes": fontes, "produtos": produtos,
                "implementacao": fontes.copy(), "assinaturas": {**fontes, **produtos},
                "questoes": bench._universos(self.contexto, self.modelo, self.politica, self.esperados),
                "esperados": self.esperados}

    def mocks(self, bundle):
        stack = ExitStack()
        stack.enter_context(patch.object(bench, "carregar", return_value=bundle))
        prever = stack.enter_context(patch("classificacao_precisao.confianca.prever", return_value=.8))
        aplicar = stack.enter_context(patch("classificacao_precisao.confianca.aplicar", return_value=True))
        stack.enter_context(patch("classificacao_precisao.confianca.ajustar", side_effect=AssertionError("Recalibração proibida.")))
        return stack, prever, aplicar

    def test_universos_excluem_os_cem_de_treino_e_ordenam_avaliacao(self):
        qs = bench._universos(self.contexto, self.modelo, self.politica, self.esperados)
        self.assertEqual(len(qs), 559)
        self.assertEqual([q["id"] for q in qs], sorted(self.contexto["protocolo"]["avaliacao_ids"]))
        self.assertFalse({q["id"] for q in qs} & set(self.modelo["treino_ids"]))

    def test_universos_recusam_duplicados_sobreposicao_receita_e_treino_incorreto(self):
        casos = []
        c = deepcopy(self.contexto)
        c["questoes"][-1] = deepcopy(c["questoes"][-2])
        casos.append((c, self.modelo, self.politica, self.esperados))
        m = deepcopy(self.modelo)
        m["treino_ids"][-1] = self.esperados[0]["id"]
        casos.append((self.contexto, m, self.politica, self.esperados))
        p = {**self.politica, "receita": "receita_divergente"}
        casos.append((self.contexto, self.modelo, p, self.esperados))
        e = deepcopy(self.esperados)
        e[-1] = deepcopy(e[-2])
        casos.append((self.contexto, self.modelo, self.politica, e))
        for args in casos:
            with self.subTest(), self.assertRaises(ValueError):
                bench._universos(*args)

    def test_comparacao_examina_campos_aninhados_tipos_e_campos_adicionais(self):
        for alteracao in ("aninhado", "tipo", "adicional"):
            atuais = deepcopy(self.esperados)
            if alteracao == "aninhado":
                atuais[0]["top_candidatos"][0]["score"] += .000000001
            elif alteracao == "tipo":
                atuais[0]["publicaria_politica_candidata"] = 1
            else:
                atuais[0]["campo_adicional"] = "marcador que não deve sair no erro"
            with self.subTest(alteracao=alteracao), self.assertRaises(ValueError) as erro:
                bench.comparar(atuais, self.esperados)
            self.assertNotIn(atuais[0]["id"], str(erro.exception))
            self.assertNotIn("marcador", str(erro.exception))

    def test_comparacao_aceita_ordem_diferente_mas_recusa_repeticao(self):
        resultado = bench.comparar(list(reversed(self.esperados)), self.esperados)
        self.assertEqual(resultado["registros_identicos"], 559)
        repetidas = self.esperados[:-1] + self.esperados[:1]
        with self.assertRaises(ValueError):
            bench.comparar(repetidas, self.esperados)

    def test_medicao_usa_modelo_salvo_e_calibrador_final_sem_treinar(self):
        bundle = self.bundle()
        stack, prever, aplicar = self.mocks(bundle)
        with stack:
            resumo = bench.medir(self.raiz, "tmp/benchmark.json")
        evidencia = json.loads((self.raiz / "tmp/benchmark.json").read_text(encoding="utf-8"))
        self.assertEqual(resumo["registros_identicos"], 559)
        self.assertEqual(len(bundle["motor"].ids), 559)
        self.assertEqual(prever.call_count, 559)
        self.assertEqual(aplicar.call_count, 559)
        self.assertTrue(all(c.args[0] is bundle["calibrador"] for c in prever.call_args_list))
        self.assertTrue(all(c.args[1] is bundle["politica"] for c in aplicar.call_args_list))
        self.assertFalse(evidencia["treino_executado"])
        self.assertFalse(evidencia["recalibracao_executada"])
        self.assertFalse(evidencia["estimativa_linear_50000"]["medida_em_producao"])
        self.assertAlmostEqual(evidencia["estimativa_linear_50000"]["segundos_so_inferencia"],
                               evidencia["tempos_segundos"]["inferencia_559"] / 559 * 50000)
        self.assertNotIn("Conteúdo exclusivamente", json.dumps(evidencia))
        self.assertNotIn(self.esperados[0]["id"], json.dumps(evidencia))

    def test_evidencia_existente_permanece_intacta_sem_carregar(self):
        antes = b'{"preservar":true}\n'
        self.escrever("tmp/benchmark.json", antes)
        with patch.object(bench, "carregar") as carregar, self.assertRaises(ValueError):
            bench.medir(self.raiz, "tmp/benchmark.json")
        carregar.assert_not_called()
        self.assertEqual((self.raiz / "tmp/benchmark.json").read_bytes(), antes)

    def test_predicao_divergente_nao_emite_evidencia(self):
        bundle = self.bundle()
        bundle["esperados"] = deepcopy(self.esperados)
        bundle["esperados"][0]["confianca"] = .9
        stack, _, _ = self.mocks(bundle)
        with stack, self.assertRaises(ValueError):
            bench.medir(self.raiz, "tmp/recusado.json")
        self.assertFalse((self.raiz / "tmp/recusado.json").exists())

    def test_fonte_alterada_durante_inferencia_nao_emite_evidencia(self):
        bundle = self.bundle()
        original = bundle["motor"].predizer
        def adulterar(*args):
            self.escrever("fonte-sintetica.json", {"origem": "alterada"})
            return original(*args)
        bundle["motor"].predizer = adulterar
        stack, _, _ = self.mocks(bundle)
        with stack, self.assertRaises(ValueError):
            bench.medir(self.raiz, "tmp/recusado.json")
        self.assertFalse((self.raiz / "tmp/recusado.json").exists())

    def test_carregar_exige_manifesto_completo_conferido_e_cache_large(self):
        bundle = self.bundle()
        produtos = {"modelo100.json": self.modelo, "politica.json": self.politica,
                    "calibradores.json": {"final80OOF": bundle["calibrador"], "externos": []},
                    "sugestoes_avaliacao.jsonl": bench._jsonl(self.esperados)}
        hashes = {n: self.escrever(f"{bench.ARTEFATOS}/{n}", b) for n, b in produtos.items()}
        manifesto = {"schema": "manifesto_precisao_m8_v1", "entradas_implementacao_sha256": bundle["fontes"],
                     "produtos_sha256": hashes, "llm_na_decisao": False, "encoder_na_decisao": False, "chamadas_api": 0}
        nome = f"{bench.ARTEFATOS}/manifesto.json"
        self.escrever(nome, manifesto)
        self.escrever("scripts/medir_precisao.py", b"# script sintetico\n")
        self.escrever("scripts/verificar_entrega.py", b"# helper sintetico\n")
        contexto = (self.contexto, {}, {}, [], {}, {}, {"dimensoes": 1024}, bundle["fontes"])
        with patch("classificacao_precisao.experimento.carregar_contexto", return_value=contexto) as carregar, \
             patch("classificacao_precisao.motor.Motor", return_value=MotorSintetico()) as motor:
            carregado = bench.carregar(self.raiz)
        carregar.assert_called_once_with(self.raiz, False)
        self.assertEqual(motor.call_args.args[4], {"dimensoes": 1024})
        self.assertEqual(carregado["calibrador"], bundle["calibrador"])
        manifesto["encoder_na_decisao"] = True
        self.escrever(nome, manifesto)
        with patch("classificacao_precisao.experimento.carregar_contexto") as carregar, self.assertRaises(ValueError):
            bench.carregar(self.raiz)
        carregar.assert_not_called()

    def test_assinaturas_e_caminhos_adulterados_sao_recusados(self):
        sha = self.escrever("fonte.json", {})
        bench._conferir_hashes(self.raiz, {"fonte.json": sha})
        for assinaturas in ({}, {"fonte.json": "0" * 64}, {"../fonte.json": sha}, {"fonte.json": "inválido"}):
            with self.subTest(), self.assertRaises(ValueError):
                bench._conferir_hashes(self.raiz, assinaturas)


if __name__ == "__main__":
    unittest.main()
