"""Exercita a preparação com textos sintéticos e sem bibliotecas de inferência."""

import hashlib
import math
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from classificacao_experimentos import preparacao_embeddings as preparacao


class TokenizerFalso:
    def __init__(self):
        self.codificados = []
        self.truncamento_desativado = False
        self.padding_desativado = False

    def no_truncation(self):
        self.truncamento_desativado = True

    def no_padding(self):
        self.padding_desativado = True

    def token_to_id(self, token):
        return 0 if token == "<pad>" else None

    def encode(self, texto, add_special_tokens=True):
        self.codificados.append((texto, add_special_tokens))
        partes = list(re.finditer(r"\S+", texto))
        ids = list(range(10, len(partes) + 10))
        offsets = [parte.span() for parte in partes]
        if add_special_tokens:
            ids = [1] + ids + [2]
            offsets = [(0, 0)] + offsets + [(0, 0)]
        return SimpleNamespace(
            ids=ids, offsets=offsets, type_ids=[0] * len(ids), overflowing=[],
        )


def registro(texto, identificador="q1", tipo="questao", papel="query"):
    return {
        "tipo": tipo, "id": identificador, "texto": texto, "papel": papel,
        "texto_sha256": hashlib.sha256(f"{papel}: {texto}".encode()).hexdigest(),
    }


def config():
    return {
        "dimensoes": 2, "max_tokens": 10, "janela_tokens": 4,
        "sobreposicao_tokens": 1, "batch_size": 2, "threads": 4,
        "casas_decimais": 8,
    }


