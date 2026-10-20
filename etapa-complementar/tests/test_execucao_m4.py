"""Fluxo M4 em repositório temporário, com casos inteiramente fictícios."""

from contextlib import ExitStack
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from classificacao_decisao import cache as c
from classificacao_decisao import desenvolvimento as d
from classificacao_decisao import execucao as e
from classificacao_experimentos.contexto import assinar
from classificacao_topicos.pipeline import _json, _jsonl
from tests.test_desenvolvimento_m4 import decodificar_jsonl, fixture


RAIZ = Path(__file__).resolve().parents[1]


def escrever(raiz, nome, valor):
    caminho = raiz / nome
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(valor if isinstance(valor, bytes) else _json(valor))


class TestExecucaoM4(unittest.TestCase):
    def setUp(self):
        self.pasta_tmp = RAIZ / "tmp"
        self.pasta_tmp.mkdir(exist_ok=True)
        self.temporaria = tempfile.TemporaryDirectory(prefix="teste-execucao-m4-", dir=self.pasta_tmp)
        self.raiz = Path(self.temporaria.name).resolve()
        self.patches = ExitStack()
        self.eventos = []
        self.ajustes = []
        predicoes, protocolo, temas, config = fixture()
        mapa = {f"D{i}": f"Q{i + 1:04d}" for i in range(6)}
        mapa.update({"R1": "Q0007", "R2": "Q0008", "E1": "Q0009", "E2": "Q0360"})
        for campo in ("desenvolvimento_ids", "reserva_ids", "avaliacao_ids"):
            protocolo[campo] = [mapa[i] for i in protocolo[campo]]
        for fold in protocolo["particoes_internas"]:
            for campo in ("treino_ids", "validacao_ids"):
                fold[campo] = [mapa[i] for i in fold[campo]]
        for p in predicoes:
            p["id"] = mapa[p["id"]]
        self.protocolo, self.taxonomia = protocolo, temas
        ids = sum((protocolo[campo] for campo in
                   ("desenvolvimento_ids", "reserva_ids", "avaliacao_ids")), [])
        questoes = [{"id": i, "enunciado": f"Cor fictícia {i}.",
                     "comando": "Escolha uma cor.", "alternativas": {"a": "Azul"}}
                    for i in ids]
        self.contexto = {
            "questoes": questoes, "taxonomia": temas, "protocolo": protocolo,
            "registros": [{"id": i} for i in protocolo["desenvolvimento_ids"] + protocolo["avaliacao_ids"]],
        }
        rotulos = [{
            "id": i, "tema_central_id": "FLOR", "extras_ids": [],
            "fora_da_taxonomia": i == "Q0008", "disciplina": "Ciências fictícias",
        } for i in protocolo["desenvolvimento_ids"] + protocolo["reserva_ids"]]
        nomes = sorted(n for n in c.FONTES_OBRIGATORIAS if not n.startswith(d.CALIBRACAO + "/"))
        for nome in nomes:
            escrever(self.raiz, nome, {})
        escrever(self.raiz, "classificacao_decisao/execucao.py", b"# Implementacao ficticia assinada.\n")
        escrever(self.raiz, "config/modulo4/protocolo.json", config)
        escrever(self.raiz, "config/modulo3/embeddings.json", {"dimensoes": 2})
        escrever(self.raiz, "artefatos/melhorias-v1/protocolo.json", protocolo)
        escrever(self.raiz, "artefatos/melhorias-v1/modelo_selecionado.json", {"marcador": "80"})
        escrever(self.raiz, "artefatos/melhorias-v1/receita_congelada.json",
                 {"parametros": {"receita": "ficticia_fixa"}})
        escrever(self.raiz, "artefatos/melhorias-v1/predicoes_desenvolvimento.jsonl", _jsonl(predicoes))
        escrever(self.raiz, "artefatos/preparacao/rotulos_referencia.jsonl", _jsonl(rotulos))
        nomes += ["artefatos/melhorias-v1/predicoes_desenvolvimento.jsonl",
                  "artefatos/preparacao/rotulos_referencia.jsonl"]
        self.fixadas = {"sha256": assinar(self.raiz, nomes)}
        escrever(self.raiz, "config/modulo4/fontes.json", self.fixadas)
        escrever(self.raiz, f"{d.CACHE}/vetores.json", {"cache": "ficticio"})
        escrever(self.raiz, f"{d.CACHE}/manifesto.json", {"cache": "ficticio"})
        for modulo in (d, e):
            self.patches.enter_context(patch.object(
                modulo, "carregar_fontes", side_effect=lambda raiz: (
                    deepcopy(self.contexto), deepcopy(self.fixadas))))
        self.patches.enter_context(patch.object(
            e, "carregar_cache_completo", side_effect=self.carregar_cache_completo))
        self.patches.enter_context(patch.object(
            e, "carregar_cache", return_value=({"cache": "m3_ficticio"}, {})))
        self.patches.enter_context(patch.object(
            e, "vincular_modelo_estendido", side_effect=lambda modelo, *args: modelo))
        self.patches.enter_context(patch.object(e, "predizer", side_effect=self.predizer))
        self.patches.enter_context(patch.object(e, "treinar", side_effect=self.treinar))
        ler_jsonl_original = e.ler_jsonl

        def ler_jsonl(raiz, nome):
            if nome == "artefatos/preparacao/rotulos_referencia.jsonl":
                self.eventos.append(("ler_rotulos_avaliacao",))
            return ler_jsonl_original(raiz, nome)

        self.patches.enter_context(patch.object(e, "ler_jsonl", side_effect=ler_jsonl))
        # Ajuste, seleção, hashes, congelamento, avaliação e publicação são reais.
        # Apenas o motor de tópicos, cache e fonte do contexto são substituídos.
        d.executar_calibracao(self.raiz)

    def tearDown(self):
        self.patches.close()
        if not self.raiz.is_relative_to(self.pasta_tmp.resolve()):
            raise AssertionError("Limpeza fora do diretório temporário permitido.")
        self.temporaria.cleanup()

    def carregar_cache_completo(self, raiz, diretorio, congelamento, sha):
        c.validar_congelamento(raiz, congelamento, sha)
        self.eventos.append(("congelamento_validado",))
        return {"cache": "completo_ficticio"}, {}

    def predizer(self, modelo, questao, cache, top_k):
        self.assertIn(("congelamento_validado",), self.eventos)
        self.assertEqual(top_k, 5)
        self.assertNotIn("tema_central_id", questao)
        self.assertNotIn("fora_da_taxonomia", questao)
        self.eventos.append(("predizer", modelo["marcador"], questao["id"]))
        return {
            "id": questao["id"], "tema_sugerido_id": "FLOR",
            "score": 0.55, "margem": 0.055, "sem_evidencia": False,
            "top_candidatos": [{"tema_id": "FLOR", "score": 0.55}],
        }

    def treinar(self, questoes, rotulos, taxonomia, receita, cache):
        self.ajustes.append({
            "questoes": [q["id"] for q in questoes], "rotulos": [r["id"] for r in rotulos],
            "receita": deepcopy(receita),
        })
        self.eventos.append(("treinar_final",))
        return {"marcador": "100", "ids": [q["id"] for q in questoes]}

    def gerar_tudo(self):
        e.executar_reserva(self.raiz)
        return e.executar_entrega(self.raiz)

    def test_reserva_prediz_somente_ids_reservados_antes_de_ler_rotulos(self):
        produtos, resumo = e.construir_reserva(self.raiz)
        consultas = [v for v in self.eventos if v[0] == "predizer"]
        self.assertEqual(consultas, [("predizer", "80", i)
                                    for i in sorted(self.protocolo["reserva_ids"])])
        posicao_rotulos = self.eventos.index(("ler_rotulos_avaliacao",))
        self.assertTrue(all(self.eventos.index(v) < posicao_rotulos for v in consultas))
        self.assertLess(self.eventos.index(("congelamento_validado",)),
                        self.eventos.index(consultas[0]))
        self.assertEqual(resumo["reserva"], 2)
        self.assertEqual(set(produtos), {"predicoes_reserva.jsonl", "metricas_reserva.json", "manifesto.json"})
        resultados = decodificar_jsonl(produtos["predicoes_reserva.jsonl"])
        self.assertEqual(sum(r["acerto"] for r in resultados), 1)
        self.assertTrue(all(r["procedencia"] == "reserva20_modelo80_calibrador80" for r in resultados))
        self.assertEqual(self.ajustes, [])

    def test_congelamento_divergente_bloqueia_antes_de_inferencia(self):
        caminho = self.raiz / d.CALIBRACAO / "politica.json"
        caminho.write_bytes(caminho.read_bytes() + b"\n")
        with self.assertRaises(ValueError):
            e.construir_reserva(self.raiz)
        self.assertEqual(self.eventos, [])
        self.assertFalse((self.raiz / d.RESERVA).exists())

    def test_reserva_existente_e_reutilizada_sem_nova_inferencia(self):
        e.executar_reserva(self.raiz)
        self.eventos.clear()
        resumo = e.executar_reserva(self.raiz)
        self.assertTrue(resumo["reutilizado"])
        self.assertEqual(resumo["reserva"], 2)
        self.assertEqual(self.eventos, [])

    def test_ajuste_final_usa_todas_referencias_e_consulta_so_avaliacao(self):
        e.executar_reserva(self.raiz)
        self.eventos.clear()
        produtos, resumo = e.construir_entrega(self.raiz)
        referencias = set(self.protocolo["desenvolvimento_ids"] + self.protocolo["reserva_ids"])
        self.assertEqual(len(self.ajustes), 1)
        self.assertEqual(set(self.ajustes[0]["questoes"]), referencias)
        self.assertEqual(set(self.ajustes[0]["rotulos"]), referencias)
        self.assertEqual(self.ajustes[0]["receita"], {"receita": "ficticia_fixa"})
        self.assertEqual([v for v in self.eventos if v[0] == "predizer"],
                         [("predizer", "100", i) for i in sorted(self.protocolo["avaliacao_ids"])])
        self.assertEqual(resumo["linhas"], 10)
        self.assertEqual(resumo["avaliacao"], 2)
        self.assertEqual(len(produtos), 6)
        modelo = json.loads(produtos["modelo_final.json"])
        self.assertEqual(set(modelo["ids"]), referencias)
        previsao = json.loads(produtos["previsao.json"])
        self.assertEqual(previsao["referencias_excluidas"], 8)
        self.assertEqual(previsao["avaliacao_total"], 2)
        self.assertEqual(previsao["decisoes_por_coorte_somente_diagnostico"]
                         ["antigas_sem_referencia"]["total"], 1)
        self.assertEqual(previsao["decisoes_por_coorte_somente_diagnostico"]
                         ["recentes_sem_referencia"]["total"], 1)

    def test_entrega_preserva_probabilidades_crossfit_e_registros_reservados(self):
        e.executar_reserva(self.raiz)
        politica = json.loads((self.raiz / d.CALIBRACAO / "politica.json").read_bytes())
        desenvolvimento = {
            p["id"]: p for p in decodificar_jsonl(
                (self.raiz / d.CALIBRACAO / "predicoes_calibradas.jsonl").read_bytes())
            if p["calibrador"] == politica["calibrador"]
        }
        reserva = {p["id"]: p for p in decodificar_jsonl(
            (self.raiz / d.RESERVA / "predicoes_reserva.jsonl").read_bytes())}
        produtos, _ = e.construir_entrega(self.raiz)
        entregues = {p["id"]: p for p in decodificar_jsonl(produtos["decisoes.jsonl"])}
        for identificador, original in desenvolvimento.items():
            with self.subTest(id=identificador):
                for campo in ("tema_sugerido_id", "confianca", "dentro_dominio", "procedencia_probabilidade"):
                    self.assertEqual(entregues[identificador][campo], original[campo])
                self.assertEqual(entregues[identificador]["procedencia_probabilidade"],
                                 "crossfit_desenvolvimento")
        for identificador, original in reserva.items():
            self.assertEqual(entregues[identificador], original)
        previsao = json.loads(produtos["previsao.json"])
        self.assertEqual(sorted(previsao["procedencias_csv"].values()), [2, 2, 6])

    def test_exportacao_escreve_so_dois_arquivos_e_preserva_outros(self):
        escrever(self.raiz, "README.md", b"Documento existente.\n")
        escrever(self.raiz, "subpasta/arquivo.txt", b"Arquivo independente.\n")
        produtos = {"publicacao.csv": b"csv ficticio\n", "previsao.txt": b"previsao ficticia\n",
                    "nao_exportar.json": b"{}\n"}
        e._publicar_raiz(self.raiz, produtos)
        e._publicar_raiz(self.raiz, produtos)
        self.assertEqual((self.raiz / "README.md").read_bytes(), b"Documento existente.\n")
        self.assertEqual((self.raiz / "subpasta/arquivo.txt").read_bytes(), b"Arquivo independente.\n")
        self.assertFalse((self.raiz / "nao_exportar.json").exists())
        self.assertEqual(list(self.raiz.glob(".produto-*.tmp")), [])
        for nome in ("publicacao.csv", "previsao.txt"):
            self.assertEqual((self.raiz / nome).read_bytes(), produtos[nome])

    def test_destino_divergente_e_recusado_antes_de_qualquer_exportacao(self):
        escrever(self.raiz, "previsao.txt", b"Previsao anterior a preservar.\n")
        produtos = {"publicacao.csv": b"novo csv\n", "previsao.txt": b"nova previsao\n"}
        with self.assertRaisesRegex(ValueError, "divergente"):
            e._publicar_raiz(self.raiz, produtos)
        self.assertFalse((self.raiz / "publicacao.csv").exists())
        self.assertEqual((self.raiz / "previsao.txt").read_bytes(),
                         b"Previsao anterior a preservar.\n")

    def test_verificador_reconstroi_quinze_produtos_e_duas_entregas_raiz(self):
        self.gerar_tudo()
        arquivos = [
            p for diretorio in (d.CALIBRACAO, d.RESERVA, d.DECISOES)
            for p in (self.raiz / diretorio).iterdir()
        ]
        self.assertEqual([len(list((self.raiz / nome).iterdir()))
                          for nome in (d.CALIBRACAO, d.RESERVA, d.DECISOES)], [6, 3, 6])
        antes = {p.relative_to(self.raiz).as_posix(): p.read_bytes()
                 for p in arquivos + [self.raiz / "publicacao.csv", self.raiz / "previsao.txt"]}
        with patch("builtins.print"):
            resumo = e.verificar_tudo(self.raiz)
        self.assertEqual(resumo["produtos_reconstruidos_identicos"], 15)
        self.assertEqual(resumo["entregas_raiz_identicas"], 2)
        self.assertEqual(antes, {nome: (self.raiz / nome).read_bytes() for nome in antes})

    def test_verificador_recusa_entrega_raiz_adulterada(self):
        self.gerar_tudo()
        caminho = self.raiz / "publicacao.csv"
        caminho.write_bytes(caminho.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "raiz diverge"):
            e.executar_entrega(self.raiz, verificar=True)

    def test_verificador_recusa_produto_ausente_e_preserva_os_demais(self):
        self.gerar_tudo()
        caminho = self.raiz / d.DECISOES / "previsao.json"
        # Remoção restrita a um arquivo de fixture, dentro do TemporaryDirectory.
        self.assertTrue(caminho.resolve().is_relative_to(self.raiz))
        caminho.unlink()
        raiz_csv = (self.raiz / "publicacao.csv").read_bytes()
        with self.assertRaises(ValueError):
            e.executar_entrega(self.raiz, verificar=True)
        self.assertFalse(caminho.exists())
        self.assertEqual((self.raiz / "publicacao.csv").read_bytes(), raiz_csv)


