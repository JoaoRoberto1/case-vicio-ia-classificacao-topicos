"""Fronteiras M9 com dados sintéticos; não usa questões ou rótulos do case."""

from copy import deepcopy
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from classificacao_politica import experimento as exp
from classificacao_politica import preparacao as prep
from classificacao_politica.politica import ANCORA, RECEITAS_CONCORDANCIA, resumir, selecionar


def predicao(identificador, *, particao=1, acerto=True, confianca=.95):
    return {
        "id": identificador, "receita": ANCORA, "tema_sugerido_id": "tema_sintetico",
        "particao_interna": particao, "confianca_oof": confianca, "confianca": confianca,
        "concordancia_algoritmos": True, "acertos": {"ramo": acerto, "exato": acerto},
        "atributos_confianca": [.5, .1, .3, .4, 1., .5, .6, .1, .2],
    }


def internas(n=20):
    return [predicao(f"treino_{i}", particao=1+i % 3) for i in range(n)]


def replicar_receitas(ps):
    return {nome: [{**deepcopy(p), "receita": nome} for p in ps] for nome in RECEITAS_CONCORDANCIA}


class AvaliacaoBlocoPoliticaM9Tests(unittest.TestCase):
    def test_sobreposicao_ou_universo_vazio_recusado_antes_de_ajustar(self):
        treino = internas()
        for a, b in ((treino, [deepcopy(treino[0])]), ([], [predicao("teste")]), (treino, [])):
            with self.subTest(n_treino=len(a), n_teste=len(b)), \
                 patch.object(exp, "selecionar") as escolher, patch.object(exp, "ajustar") as ajustar:
                with self.assertRaises(ValueError):
                    exp.avaliar_bloco(a, b)
                escolher.assert_not_called()
                ajustar.assert_not_called()

    def test_aplica_probabilidade_externa_recalculada_e_nunca_oof(self):
        treino = internas()
        teste = [predicao("externa_1", confianca=1), predicao("externa_2", confianca=0)]
        antes = deepcopy((treino, teste))
        modelo_sentinela = {"treino": "sintetico"}
        with patch.object(exp, "ajustar", return_value=modelo_sentinela) as ajustar, \
             patch.object(exp, "prever", side_effect=[.94, .96]) as prever:
            politica, modelo, ps = exp.avaliar_bloco(treino, teste)
        ajustar.assert_called_once_with(treino)
        self.assertEqual(prever.call_args_list[0].args, (modelo_sentinela, teste[0]))
        self.assertEqual(prever.call_args_list[1].args, (modelo_sentinela, teste[1]))
        self.assertEqual(politica["corte"], .95)
        self.assertEqual([p["confianca"] for p in ps], [.94, .96])
        self.assertEqual([p["publicaria_m9"] for p in ps], [False, True])
        self.assertEqual([p["confianca_oof"] for p in ps], [1, 0])
        self.assertIs(modelo, modelo_sentinela)
        self.assertEqual((treino, teste), antes)

    def test_alvos_externos_nao_afetam_escolha_calibrador_probabilidade_ou_decisao(self):
        treino = internas()
        teste = [predicao(f"externa_{i}", confianca=.01) for i in range(3)]
        politica, modelo, ps = exp.avaliar_bloco(treino, teste)
        alteradas = deepcopy(teste)
        for p in alteradas:
            p["acertos"] = {"ramo": False, "exato": False}
            p["referencia_fora"] = True
            p["disciplina_referencia"] = "referencia_alterada"
        politica2, modelo2, ps2 = exp.avaliar_bloco(treino, alteradas)
        self.assertEqual((politica2, modelo2), (politica, modelo))
        campos = ("id", "tema_sugerido_id", "confianca", "publicaria_m9")
        self.assertEqual([{k: p[k] for k in campos} for p in ps2],
                         [{k: p[k] for k in campos} for p in ps])
        self.assertTrue(all(p["publicaria_m9"] for p in ps))

    def test_cobertura_559_nao_precisa_de_rotulos_nem_de_particoes(self):
        politica = selecionar(internas())
        ps = [{"id": f"avaliacao_{i}", "confianca": .96 if i < 10 else .4,
               "concordancia_algoritmos": True} for i in range(559)]
        resultado = exp._cobertura_sem_rotulos(ps, politica)
        self.assertEqual((resultado["total"], resultado["n"]), (559, 10))
        self.assertAlmostEqual(resultado["coverage"], 10/559)
        self.assertIsNone(resultado["precision"])
        for p in ps:
            p["acertos"] = object()
        self.assertEqual(exp._cobertura_sem_rotulos(ps, politica), resultado)