class PreparacaoEmbeddingsTests(unittest.TestCase):
    def test_janelas_cobrem_corpo_com_sobreposicao_sem_cauda_redundante(self):
        tokenizer = TokenizerFalso()
        texto = "  um dois três quatro cinco seis sete oito nove dez  "
        janelas, total = preparacao._janelas_texto(texto, tokenizer, 4, 1)
        self.assertEqual(total, 10)
        self.assertEqual(janelas, [
            "  um dois três quatro", "quatro cinco seis sete",
            "sete oito nove dez  ",
        ])

    def test_texto_menor_e_texto_vazio_sao_preservados(self):
        for texto, quantidade in ((" ação lícita  ", 2), ("", 0)):
            with self.subTest(texto=texto):
                self.assertEqual(
                    preparacao._janelas_texto(texto, TokenizerFalso(), 4, 1),
                    ([texto], quantidade),
                )

    def test_recusa_tokenizacao_previamente_truncada(self):
        tokenizer = SimpleNamespace(encode=lambda *a, **k: SimpleNamespace(
            ids=[1], offsets=[(0, 1)], overflowing=[object()],
        ))
        with self.assertRaisesRegex(ValueError, "truncou"):
            preparacao._janelas_texto("abc", tokenizer, 4, 1)

    def test_recusa_offsets_incompativeis_ou_fora_do_texto(self):
        for offsets in ([], [(0, 99)], [(2, 1)], [(-1, 1)]):
            tokenizer = SimpleNamespace(encode=lambda *a, **k: SimpleNamespace(
                ids=[1], offsets=offsets, overflowing=[],
            ))
            with self.subTest(offsets=offsets), self.assertRaises(ValueError):
                preparacao._janelas_texto("abc", tokenizer, 4, 1)

    def test_hash_assina_prefixo_e_corpo_sem_transformacao(self):
        entrada = registro("AÇÃO\nválida")
        self.assertEqual(preparacao._validar_registros([entrada]), [entrada])
        for mudanca in ({"papel": "passage"}, {"texto": "ACAO\nvalida"}):
            with self.subTest(mudanca=mudanca), self.assertRaisesRegex(ValueError, "Hash"):
                preparacao._validar_registros([{**entrada, **mudanca}])

    def test_duplicado_e_rejeitado_mas_id_pode_existir_nos_dois_tipos(self):
        entrada = registro("um")
        with self.assertRaisesRegex(ValueError, "duplicado"):
            preparacao._validar_registros([entrada, entrada])
        self.assertEqual(len(preparacao._validar_registros([
            entrada, registro("dois", tipo="tema", papel="passage"),
        ])), 2)

    def test_agregacao_normaliza_media_e_recusa_vetor_invalido(self):
        vetor = preparacao._agregar_vetores([[1.0, 0.0], [0.0, 1.0]], 2, 8)
        self.assertEqual(vetor, [0.70710678, 0.70710678])
        self.assertAlmostEqual(math.hypot(*vetor), 1, places=7)
        for vetores in ([], [[0, 0]], [[1]], [[math.nan, 1]], [[1, 0], [-1, 0]]):
            with self.subTest(vetores=vetores), self.assertRaises(ValueError):
                preparacao._agregar_vetores(vetores, 2, 8)

    def test_parametros_nao_aceitam_booleanos_e_sobreposicao_infinita(self):
        for mudanca in (
            {"threads": True}, {"sobreposicao_tokens": 4}, {"batch_size": 0},
            {"max_tokens": 513}, {"janela_tokens": 10},
        ):
            with self.subTest(mudanca=mudanca), self.assertRaises(ValueError):
                preparacao._validar_config({**config(), **mudanca})

    def _executar_fake(self, registros, parametros=None, tokenizer=None):
        tokenizer = tokenizer or TokenizerFalso()
        chamadas_sessao = []
        lotes = []
        progressos = []

        def criar_sessao(caminho, **kwargs):
            chamadas_sessao.append(kwargs)
            return SimpleNamespace(get_providers=lambda: ["CPUExecutionProvider"])

        ort = SimpleNamespace(
            __version__="fake-ort", SessionOptions=SimpleNamespace,
            ExecutionMode=SimpleNamespace(ORT_SEQUENTIAL="sequencial"),
            InferenceSession=criar_sessao,
        )
        dependencias = (
            SimpleNamespace(__version__="fake-numpy"), ort,
            SimpleNamespace(__version__="fake-tokenizers",
                            Tokenizer=SimpleNamespace(from_file=lambda p: tokenizer)),
        )

        def inferir(np, sessao, codificacoes, padding_id, dimensoes):
            lotes.append(len(codificacoes))
            return [[1.0, 0.0] for _ in codificacoes]

        with tempfile.TemporaryDirectory() as pasta:
            modelo = Path(pasta) / "modelo.onnx"
            tokenizer_path = Path(pasta) / "tokenizer.json"
            modelo.write_bytes(b"fake")
            tokenizer_path.write_bytes(b"fake")
            with patch.object(preparacao, "_dependencias", return_value=dependencias):
                with patch.object(preparacao, "_inferir_lote", side_effect=inferir):
                    resultado = preparacao.gerar_cache(
                        registros, parametros or config(), modelo, tokenizer_path,
                        lambda feitos, total: progressos.append((feitos, total)),
                    )
        return resultado, tokenizer, chamadas_sessao, lotes, progressos

    def test_fluxo_cache_batcheado_prefixa_todas_janelas_e_isola_metadados(self):
        entradas = [
            registro("um dois três quatro cinco seis sete oito nove dez"),
            registro("tema exemplo", "t1", "tema", "passage"),
        ]
        (cache, diagnostico), tokenizer, sessoes, lotes, progressos = self._executar_fake(entradas)
        self.assertTrue(tokenizer.truncamento_desativado)
        self.assertTrue(tokenizer.padding_desativado)
        codificados = [texto for texto, especiais in tokenizer.codificados if especiais]
        self.assertEqual(sum(texto.startswith("query: ") for texto in codificados), 3)
        self.assertEqual(sum(texto.startswith("passage: ") for texto in codificados), 1)
        self.assertEqual(lotes, [2, 2])
        self.assertEqual(progressos, [(2, 4), (4, 4)])
        self.assertEqual(sessoes[0]["providers"], ["CPUExecutionProvider"])
        self.assertEqual(sessoes[0]["sess_options"].inter_op_num_threads, 1)
        self.assertEqual(sessoes[0]["sess_options"].intra_op_num_threads, 4)
        self.assertEqual(cache["questoes"]["q1"], {
            "texto_sha256": entradas[0]["texto_sha256"],
            "vetor": [1.0, 0.0], "tokens": 10, "janelas": 3,
        })
        self.assertEqual(diagnostico["truncados"], 0)
        self.assertEqual(diagnostico["janelas_total"], 4)
        self.assertEqual(diagnostico["max_tokens_janela"], 7)
        self.assertNotIn("q1", str(diagnostico))
        self.assertNotIn("um dois", str(diagnostico))
        self.assertNotIn("texto", cache["questoes"]["q1"])

    def test_cache_independe_da_ordem_das_entradas(self):
        entradas = [registro("um", "q2"), registro("dois", "q1")]
        resultado1, *_ = self._executar_fake(entradas)
        resultado2, *_ = self._executar_fake(list(reversed(entradas)))
        self.assertEqual(resultado1, resultado2)

    def test_janela_estourada_e_recusada_antes_da_inferencia(self):
        with self.assertRaisesRegex(ValueError, "truncamento recusado"):
            self._executar_fake([registro("um dois três quatro")],
                                {**config(), "max_tokens": 5})

    def test_inferencia_envia_somente_entradas_declaradas_e_mascara_padding(self):
        chamadas = []
        sessao = SimpleNamespace(
            get_inputs=lambda: [
                SimpleNamespace(name="input_ids"), SimpleNamespace(name="attention_mask"),
            ],
            run=lambda saidas, entradas: chamadas.append(entradas) or ["estados"],
        )
        np = SimpleNamespace(int64="int64", asarray=lambda dados, dtype: dados)
        tokenizer = TokenizerFalso()
        codificacoes = [tokenizer.encode("um dois"), tokenizer.encode("três")]
        with patch.object(preparacao, "_pooling_normalizado",
                          return_value=[[1, 0], [0, 1]]) as pooling:
            self.assertEqual(
                preparacao._inferir_lote(np, sessao, codificacoes, 0, 2),
                [[1, 0], [0, 1]],
            )
        self.assertEqual(chamadas[0]["attention_mask"], [[1, 1, 1, 1], [1, 1, 1, 0]])
        self.assertEqual(chamadas[0]["input_ids"][1][-1], 0)
        self.assertNotIn("token_type_ids", chamadas[0])
        self.assertEqual(pooling.call_args.args[2], chamadas[0]["attention_mask"])

    def test_entrada_onnx_desconhecida_impede_execucao(self):
        sessao = SimpleNamespace(get_inputs=lambda: [SimpleNamespace(name="outro")])
        with self.assertRaisesRegex(ValueError, "Entradas ONNX"):
            preparacao._inferir_lote(
                object(), sessao, [TokenizerFalso().encode("um")], 0, 2,
            )


if __name__ == "__main__":
    unittest.main()
