"""Garantias de origem e isolamento da preparação opcional E5-large."""

import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from classificacao_precisao.preparar_large import (
    CONFIG, _gerar_streaming, _salvar_imutavel, _sha_arquivo, baixar, selecionar_piloto,
)


class PreparacaoLargeTest(unittest.TestCase):
    def test_piloto_independe_da_ordem_e_conteudo_dos_textos(self):
        registros = [{"tipo": tipo, "id": str(i), "texto": "original"}
                     for tipo in ("questao", "tema") for i in range(8)]
        escolhidos = [(r["tipo"], r["id"]) for r in selecionar_piloto(registros)]
        alterados = [dict(r, texto="texto inteiramente distinto") for r in reversed(registros)]
        self.assertEqual(escolhidos, [(r["tipo"], r["id"]) for r in selecionar_piloto(alterados)])
        self.assertEqual(5, sum(tipo == "questao" for tipo, _ in escolhidos))
        self.assertEqual(5, sum(tipo == "tema" for tipo, _ in escolhidos))

    def test_artefato_diferente_nao_pode_ser_substituido(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "vetores.json"
            _salvar_imutavel(p, b"original")
            _salvar_imutavel(p, b"original")
            with self.assertRaises(ValueError):
                _salvar_imutavel(p, b"alterado")
            self.assertEqual(b"original", p.read_bytes())

    def test_hash_streaming_equivale_ao_sha_completo(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "pesos"
            dados = b"\x01\x00\xff" * 800000
            p.write_bytes(dados)
            self.assertEqual(hashlib.sha256(dados).hexdigest(), _sha_arquivo(p))

    def _config(self, raiz, dados, sha=None):
        p = raiz / CONFIG
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps({"origem": "https://huggingface.co/publico/modelo",
                                "revisao": "revisao-fixa", "arquivos": {
                                    "modelo.onnx": {"caminho_remoto": "onnx/modelo.onnx",
                                                    "bytes": len(dados),
                                                    "sha256": sha or hashlib.sha256(dados).hexdigest()}}}), encoding="utf-8")

    def test_download_conferido_antes_de_publicar_arquivo(self):
        with tempfile.TemporaryDirectory() as d:
            raiz = Path(d)
            dados = b"pesos ficticios"
            self._config(raiz, dados)
            with patch("classificacao_precisao.preparar_large.urllib.request.urlopen",
                       return_value=io.BytesIO(dados)) as abrir:
                baixar(raiz)
            self.assertIn("revisao-fixa", abrir.call_args.args[0])
            self.assertEqual(dados, (raiz / ".cache-modelos/e5-large/modelo.onnx").read_bytes())

    def test_download_adulterado_nao_produz_peso_final(self):
        with tempfile.TemporaryDirectory() as d:
            raiz = Path(d)
            self._config(raiz, b"legitimo")
            with patch("classificacao_precisao.preparar_large.urllib.request.urlopen",
                       return_value=io.BytesIO(b"malicioso")):
                with self.assertRaises(ValueError):
                    baixar(raiz)
            self.assertFalse((raiz / ".cache-modelos/e5-large/modelo.onnx").exists())

    def test_peso_existente_adulterado_nao_e_sobrescrito(self):
        with tempfile.TemporaryDirectory() as d:
            raiz = Path(d)
            self._config(raiz, b"legitimo")
            p = raiz / ".cache-modelos/e5-large/modelo.onnx"
            p.parent.mkdir(parents=True)
            p.write_bytes(b"alterado")
            with patch("classificacao_precisao.preparar_large.urllib.request.urlopen") as abrir:
                with self.assertRaises(ValueError):
                    baixar(raiz)
                abrir.assert_not_called()
            self.assertEqual(b"alterado", p.read_bytes())

    def test_retomada_nao_reexecuta_encoder_e_rejeita_vetor_adulterado(self):
        registro = {"tipo": "questao", "id": "q1", "papel": "query", "texto": "texto",
                    "texto_sha256": hashlib.sha256(b"query: texto").hexdigest()}
        config = {"preparacao": {"dimensoes": 1024, "max_tokens": 512,
                                  "janela_tokens": 480, "sobreposicao_tokens": 32,
                                  "batch_size": 1, "threads": 2, "casas_decimais": 8},
                  "sessao_onnx": {"enable_cpu_mem_arena": False, "enable_mem_pattern": False}}
        tokenizer = SimpleNamespace(no_truncation=lambda: None, no_padding=lambda: None,
                                    token_to_id=lambda _: 0,
                                    encode=lambda *a, **kw: SimpleNamespace(ids=[1, 2, 3], overflowing=[]))
        sessao = SimpleNamespace(get_providers=lambda: ["CPUExecutionProvider"])
        ort = SimpleNamespace(__version__="teste", SessionOptions=SimpleNamespace,
                              ExecutionMode=SimpleNamespace(ORT_SEQUENTIAL=0),
                              InferenceSession=lambda *a, **kw: sessao)
        deps = (SimpleNamespace(__version__="teste"), ort,
                SimpleNamespace(__version__="teste", Tokenizer=SimpleNamespace(from_file=lambda _: tokenizer)))
        modulo = "classificacao_experimentos.preparacao_embeddings"
        with tempfile.TemporaryDirectory() as d, \
                patch(modulo + "._dependencias", return_value=deps), \
                patch(modulo + "._janelas_texto", return_value=(["texto"], 1)), \
                patch(modulo + "._inferir_lote", return_value=[[1.0] + [0.0] * 1023]) as inferir:
            pasta = Path(d) / "checkpoint"
            original, _, reusos = _gerar_streaming([registro], config, Path(d), pasta, {}, lambda *_: None)
            retomado, _, reusos2 = _gerar_streaming([registro], config, Path(d), pasta, {}, lambda *_: None)
            self.assertEqual(original, retomado)
            self.assertEqual((0, 1), (reusos, reusos2))
            self.assertEqual(1, inferir.call_count)
            with self.assertRaises(ValueError):
                _gerar_streaming([registro], config, Path(d), pasta, {"fonte": "alterada"}, lambda *_: None)
            arquivo = next(p for p in pasta.glob("*.json") if p.name != "indice.json")
            arquivo.write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                _gerar_streaming([registro], config, Path(d), pasta, {}, lambda *_: None)


if __name__ == "__main__":
    unittest.main()