class ReconstrucaoPoliticaM9Tests(unittest.TestCase):
    def setUp(self):
        self.treino = [f"treino_{i}" for i in range(9)]
        self.teste = ["externa_0", "externa_1", "externa_2"]
        self.qs = {i: {"id": i} for i in self.treino + self.teste}
        self.rs = {i: {"id": i, "rotulo_sintetico": i} for i in self.qs}
        self.grupos = [{"ids": [i]} for i in self.qs]
        self.fold = {"indice": 1, "treino_ids": self.treino, "validacao_ids": self.teste}
        self.config = {"particoes_internas": 3, "salt": "teste-m9"}

    def test_oof_recebe_apenas_questoes_e_rotulos_do_treino_externo(self):
        motor = Mock(name="motor_sintetico")
        chamadas = []

        def oof_recebida(motor_recebido, qs, rs, folds, receitas):
            self.assertIs(motor_recebido, motor)
            self.assertEqual(set(qs), set(self.treino))
            self.assertEqual(set(rs), set(self.treino))
            self.assertEqual(receitas, list(prep.RECEITAS))
            self.assertFalse(set(rs) & set(self.teste))
            for fold in folds:
                self.assertEqual(set(fold["treino_ids"]) | set(fold["validacao_ids"]), set(self.treino))
                self.assertFalse(set(fold["treino_ids"]) & set(fold["validacao_ids"]))
            chamadas.append(deepcopy((qs, rs, folds, receitas)))
            return {nome: [{"id": i} for i in sorted(qs)] for nome in receitas}

        antes = deepcopy((self.qs, self.rs, self.grupos, self.fold, self.config))
        with patch.object(prep, "_oof", side_effect=oof_recebida):
            primeiro = prep.reconstruir_internas(motor, self.qs, self.rs, self.grupos, self.fold, self.config)
            alterados = deepcopy(self.rs)
            for i in self.teste:
                alterados[i] = {"id": i, "rotulo_sintetico": "externo_proibido"}
            segundo = prep.reconstruir_internas(motor, self.qs, alterados, self.grupos, self.fold, self.config)
        self.assertEqual(chamadas[0], chamadas[1])
        self.assertEqual(primeiro, segundo)
        self.assertEqual((self.qs, self.rs, self.grupos, self.fold, self.config), antes)

    def test_cortes_externos_invalidos_recusados_antes_de_oof(self):
        alteracoes = [{"treino_ids": []}, {"validacao_ids": []}, {"validacao_ids": [self.treino[0]]}]
        for alteracao in alteracoes:
            with self.subTest(alteracao=alteracao), patch.object(prep, "_oof") as oof:
                with self.assertRaises(ValueError):
                    prep.reconstruir_internas(Mock(), self.qs, self.rs, self.grupos,
                                              {**self.fold, **alteracao}, self.config)
                oof.assert_not_called()

    def test_reconstituicao_recusa_oof_com_id_externo_ou_cobertura_incompleta(self):
        for ids in (self.treino[:-1], self.treino + self.teste[:1]):
            resultados = {nome: [{"id": i} for i in ids] for nome in prep.RECEITAS}
            with self.subTest(n=len(ids)), patch.object(prep, "_oof", return_value=resultados):
                with self.assertRaises(ValueError):
                    prep.reconstruir_internas(Mock(), self.qs, self.rs, self.grupos, self.fold, self.config)

    def test_grupo_cruzando_externa_recusado_antes_de_oof(self):
        grupo_cruzado = [{"ids": [self.treino[0], self.teste[0]]}]
        grupo_cruzado += [g for g in self.grupos if g["ids"][0] not in {self.treino[0], self.teste[0]}]
        with patch.object(prep, "_oof") as oof:
            with self.assertRaises(ValueError):
                prep.reconstruir_internas(Mock(), self.qs, self.rs, grupo_cruzado, self.fold, self.config)
            oof.assert_not_called()


