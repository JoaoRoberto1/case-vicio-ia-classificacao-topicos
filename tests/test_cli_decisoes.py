"""Contratos dos comandos offline de decisões, auditoria e avaliação."""

from contextlib import contextmanager, redirect_stderr, redirect_stdout
import csv
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from classificacao_topicos.__main__ import main


@contextmanager
def sem_api():
    with patch("classificacao_topicos.gemini.carregar_configuracao", side_effect=AssertionError("credencial")), \
            patch("classificacao_topicos.execucao.carregar_configuracao", side_effect=AssertionError("credencial")), \
            patch("classificacao_topicos.execucao.gerar_json", side_effect=AssertionError("modelo")), \
            patch("urllib.request.urlopen", side_effect=AssertionError("rede")):
        yield


class TestCLIDecisoes(unittest.TestCase):
    def executar(self, *argumentos):
        saida = io.StringIO()
        with patch("sys.argv", ["classificacao_topicos", *map(str, argumentos)]), \
                sem_api(), redirect_stdout(saida):
            codigo = main()
        return codigo, json.loads(saida.getvalue())

    def test_decisoes_encaminha_padrao_e_retorna_pendencias_com_codigo_um(self):
        resumo = {"total_questoes": 3, "completo": False, "pendentes_fora": 1,
                  "ids_pendentes": ["Q0003"], "decisoes": {"publicar": 1, "revisar": 1, "fora": 0},
                  "revisoes_fora": {"confirmadas_sem_tema": 0, "ids_confirmadas_sem_tema": [],
                                    "temas_encontrados": 0, "ids_temas_encontrados": []}}
        with patch("classificacao_topicos.decisoes.preparar_decisoes", return_value=resumo) as preparar:
            codigo, resultado = self.executar("preparar-decisoes", "--lote", "lote", "--execucao", "recibos",
                                               "--saida", "decisoes")
        preparar.assert_called_once_with(Path("lote"), Path("artefatos/preparacao"), Path("recibos"),
                                          Path("config/politica_v1.json"), Path("decisoes"), confirmacoes_fora=None)
        self.assertEqual(codigo, 1)
        self.assertEqual(resultado["ids_pendentes"], ["Q0003"])
        self.assertEqual(resultado["pendentes_fora"], 1)
        self.assertFalse(resultado["completo"])
        self.assertEqual(resultado["revisoes_fora"], resumo["revisoes_fora"])
        self.assertEqual(resultado["chamadas_api"], 0)

    def test_decisoes_reais_offline_geram_csv_so_apos_confirmacao(self):
        from tests.test_decisoes import DecisoesTests
        fixture = DecisoesTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        argumentos = ("preparar-decisoes", "--lote", fixture.lote, "--preparacao", fixture.preparacao,
                      "--execucao", fixture.execucao, "--politica", fixture.politica, "--saida", fixture.saida)
        originais = {p.name: p.read_bytes() for p in fixture.execucao.iterdir()}
        codigo, pendente = self.executar(*argumentos)
        self.assertEqual(codigo, 1)
        self.assertEqual(pendente["ids_pendentes"], ["Q0003"])
        self.assertFalse((fixture.saida / "publicacao.csv").exists())
        fixture.gravar_confirmacoes()
        codigo, pronto = self.executar(*argumentos, "--confirmacoes-fora", fixture.confirmacoes)
        self.assertEqual(codigo, 0)
        self.assertTrue(pronto["completo"])
        self.assertEqual(pronto["decisoes"], {"publicar": 1, "revisar": 1, "fora": 1})
        self.assertEqual(pronto["chamadas_api"], 0)
        with (fixture.saida / "publicacao.csv").open(encoding="utf-8", newline="") as arquivo:
            linhas = list(csv.DictReader(arquivo))
        self.assertEqual([linha["id"] for linha in linhas], ["Q0001", "Q0002", "Q0003"])
        self.assertEqual(linhas[2]["decisao"], "fora")
        self.assertEqual({p.name: p.read_bytes() for p in fixture.execucao.iterdir()}, originais)

    def test_auditoria_encaminha_padrao_e_resume_estratos_sem_vazar_ids(self):
        manifesto = {"total_questoes": 3, "total_publicadas": 2, "ids": ["Q0001", "Q0002"],
                     "semente": 2026101401, "referencia_tipo": "Referência provisória por IA.",
                     "estratos": {"desenvolvimento": {"N": 1, "n": 1, "metodo": "censo", "selecionados_ids": ["Q0001"]},
                                  "restante": {"N": 1, "n": 1, "metodo": "censo", "selecionados_ids": ["Q0002"]}}}
        with patch("classificacao_topicos.auditoria.preparar_auditoria", return_value=manifesto) as preparar:
            codigo, resultado = self.executar("preparar-auditoria", "--lote", "lote", "--decisoes", "publicacao.csv",
                                               "--saida", "auditoria")
        preparar.assert_called_once_with(Path("artefatos/preparacao"), Path("lote"), Path("publicacao.csv"),
                                          Path("config/politica_v1.json"), Path("auditoria"))
        self.assertEqual(codigo, 0)
        self.assertEqual(resultado["selecionadas"], 2)
        self.assertEqual(resultado["estratos"]["restante"], {"N": 1, "n": 1, "metodo": "censo"})
        self.assertEqual(resultado["chamadas_api"], 0)
        self.assertEqual(resultado["referencia_tipo"], manifesto["referencia_tipo"])

    def test_correcao_de_candidato_fora_pela_cli_gera_revisar_e_preserva_original(self):
        from tests.test_decisoes import DecisoesTests, confirmacao, sugestao
        fixture = DecisoesTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        originais = {p.name: p.read_bytes() for p in fixture.execucao.iterdir()}
        correcao = sugestao("Q0003", requer_revisao=True)
        fixture.gravar_confirmacoes([confirmacao(
            sem_tema=False, situacao="tema_encontrado", sugestao_corrigida=correcao,
            justificativa="A revisão separada encontrou tema ativo para a menção a furto.")])
        codigo, resultado = self.executar(
            "preparar-decisoes", "--lote", fixture.lote, "--preparacao", fixture.preparacao,
            "--execucao", fixture.execucao, "--politica", fixture.politica,
            "--confirmacoes-fora", fixture.confirmacoes, "--saida", fixture.saida)
        self.assertEqual(codigo, 0)
        self.assertTrue(resultado["completo"])
        self.assertEqual(resultado["decisoes"], {"publicar": 1, "revisar": 2, "fora": 0})
        self.assertEqual(resultado["revisoes_fora"]["temas_encontrados"], 1)
        self.assertEqual(resultado["revisoes_fora"]["ids_temas_encontrados"], ["Q0003"])
        self.assertEqual(resultado["chamadas_api"], 0)
        with (fixture.saida / "publicacao.csv").open(encoding="utf-8", newline="") as arquivo:
            linhas = {linha["id"]: linha for linha in csv.DictReader(arquivo)}
        self.assertEqual(linhas["Q0003"]["decisao"], "revisar")
        self.assertEqual(linhas["Q0003"]["tema_central_id"], "T001")
        self.assertTrue(linhas["Q0003"]["motivo"].strip())
        trilha = {item["id"]: item for item in (
            json.loads(linha) for linha in (fixture.saida / "trilha_decisoes.jsonl").read_text(encoding="utf-8").splitlines())}
        self.assertTrue(trilha["Q0003"]["sugestao"]["sem_tema"])
        self.assertEqual(trilha["Q0003"]["confirmacao_fora"]["sugestao_corrigida"], correcao)
        self.assertEqual({p.name: p.read_bytes() for p in fixture.execucao.iterdir()}, originais)

    def test_avaliacao_encaminha_padrao_e_mantem_qualificacao_da_estimativa(self):
        relatorio = {"total_questoes": 3, "total_publicadas": 2, "total_revisadas": 2,
                     "tipo_referencia": "IA_sem_especialista", "comparacao_central": {"exata": 2},
                     "precisao_condicional": {"conservador": {"estimativa": 1.0}},
                     "cobertura": {"observada": 2 / 3, "inferencia_futura": False}}
        with patch("classificacao_topicos.avaliacao.avaliar_auditoria", return_value=relatorio) as avaliar:
            codigo, resultado = self.executar("avaliar-auditoria", "--auditoria", "auditoria", "--decisoes", "decisoes",
                                               "--revisoes", "revisoes", "--saida", "avaliacao")
        avaliar.assert_called_once_with(Path("artefatos/preparacao"), Path("auditoria"), Path("decisoes"),
                                         Path("revisoes"), Path("avaliacao"))
        self.assertEqual(codigo, 0)
        self.assertEqual(resultado["tipo_referencia"], "IA_sem_especialista")
        self.assertEqual(resultado["precisao_condicional"], relatorio["precisao_condicional"])
        self.assertEqual(resultado["cobertura"], relatorio["cobertura"])
        self.assertEqual(resultado["chamadas_api"], 0)
        self.assertNotIn("precisao", resultado)

    def test_auditoria_e_avaliacao_reais_offline_com_caminhos_explicitos(self):
        from tests.test_avaliacao import AvaliacaoAuditoriaTest
        fixture = AvaliacaoAuditoriaTest()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        auditoria = fixture.raiz / "auditoria_cli"
        csv_original = fixture.decisoes.read_bytes()
        codigo, amostra = self.executar("preparar-auditoria", "--preparacao", fixture.preparacao,
                                        "--lote", fixture.lote, "--decisoes", fixture.decisoes,
                                        "--politica", fixture.politica, "--saida", auditoria)
        self.assertEqual(codigo, 0)
        self.assertEqual(amostra["selecionadas"], 100)
        self.assertEqual(amostra["estratos"]["restante"]["N"], 100)
        self.assertEqual((auditoria / "entradas_cegas.jsonl").read_bytes(),
                         (fixture.auditoria / "entradas_cegas.jsonl").read_bytes())
        codigo, avaliacao = self.executar("avaliar-auditoria", "--preparacao", fixture.preparacao,
                                           "--auditoria", auditoria, "--decisoes", fixture.decisoes,
                                           "--revisoes", fixture.revisoes, "--saida", fixture.saida)
        self.assertEqual(codigo, 0)
        self.assertEqual(avaliacao["revisadas"], 100)
        self.assertEqual(avaliacao["comparacao_central"]["exata"], 100)
        self.assertEqual(avaliacao["tipo_referencia"], "IA_sem_especialista")
        self.assertEqual(avaliacao["cobertura"]["observada_exata"], "60/61")
        self.assertTrue((fixture.saida / "relatorio_avaliacao.json").is_file())
        self.assertEqual(fixture.decisoes.read_bytes(), csv_original)

    def test_erros_de_entrada_terminam_com_codigo_dois_sem_json_de_sucesso(self):
        casos = [
            ("classificacao_topicos.decisoes.preparar_decisoes",
             ["preparar-decisoes", "--lote", "lote", "--execucao", "recibos", "--saida", "decisoes"]),
            ("classificacao_topicos.auditoria.preparar_auditoria",
             ["preparar-auditoria", "--lote", "lote", "--decisoes", "decisoes", "--saida", "auditoria"]),
            ("classificacao_topicos.avaliacao.avaliar_auditoria",
             ["avaliar-auditoria", "--auditoria", "auditoria", "--decisoes", "decisoes",
              "--revisoes", "revisoes", "--saida", "avaliacao"]),
        ]
        for alvo, argumentos in casos:
            saida, erros = io.StringIO(), io.StringIO()
            with self.subTest(comando=argumentos[0]), patch("sys.argv", ["classificacao_topicos", *argumentos]), \
                    patch(alvo, side_effect=ValueError("Entrada inválida.")), sem_api(), \
                    redirect_stdout(saida), redirect_stderr(erros), self.assertRaises(SystemExit) as erro:
                main()
            self.assertEqual(erro.exception.code, 2)
            self.assertEqual(saida.getvalue(), "")
            self.assertIn("Erro: Entrada inválida.", erros.getvalue())

    def test_comandos_exigem_destinos_e_entradas_essenciais(self):
        for comando in ("preparar-decisoes", "preparar-auditoria", "avaliar-auditoria"):
            with self.subTest(comando=comando), patch("sys.argv", ["classificacao_topicos", comando]), \
                    sem_api(), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as erro:
                main()
            self.assertEqual(erro.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