class TestBloqueiosCliM4(unittest.TestCase):
    def executar_isolado(self, preparacao):
        programa = r'''
from pathlib import Path
import json, socket, sys, tempfile
from unittest.mock import patch
from classificacao_decisao import __main__ as cli
from classificacao_decisao import execucao

preparacao = sys.argv[1] == "1"
with tempfile.TemporaryDirectory(prefix="teste-audit-m4-", dir=sys.argv[2]) as pasta:
    raiz = Path(pasta).resolve()
    pesos = raiz / ".cache-modelos" / "ficticio.bin"
    pesos.parent.mkdir()
    pesos.write_bytes(b"pesos ficticios")
    ambiente = raiz / ".env"
    ambiente.write_bytes(b"CHAVE_FICTICIA=nao_e_segredo")
    normal = raiz / "normal.json"
    normal.write_bytes(b"{}")

    def esperar_bloqueio(operacao):
        try:
            operacao()
        except RuntimeError:
            return
        raise AssertionError("Operacao deveria ter sido bloqueada.")

    def conferir(_=None):
        esperar_bloqueio(lambda: ambiente.read_bytes())
        esperar_bloqueio(lambda: socket.getaddrinfo("localhost", 80))
        with socket.socket() as canal:
            esperar_bloqueio(lambda: canal.connect(("127.0.0.1", 9)))
        assert normal.read_bytes() == b"{}"
        dependencias = ("numpy", "onnxruntime", "tokenizers", "torch",
                        "transformers", "sentence_transformers", "huggingface_hub")
        if preparacao:
            assert pesos.read_bytes() == b"pesos ficticios"
            for nome in dependencias:
                sys.audit("import", nome, None, [], [], [])
        else:
            esperar_bloqueio(lambda: pesos.read_bytes())
            for nome in dependencias:
                esperar_bloqueio(lambda nome=nome: __import__(nome))
        return {"fixture_auditada": True}

    if preparacao:
        cli._bloquear_operacoes(True)
        conferir()
    else:
        # O próprio comando verificar instala o hook antes de chamar a biblioteca.
        with patch.object(sys, "argv", ["classificacao_decisao", "verificar"]), \
             patch.object(execucao, "verificar_tudo", side_effect=conferir):
            assert cli.main() == 0
print("BLOQUEIOS_OK")
'''
        pasta_tmp = RAIZ / "tmp"
        pasta_tmp.mkdir(exist_ok=True)
        resultado = subprocess.run(
            [sys.executable, "-B", "-c", programa, "1" if preparacao else "0", str(pasta_tmp)],
            cwd=RAIZ, text=True, capture_output=True, timeout=60,
        )
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        self.assertIn("BLOQUEIOS_OK", resultado.stdout)

    def test_comando_verificar_bloqueia_rede_credenciais_pesos_e_imports(self):
        self.executar_isolado(False)

    def test_preparacao_libera_encoder_e_pesos_mas_bloqueia_rede_e_credenciais(self):
        self.executar_isolado(True)


if __name__ == "__main__":
    unittest.main()