class EstabilidadePoliticaM9Tests(unittest.TestCase):
    def test_um_acerto_por_bloco_passa_somente_como_experimental(self):
        ps = [predicao(f"p{i}", particao=i) for i in (1, 2, 3)]
        resumo = resumir(ps, [True] * 3)
        resultado = exp.avaliar_estabilidade(resumo)
        self.assertTrue(resultado["aprovada_experimentalmente"])
        self.assertFalse(resultado["garantia_populacional_95"])
        self.assertEqual(resultado["motivos"], [])
        self.assertLess(resumo["wilson95"]["inferior"], .95)
        self.assertIn("1/1", resultado["limitacao"])

    def test_sem_publicacoes_falha_sem_tentar_comparar_none(self):
        ps = [predicao(f"p{i}", particao=i) for i in (1, 2, 3)]
        resumo = resumir(ps, [False] * 3)
        self.assertIsNone(resumo["precision"])
        resultado = exp.avaliar_estabilidade(resumo)
        self.assertFalse(resultado["aprovada_experimentalmente"])
        self.assertEqual(len(resultado["motivos"]), 2)

    def test_fold_sem_publicacoes_e_concentracao_em_um_fold_falham(self):
        ps = [predicao(f"p{i}", particao=i) for i in (1, 2, 3)]
        for aceitos in ([True, True, False], [True, False, False]):
            resultado = exp.avaliar_estabilidade(resumir(ps, aceitos))
            self.assertFalse(resultado["aprovada_experimentalmente"])
            self.assertEqual(len(resultado["motivos"]), 1)

    def test_fold_ausente_do_universo_tambem_falha(self):
        ps = [predicao("p1", particao=1), predicao("p2", particao=2)]
        self.assertFalse(exp.avaliar_estabilidade(resumir(ps, [True, True]))["aprovada_experimentalmente"])

    def test_agregado_acima_95_nao_oculta_fold_abaixo_95(self):
        ps = [predicao(f"p{i}", particao=1 if i < 40 else 2) for i in range(80)]
        ps += [predicao(f"ultimo_{i}", particao=3, acerto=i < 19) for i in range(21)]
        resumo = resumir(ps, [True] * len(ps))
        self.assertGreater(resumo["precision"], .95)
        self.assertLess(resumo["por_particao"][2]["precision"], .95)
        resultado = exp.avaliar_estabilidade(resumo)
        self.assertFalse(resultado["aprovada_experimentalmente"])
        self.assertEqual(len(resultado["motivos"]), 1)


