"""Reserva sintética: congelamento obrigatório e extensão sem recodificar o M3."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from classificacao_decisao import cache as m4
from classificacao_experimentos.contexto import assinar
from classificacao_experimentos.entradas import construir_registros
from classificacao_experimentos.motor import predizer, treinar
from classificacao_experimentos.preparar import FONTES_PREPARACAO
from classificacao_local.classificador import CONFIG_PADRAO
from classificacao_topicos.pipeline import _json, _sha


RAIZ = Path(__file__).resolve().parents[1]


def cache_sintetico(registros):
    cache = {"schema": "embeddings_e5_v1", "dimensoes": 2, "questoes": {}, "temas": {}}
    for r in registros:
        campo = "questoes" if r["tipo"] == "questao" else "temas"
        cache[campo][r["id"]] = {
            "texto_sha256": r["texto_sha256"], "vetor": [0.6, 0.8],
            "tokens": 7, "janelas": 1,
        }
    return cache


def escrever(raiz, nome, valor):
    caminho = raiz / nome
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(valor if isinstance(valor, bytes) else _json(valor))


def fixture(raiz):
    questoes = [
        {"id": i, "enunciado": texto, "comando": "Escolha uma cor.",
         "alternativas": {"a": "Azul", "b": "Amarelo"}}
        for i, texto in (
            ("D1", "Flores do jardim."), ("R1", "Pigmentos reservados."),
            ("E1", "Tinta na parede."),
        )
    ]
    temas = [
        {"tema_id": "raiz", "parent_id": "", "nivel": "0", "status": "active",
         "titulo": "Catálogo", "caminho": "Catálogo", "descricao": ""},
        {"tema_id": "T1", "parent_id": "raiz", "nivel": "1", "status": "active",
         "titulo": "Cores", "caminho": "Catálogo > Cores", "descricao": "Pigmentos."},
    ]
    protocolo = {"desenvolvimento_ids": ["D1"], "reserva_ids": ["R1"],
                 "avaliacao_ids": ["E1"]}
    registros = construir_registros(questoes, temas, {"D1", "E1"})
    contexto = {
        "questoes": questoes,
        "taxonomia": {"registros": temas, "por_id": {t["tema_id"]: t for t in temas}},
        "registros": registros, "protocolo": protocolo,
    }
    for nome in set(FONTES_PREPARACAO) | m4.FONTES_OBRIGATORIAS | {
        "classificacao_decisao/cache.py", "classificacao_decisao/__init__.py",
        "config/modulo4/experimento.json",
    }:
        escrever(raiz, nome, {})
    config = {
        "modelo": "sintetico", "preparacao": {"dimensoes": 2},
        "dependencias_preparacao": {"numpy": "sintetico"}, "arquivos": {},
    }
    escrever(raiz, "config/modulo3/embeddings.json", config)
    escrever(raiz, "artefatos/melhorias-v1/protocolo.json", protocolo)
    escrever(raiz, "artefatos/lexical-v1/protocolo.json", protocolo)
    anterior = cache_sintetico(registros)
    escrever(raiz, "artefatos/embeddings-e5-v1/vetores.json", anterior)
    escrever(raiz, "artefatos/embeddings-e5-v1/manifesto.json", {
        "configuracao": config,
        "fontes_preparacao_sha256": assinar(raiz, FONTES_PREPARACAO),
        "produtos_sha256": {"vetores.json": _sha(_json(anterior))},
    })
    escrever(raiz, "artefatos/melhorias-v1/manifesto.json", {
        "entradas_e_implementacao_sha256": {}, "produtos_sha256": {},
    })
    nomes = sorted(m4.FONTES_OBRIGATORIAS | {
        "classificacao_decisao/cache.py", "classificacao_decisao/__init__.py",
        "config/modulo4/experimento.json",
    })
    freeze = {
        "schema": "congelamento_m4_v1", "classificador_congelado": True,
        "calibrador_congelado": True, "politica_congelada": True,
        **protocolo, "fontes_sha256": assinar(raiz, nomes),
    }
    caminho = raiz / "artefatos/calibracao-v1/congelamento.json"
    escrever(raiz, caminho, freeze)
    return contexto, freeze, caminho, _sha(_json(freeze)), anterior


class TestCacheM4(unittest.TestCase):
    def setUp(self):
        self.pasta_tmp = RAIZ / "tmp"
        self.pasta_tmp.mkdir(exist_ok=True)
        self.temporaria = tempfile.TemporaryDirectory(prefix="teste-cache-m4-", dir=self.pasta_tmp)
        self.raiz = Path(self.temporaria.name).resolve()
        self.contexto, self.freeze, self.caminho, self.sha, self.anterior = fixture(self.raiz)
        self.saida = self.raiz / "artefatos/embeddings-completos-v1"

    def tearDown(self):
        if not self.raiz.is_relative_to(self.pasta_tmp.resolve()):
            raise AssertionError("Limpeza fora da pasta temporária permitida.")
        self.temporaria.cleanup()

    def atualizar_freeze(self):
        escrever(self.raiz, self.caminho, self.freeze)
        self.sha = _sha(_json(self.freeze))

    def preparar(self, encoder=None):
        if encoder is None:
            encoder = lambda registros, *args, **kwargs: (
                cache_sintetico(registros), {"registros_total": len(registros)},
            )
        with (
            patch.object(m4, "carregar_contexto", return_value=deepcopy(self.contexto)),
            patch.object(m4, "_conferir_pesos_e_dependencias",
                         return_value=(self.raiz / "pesos", {"numpy": "sintetico"})),
            patch("classificacao_experimentos.preparacao_embeddings.gerar_cache",
                  side_effect=encoder) as gerar,
        ):
            resultado = m4.preparar_reserva(self.raiz, self.saida, self.caminho, self.sha)
        return resultado, gerar

    def carregar(self):
        with patch.object(m4, "carregar_contexto", return_value=deepcopy(self.contexto)):
            return m4.carregar_cache_completo(self.raiz, self.saida, self.caminho, self.sha)

    def test_freeze_sha_invalido_bloqueia_antes_de_ler_textos(self):
        with patch.object(m4, "carregar_contexto") as contexto:
            for sha in ("", "x" * 64, "a" * 64, True):
                with self.subTest(sha=sha), self.assertRaises(ValueError):
                    m4.preparar_reserva(self.raiz, self.saida, self.caminho, sha)
            contexto.assert_not_called()
        self.assertFalse(self.saida.exists())

    def test_freeze_exige_tres_flags_e_grupos_disjuntos(self):
        original = deepcopy(self.freeze)
        variacoes = []
        for campo in ("classificador_congelado", "calibrador_congelado", "politica_congelada"):
            for valor in (False, 1):
                doc = deepcopy(original)
                doc[campo] = valor
                variacoes.append(doc)
        for campo, valor in (
            ("reserva_ids", ["D1"]), ("reserva_ids", ["R1", "R1"]),
            ("reserva_ids", []), ("reserva_ids", ["R2"]), ("schema", "outro"),
        ):
            doc = deepcopy(original)
            doc[campo] = valor
            variacoes.append(doc)
        for doc in variacoes:
            self.freeze = doc
            self.atualizar_freeze()
            with self.subTest(doc=doc), self.assertRaises(ValueError):
                m4.validar_congelamento(self.raiz, self.caminho, self.sha)

    def test_freeze_exige_fontes_codigo_e_configs_completos(self):
        original = deepcopy(self.freeze)
        for omitido in (
            "artefatos/calibracao-v1/politica.json",
            "artefatos/embeddings-e5-v1/vetores.json",
            "classificacao_decisao/cache.py", "config/modulo4/experimento.json",
        ):
            self.freeze = deepcopy(original)
            del self.freeze["fontes_sha256"][omitido]
            self.atualizar_freeze()
            with self.subTest(omitido=omitido), self.assertRaisesRegex(ValueError, "omite"):
                m4.validar_congelamento(self.raiz, self.caminho, self.sha)
        self.freeze = original
        self.atualizar_freeze()
        escrever(self.raiz, "classificacao_decisao/novo.py", {})
        with self.assertRaisesRegex(ValueError, "omite"):
            m4.validar_congelamento(self.raiz, self.caminho, self.sha)

    def test_fonte_mudada_bloqueia_antes_do_contexto(self):
        escrever(self.raiz, "artefatos/calibracao-v1/politica.json", {"alteracao": True})
        with patch.object(m4, "carregar_contexto") as contexto, self.assertRaises(ValueError):
            m4.preparar_reserva(self.raiz, self.saida, self.caminho, self.sha)
        contexto.assert_not_called()

    def test_extensao_codifica_so_reserva_e_preserva_cache_m3(self):
        antes = (self.raiz / "artefatos/embeddings-e5-v1/vetores.json").read_bytes()
        resultado, gerar = self.preparar()
        self.assertEqual(resultado["questoes_codificadas"], 1)
        registros, config, modelo, tokenizer = gerar.call_args.args
        self.assertEqual([(r["tipo"], r["id"]) for r in registros], [("questao", "R1")])
        self.assertEqual(config, {"dimensoes": 2})
        self.assertEqual(modelo.name, "modelo.onnx")
        self.assertEqual(tokenizer.name, "tokenizer.json")
        for r in registros:
            self.assertEqual(set(r), {"tipo", "id", "papel", "texto", "texto_sha256"})
        cache, manifesto = self.carregar()
        self.assertEqual(set(cache["questoes"]), {"D1", "R1", "E1"})
        self.assertEqual(_json(cache["temas"]), _json(self.anterior["temas"]))
        for i, item in self.anterior["questoes"].items():
            self.assertEqual(_json(cache["questoes"][i]), _json(item))
        self.assertEqual(manifesto["congelamento_sha256"], self.sha)
        self.assertEqual(manifesto["questoes_reutilizadas"], 2)
        self.assertEqual(manifesto["temas_reutilizados"], 1)
        self.assertFalse(manifesto["rotulos_fornecidos_ao_codificador"])
        self.assertEqual(antes, (self.raiz / "artefatos/embeddings-e5-v1/vetores.json").read_bytes())

    def test_reuso_e_leitura_nao_carregam_encoder_nem_pesos(self):
        self.preparar()
        with (
            patch.object(m4, "carregar_contexto", return_value=self.contexto),
            patch.object(m4, "_conferir_pesos_e_dependencias",
                         side_effect=AssertionError("Não ler pesos.")),
            patch("classificacao_experimentos.preparacao_embeddings.gerar_cache",
                  side_effect=AssertionError("Não codificar.")),
        ):
            resultado = m4.preparar_reserva(self.raiz, self.saida, self.caminho, self.sha)
            cache, _ = m4.carregar_cache_completo(
                self.raiz, self.saida, self.caminho, self.sha,
            )
        self.assertTrue(resultado["reutilizado"])
        self.assertEqual(len(cache["questoes"]), 3)

    def test_cache_parcial_ou_adulterado_recusado(self):
        self.preparar()
        vetor_path = self.saida / "vetores.json"
        vetor_path.write_bytes(vetor_path.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "adulterado"):
            self.carregar()
        vetor_path.unlink()
        with self.assertRaisesRegex(ValueError, "parcial"):
            self.carregar()

    def test_extensao_nao_pode_mudar_vetor_antigo_nem_mesmo_com_novo_hash(self):
        self.preparar()
        cache = json.loads((self.saida / "vetores.json").read_bytes())
        cache["questoes"]["D1"]["vetor"] = [1.0, 0.0]
        manifesto = json.loads((self.saida / "manifesto.json").read_bytes())
        manifesto["produtos_sha256"]["vetores.json"] = _sha(_json(cache))
        escrever(self.raiz, self.saida / "vetores.json", cache)
        escrever(self.raiz, self.saida / "manifesto.json", manifesto)
        with self.assertRaisesRegex(ValueError, "alterou"):
            self.carregar()

    def test_encoder_com_item_extra_ou_vetor_invalido_nao_publica(self):
        for erro in ("extra", "invalido"):
            def encoder(registros, *args, **kwargs):
                parcial = cache_sintetico(registros)
                if erro == "extra":
                    parcial["questoes"]["D1"] = deepcopy(parcial["questoes"]["R1"])
                else:
                    parcial["questoes"]["R1"]["vetor"] = [0.0, 0.0]
                return parcial, {}
            with self.subTest(erro=erro), self.assertRaises(ValueError):
                self.preparar(encoder)
            self.assertFalse(self.saida.exists())

    def test_mudanca_durante_encoder_impede_publicacao(self):
        def encoder(registros, *args, **kwargs):
            escrever(self.raiz, "artefatos/calibracao-v1/politica.json", {"mudou": True})
            return cache_sintetico(registros), {}
        with self.assertRaises(ValueError):
            self.preparar(encoder)
        self.assertFalse(self.saida.exists())

    def test_saida_nao_pode_sobrepor_fontes(self):
        for nome in (
            "artefatos/embeddings-e5-v1",
            "artefatos/melhorias-v1/filho",
            "artefatos/calibracao-v1",
        ):
            with self.subTest(nome=nome), self.assertRaisesRegex(ValueError, "separado"):
                m4.preparar_reserva(self.raiz, Path(nome), self.caminho, self.sha)

    def test_vinculo_muda_apenas_sha_e_preserva_predicao_anterior(self):
        self.preparar()
        completo, _ = self.carregar()
        anterior = deepcopy(self.anterior)
        anterior["sha256"] = _sha(_json(self.anterior))
        taxonomia = self.contexto["taxonomia"]
        treino = [q for q in self.contexto["questoes"] if q["id"] == "D1"]
        rotulos = [{"id": "D1", "tema_central_id": "T1", "extras_ids": [],
                    "fora_da_taxonomia": False}]
        config = {
            "modo": "hibrido", "peso_exemplos": 0.0, "vizinhos": "lexicais",
            "lexical": CONFIG_PADRAO.copy(),
        }
        modelo = treinar(treino, rotulos, taxonomia, config, anterior)
        antes = deepcopy(modelo)
        vinculado = m4.vincular_modelo_estendido(modelo, anterior, completo)
        esperado = deepcopy(modelo)
        esperado["cache_sha256"] = completo["sha256"]
        self.assertEqual(vinculado, esperado)
        self.assertEqual(modelo, antes)
        consulta = next(q for q in self.contexto["questoes"] if q["id"] == "E1")
        self.assertEqual(predizer(modelo, consulta, anterior), predizer(vinculado, consulta, completo))
        reserva = next(q for q in self.contexto["questoes"] if q["id"] == "R1")
        self.assertEqual(predizer(vinculado, reserva, completo)["id"], "R1")
        completo["sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "SHA"):
            m4.vincular_modelo_estendido(modelo, anterior, completo)

    def test_importacao_nao_carrega_dependencias_nem_rede(self):
        codigo = """
import sys
proibidos = {'numpy', 'onnxruntime', 'tokenizers', 'torch', 'transformers',
             'sentence_transformers', 'huggingface_hub'}
def guard(event, args):
    if event == 'socket.connect':
        raise AssertionError('Rede proibida.')
    if event == 'import' and args and args[0].split('.')[0] in proibidos:
        raise AssertionError('Encoder proibido.')
sys.addaudithook(guard)
from classificacao_decisao.cache import carregar_cache_completo, vincular_modelo_estendido
assert not (proibidos & set(sys.modules))
"""
        resultado = subprocess.run(
            [sys.executable, "-B", "-c", codigo], cwd=RAIZ,
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(resultado.returncode, 0, resultado.stderr)


if __name__ == "__main__":
    unittest.main()