class CheckpointPoliticaM9Tests(unittest.TestCase):
    def test_par_produto_hash_ausente_retorna_none_sem_criar_arquivos(self):
        with tempfile.TemporaryDirectory(prefix="teste-checkpoint-m9-") as nome_pasta:
            pasta = Path(nome_pasta)
            self.assertIsNone(prep.ler_parcial(pasta, "sintetico.json"))
            self.assertEqual(list(pasta.iterdir()), [])

    def test_par_integro_retorna_bytes_exatos_sem_alterar_arquivos(self):
        conteudo = '{"origem": "sintética", "n": 3}\n'.encode("utf-8")
        with tempfile.TemporaryDirectory(prefix="teste-checkpoint-m9-") as nome_pasta:
            pasta = Path(nome_pasta)
            (pasta / "sintetico.json").write_bytes(conteudo)
            assinatura = (prep.sha(conteudo) + "\n").encode()
            (pasta / "sintetico.json.sha256").write_bytes(assinatura)
            self.assertEqual(prep.ler_parcial(pasta, "sintetico.json"), conteudo)
            self.assertEqual((pasta / "sintetico.json").read_bytes(), conteudo)
            self.assertEqual((pasta / "sintetico.json.sha256").read_bytes(), assinatura)

    def test_produto_ou_hash_orfao_recusado_sem_assinar_ou_reparar(self):
        conteudo = b'{"origem":"sintetica"}\n'
        for apenas_produto in (True, False):
            with self.subTest(apenas_produto=apenas_produto), \
                 tempfile.TemporaryDirectory(prefix="teste-checkpoint-m9-") as nome_pasta:
                pasta = Path(nome_pasta)
                if apenas_produto:
                    (pasta / "sintetico.json").write_bytes(conteudo)
                else:
                    (pasta / "sintetico.json.sha256").write_bytes((prep.sha(conteudo) + "\n").encode())
                antes = {p.name: p.read_bytes() for p in pasta.iterdir()}
                with self.assertRaisesRegex(ValueError, "incompleto"):
                    prep.ler_parcial(pasta, "sintetico.json")
                self.assertEqual({p.name: p.read_bytes() for p in pasta.iterdir()}, antes)

    def test_produto_alterado_ou_hash_invalido_recusado_sem_sobrescrever(self):
        original = b'{"n":3}\n'
        pares = [(b'{"n":4}\n', (prep.sha(original) + "\n").encode()),
                 (original, b"hash_invalido\n"), (original, prep.sha(original).encode())]
        for conteudo, assinatura in pares:
            with self.subTest(conteudo=conteudo, assinatura=assinatura), \
                 tempfile.TemporaryDirectory(prefix="teste-checkpoint-m9-") as nome_pasta:
                pasta = Path(nome_pasta)
                (pasta / "sintetico.json").write_bytes(conteudo)
                (pasta / "sintetico.json.sha256").write_bytes(assinatura)
                with self.assertRaisesRegex(ValueError, "alterado"):
                    prep.ler_parcial(pasta, "sintetico.json")
                self.assertEqual((pasta / "sintetico.json").read_bytes(), conteudo)
                self.assertEqual((pasta / "sintetico.json.sha256").read_bytes(), assinatura)


class IntegracaoPoliticaM9Tests(unittest.TestCase):
    def test_construcao_sintetica_659_preserva559_sem_rotulos_e_seleciona_antes_dos_diagnosticos(self):
        dev = [predicao(f"dev_{i:03d}", particao=1+i % 3) for i in range(80)]
        resultados = replicar_receitas(dev)
        blocos = {}
        for indice in (1, 2, 3):
            treino = [deepcopy(p) for p in dev if p["particao_interna"] != indice]
            for i, p in enumerate(treino):
                p["particao_interna"] = i % 3
            blocos[indice] = {
                "externa": {"indice": indice, "treino_ids": [p["id"] for p in treino],
                            "validacao_ids": [p["id"] for p in dev if p["particao_interna"] == indice]},
                "predicoes": replicar_receitas(treino),
            }
        reserva = [predicao(f"reserva_{i:03d}") for i in range(20)]
        avaliacao = [predicao(f"avaliacao_{i:03d}") for i in range(559)]
        for p in reserva + avaliacao:
            del p["particao_interna"]
            del p["confianca_oof"]
        for p in avaliacao:
            del p["acertos"]
        selecoes = []

        def selecionar_espiao(ps):
            self.assertTrue(all(p["id"].startswith("dev_") for p in ps))
            selecoes.append({p["id"] for p in ps})
            return selecionar(ps)

        def ler_json(_raiz, nome):
            for indice, bloco in blocos.items():
                if nome == f"{prep.CACHE}/internas_bloco{indice}.json":
                    return deepcopy(bloco)
            if nome == f"{prep.M8}/metricas.json":
                return {"selecao_aninhada": {"publicacao": {"n": 0}}, "avaliacao559": {"publicaria": 0}}
            if nome == "artefatos/preparacao/temas_preparados.json":
                return [{"tema_id": "tema_sintetico", "status": "active", "nivel": 1}]
            raise AssertionError("Leitura não prevista pela fixture sintética.")

        def ler_jsonl(_raiz, nome):
            self.assertEqual(len(selecoes), 4, "Diagnóstico lido antes de congelar todas as escolhas.")
            if nome == f"{prep.CACHE}/predicoes_20_concordancia.jsonl":
                return deepcopy(reserva)
            if nome == f"{prep.CACHE}/sugestoes_559_concordancia.jsonl":
                return deepcopy(avaliacao)
            raise AssertionError("Leitura não prevista pela fixture sintética.")

        with tempfile.TemporaryDirectory(prefix="teste-politica-m9-") as pasta, \
             patch.object(exp, "carregar_cache", return_value={"produtos_sha256": {}}), \
             patch.object(exp, "assinar", return_value={}), patch.object(exp, "conferir_assinaturas"), \
             patch.object(exp, "_ler_resultados", return_value=resultados), \
             patch.object(exp, "ler_json", side_effect=ler_json), \
             patch.object(exp, "ler_jsonl", side_effect=ler_jsonl), \
             patch.object(exp, "selecionar", side_effect=selecionar_espiao):
            produtos, metricas = exp.construir_produtos(Path(pasta))
            self.assertEqual(list(Path(pasta).iterdir()), [], "O construtor não deve gravar arquivos.")
        self.assertEqual(len(selecoes[0]), 80)
        self.assertEqual(sorted(len(ids) for ids in selecoes[1:]), [53, 53, 54])
        self.assertEqual(metricas["candidata559"]["total"], 559)
        self.assertIsNone(metricas["candidata559"]["precision"])
        self.assertFalse(metricas["oficial_substituida"])
        ps559 = [json.loads(linha) for linha in produtos["sugestoes_559.jsonl"].decode().splitlines()]
        self.assertEqual(len(ps559), 559)
        self.assertTrue(all("acertos" not in p for p in ps559))
        linhas = list(csv.DictReader(io.StringIO(produtos["publicacao_candidata.csv"].decode())))
        self.assertEqual(len(linhas), 659)
        self.assertEqual(len({r["id"] for r in linhas}), 659)
        self.assertTrue(all(p["precision"] is None for p in metricas["curvas_559_sem_rotulos"]))

    def test_helpers_funcionam_em_subprocesso_com_rede_encoder_e_env_bloqueados(self):
        codigo = '''
import json
import socket
from classificacao_decisao.__main__ import _bloquear_operacoes
_bloquear_operacoes(False)
from classificacao_politica.experimento import avaliar_bloco
treino = [{"id": "t"+str(i), "particao_interna": i%3,
           "confianca_oof": .95, "concordancia_algoritmos": True,
           "atributos_confianca": [.1]*9,
           "acertos": {"ramo": True, "exato": True}} for i in range(20)]
teste = [{"id": "externa", "confianca_oof": 0,
          "concordancia_algoritmos": True, "atributos_confianca": [.1]*9}]
politica, modelo, ps = avaliar_bloco(treino, teste)
assert ps[0]["publicaria_m9"] is True
bloqueios = 0
for operacao in (lambda: socket.getaddrinfo("localhost", 80),
                 lambda: __import__("onnxruntime"), lambda: open(".env", "rb")):
    try:
        operacao()
    except RuntimeError:
        bloqueios += 1
assert bloqueios == 3
print(json.dumps({"bloqueios": bloqueios, "decisoes": len(ps)}))
'''
        processo = subprocess.run([sys.executable, "-E", "-B", "-S", "-X", "utf8", "-c", codigo],
                                  cwd=Path(__file__).resolve().parents[1], capture_output=True,
                                  text=True, encoding="utf-8", timeout=30)
        self.assertEqual(processo.returncode, 0, processo.stderr)
        self.assertEqual(json.loads(processo.stdout), {"bloqueios": 3, "decisoes": 1})


if __name__ == "__main__":
    unittest.main()
