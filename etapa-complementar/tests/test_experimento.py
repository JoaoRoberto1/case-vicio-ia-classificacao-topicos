"""Controles do experimento com dados inteiramente sintéticos.

Não carrega questões, referências humanas, configurações ou métricas do case.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from classificacao_local import experimento
from classificacao_local.classificador import predizer, treinar


RAIZ = Path(__file__).resolve().parents[1]
DESENVOLVIMENTO = [f"D{i:02}" for i in range(1, 7)]
RESERVA = ["R01", "R02"]
AVALIACAO = ["A01", "A02"]


def dados_sinteticos():
    temas = [
        {
            "tema_id": "RAIZ", "titulo": "Catálogo sintético", "caminho": "Catálogo",
            "descricao": "", "status": "active", "nivel": "0",
            "parent_id": "", "ancestrais_ids": [],
        },
        {
            "tema_id": "AMBAR", "titulo": "Pigmento âmbar",
            "caminho": "Catálogo > Pigmento âmbar",
            "descricao": "Tinta amarela e pigmento cromático.",
            "status": "active", "nivel": "1",
            "parent_id": "RAIZ", "ancestrais_ids": ["RAIZ"],
        },
        {
            "tema_id": "PRISMA", "titulo": "Formas prisma",
            "caminho": "Catálogo > Formas prisma",
            "descricao": "Figuras com faces e volume geométrico.",
            "status": "active", "nivel": "1",
            "parent_id": "RAIZ", "ancestrais_ids": ["RAIZ"],
        },
    ]
    taxonomia = {"registros": temas, "por_id": {t["tema_id"]: t for t in temas}}
    textos = {
        "D01": "pigmento âmbar tinta amarela primeiroexemplo",
        "D02": "prisma faces volume primeirovolume",
        "D03": "tinta cromática âmbar segundoexemplo",
        "D04": "figura prisma geométrico segundovolume",
        "D05": "pigmento cromático prisma misturaexemplo",
        "D06": "galáxia cometa nebulosa exterior",
        "R01": "segredoreserva pigmento",
        "R02": "segredoreserva prisma",
        "A01": "futuroavaliacao pigmento âmbar",
        "A02": "futuroavaliacao prisma volume",
    }
    questoes = [
        {
            "id": identificador, "enunciado": texto,
            "comando": "Examine a descrição fictícia.",
            "alternativas": {"a": "Afirmação ilustrativa."},
            "coorte": "metadadoirrelevante",
            "disciplina_origem": "origemnaoutilizavel",
        }
        for identificador, texto in textos.items()
    ]
    centrais = {
        "D01": "AMBAR", "D02": "PRISMA", "D03": "AMBAR",
        "D04": "PRISMA", "D05": "AMBAR", "D06": "",
        "R01": "AMBAR", "R02": "PRISMA",
    }
    rotulos = [
        {
            "id": identificador, "tema_central_id": central,
            "extras_ids": ["PRISMA"] if identificador == "D05" else [],
            "fora_da_taxonomia": not central,
            "disciplina": "Fora" if not central else "Catálogo sintético",
        }
        for identificador, central in centrais.items()
    ]
    internas = []
    for indice, inicio in enumerate(range(0, 6, 2), start=1):
        validacao = DESENVOLVIMENTO[inicio:inicio + 2]
        internas.append({
            "indice": indice,
            "treino_ids": [i for i in DESENVOLVIMENTO if i not in validacao],
            "validacao_ids": validacao,
        })
    particoes = {
        "folds": [{
            "indice": 1, "treino_ids": list(DESENVOLVIMENTO),
            "teste_ids": list(RESERVA), "internas": internas,
        }],
        "rotulados_ids": DESENVOLVIMENTO + RESERVA,
        "avaliacao_ids": list(AVALIACAO),
        "grupos": [
            {"id": "grupo-" + i, "ids": [i]}
            for i in DESENVOLVIMENTO + RESERVA + AVALIACAO
        ],
    }
    config_protocolo = {
        "versao": 2, "particao_externa_reservada": 1,
        "contagens": {
            "desenvolvimento": 6, "reserva": 2,
            "avaliacao": 2, "particoes_internas": 3,
        },
        "uso_reserva": "Reservada até o congelamento da receita completa.",
    }
    config = {
        "versao": 1,
        "criterio_selecao": [
            "acertos_ramo_decrescente",
            "acertos_exato_decrescente",
            "receita_id_crescente",
        ],
        "top_k": 2,
        "limiares_diagnosticos_score": [0.0, 0.5, 1.0],
        "receitas": {
            "lexical": {
                "peso_catalogo": 0.7, "peso_exemplos": 0.3, "peso_leis": 0.0,
            },
            "lexical_leis": {
                "peso_catalogo": 0.6, "peso_exemplos": 0.3, "peso_leis": 0.1,
            },
        },
    }
    return questoes, rotulos, taxonomia, particoes, config_protocolo, config


def linhas_json(conteudo: bytes) -> list[dict]:
    return [json.loads(linha) for linha in conteudo.decode("utf-8").splitlines()]


class TestProtocoloExperimento(unittest.TestCase):
    def setUp(self):
        (_, _, _, self.particoes,
         self.config, _) = dados_sinteticos()

    def test_reserva_fixa_e_cobertura_das_internas(self):
        protocolo = experimento.selecionar_protocolo(self.particoes, self.config)
        self.assertEqual(protocolo["reserva_ids"], RESERVA)
        self.assertEqual(protocolo["desenvolvimento_ids"], DESENVOLVIMENTO)
        self.assertEqual(protocolo["avaliacao_ids"], AVALIACAO)
        self.assertFalse(protocolo["reserva_inferida_ou_avaliada"])
        contagens = Counter(
            identificador
            for fold in protocolo["particoes_internas"]
            for identificador in fold["validacao_ids"]
        )
        self.assertEqual(contagens, Counter(DESENVOLVIMENTO))

    def test_recusa_particao_que_incorpora_reserva_ao_treino(self):
        fold = self.particoes["folds"][0]["internas"][0]
        fold["treino_ids"][0] = "R01"
        with self.assertRaisesRegex(ValueError, "só o desenvolvimento"):
            experimento.selecionar_protocolo(self.particoes, self.config)

    def test_recusa_referencia_validada_duas_vezes(self):
        internas = self.particoes["folds"][0]["internas"]
        internas[1]["treino_ids"] = internas[0]["treino_ids"].copy()
        internas[1]["validacao_ids"] = internas[0]["validacao_ids"].copy()
        with self.assertRaisesRegex(ValueError, "exatamente uma vez"):
            experimento.selecionar_protocolo(self.particoes, self.config)

    def test_recusa_grupo_semelhante_cruzando_cada_tipo_de_corte(self):
        for esquerda, direita in (
            ("D01", "R01"), ("D01", "A01"), ("D01", "D03"),
        ):
            with self.subTest(grupo=(esquerda, direita)):
                adulteradas = deepcopy(self.particoes)
                adulteradas["grupos"] = [
                    g for g in adulteradas["grupos"]
                    if not ({esquerda, direita} & set(g["ids"]))
                ]
                adulteradas["grupos"].append({
                    "id": "grupo-semelhante", "ids": [esquerda, direita],
                })
                with self.assertRaisesRegex(ValueError, "atravessa uma partição"):
                    experimento.selecionar_protocolo(adulteradas, self.config)

    def test_recusa_grupo_omitido_ou_repetido(self):
        for tipo in ("omitido", "repetido"):
            with self.subTest(tipo=tipo):
                adulteradas = deepcopy(self.particoes)
                if tipo == "omitido":
                    adulteradas["grupos"].pop()
                else:
                    adulteradas["grupos"].append(
                        deepcopy(adulteradas["grupos"][0]))
                with self.assertRaises(ValueError):
                    experimento.selecionar_protocolo(adulteradas, self.config)

    def test_recusa_tamanho_da_reserva_diferente_do_congelado(self):
        self.config["contagens"]["reserva"] = 1
        with self.assertRaisesRegex(ValueError, "Contagens incompatíveis"):
            experimento.selecionar_protocolo(self.particoes, self.config)


class TestProcessamentoExperimento(unittest.TestCase):
    def setUp(self):
        (self.questoes, self.rotulos, self.taxonomia, particoes,
         config_protocolo, self.config) = dados_sinteticos()
        self.protocolo = experimento.selecionar_protocolo(
            particoes, config_protocolo)

    def processar(self):
        return experimento.processar_experimento(
            self.questoes, self.rotulos, self.taxonomia,
            self.protocolo, self.config,
        )

    def test_reserva_e_validacao_nao_entram_no_ajuste_nem_no_vocabulario(self):
        with (
            patch.object(experimento, "treinar", wraps=treinar) as ajuste,
            patch.object(experimento, "predizer", wraps=predizer) as inferencia,
            patch.object(socket.socket, "connect",
                         side_effect=AssertionError("rede proibida")),
        ):
            produtos, resumo = self.processar()
        self.assertEqual(ajuste.call_count, 8)
        for chamada in ajuste.call_args_list:
            questoes, rotulos, _, _ = chamada.args
            ids = {q["id"] for q in questoes}
            self.assertEqual(ids, {r["id"] for r in rotulos})
            self.assertTrue(ids <= set(DESENVOLVIMENTO))
            self.assertFalse(ids & set(RESERVA + AVALIACAO))
        vistos = Counter()
        for chamada in inferencia.call_args_list:
            modelo, questao = chamada.args
            identificador = questao["id"]
            vistos[identificador] += 1
            treino = {r["id"] for r in modelo["treino"]}
            self.assertNotIn(identificador, treino)
            self.assertNotIn(identificador, RESERVA)
            self.assertNotIn("segredoreserva", modelo["idf"])
            self.assertNotIn("futuroavaliacao", modelo["idf"])
            self.assertNotIn("metadadoirrelevante", modelo["idf"])
            self.assertNotIn("origemnaoutilizavel", modelo["idf"])
        self.assertEqual(vistos, Counter({
            **{i: 2 for i in DESENVOLVIMENTO},
            **{i: 1 for i in AVALIACAO},
        }))
        for nome, conteudo in produtos.items():
            if nome.startswith("modelo_"):
                modelo = json.loads(conteudo)
                self.assertEqual(
                    {r["id"] for r in modelo["treino"]},
                    set(DESENVOLVIMENTO),
                )
                self.assertNotIn("segredoreserva", modelo["idf"])
        self.assertEqual(resumo["reserva_sem_predicao"], 2)

    def test_alterar_conteudo_e_rotulos_da_reserva_nao_altera_resultados(self):
        esperado = self.processar()
        for questao in self.questoes:
            if questao["id"] in RESERVA:
                questao["enunciado"] = "outrareserva sem qualquer relação"
                questao["comando"] = "Não consultar."
        for rotulo in self.rotulos:
            if rotulo["id"] in RESERVA:
                rotulo.update({
                    "tema_central_id": "", "extras_ids": [],
                    "fora_da_taxonomia": True, "disciplina": "Outra",
                })
        self.assertEqual(self.processar(), esperado)

    def test_oof_uma_vez_por_receita_e_apenas_uma_sugestao_por_avaliacao(self):
        produtos, _ = self.processar()
        predicoes = linhas_json(produtos["predicoes_desenvolvimento.jsonl"])
        for receita in self.config["receitas"]:
            selecionadas = [p for p in predicoes if p["receita"] == receita]
            self.assertEqual(
                Counter(p["id"] for p in selecionadas),
                Counter(DESENVOLVIMENTO),
            )
            for p in selecionadas:
                fold = next(f for f in self.protocolo["particoes_internas"]
                            if f["indice"] == p["particao_interna"])
                self.assertIn(p["id"], fold["validacao_ids"])
                self.assertNotIn(p["id"], fold["treino_ids"])
                self.assertTrue(
                    {v["id"] for v in p["vizinhos"]} <= set(fold["treino_ids"]))
        sugestoes = linhas_json(produtos["sugestoes_avaliacao.jsonl"])
        self.assertEqual(Counter(p["id"] for p in sugestoes), Counter(AVALIACAO))
        self.assertTrue(all(p["uso"] == "sugestao_intermediaria" for p in sugestoes))
        self.assertTrue(all("confianca" not in p and "decisao" not in p
                            for p in predicoes + sugestoes))

    def test_fora_permanece_no_denominador_e_curva_vazia_tem_taxa_nula(self):
        produtos, _ = self.processar()
        relatorio = json.loads(produtos["metricas_desenvolvimento.json"])
        self.assertEqual(
            relatorio["referencias_desenvolvimento"]["fora"], 1)
        self.assertFalse(relatorio["score_e_probabilidade"])
        self.assertFalse(relatorio["curva_define_publicacao"])
        for metricas in relatorio["receitas"].values():
            self.assertEqual(metricas["geral"]["total"], 6)
            self.assertEqual(metricas["dentro_taxonomia"]["total"], 5)
            self.assertEqual(metricas["fora_taxonomia"]["total"], 1)
            self.assertEqual(
                metricas["fora_taxonomia"]["acertos"],
                {"ramo": 0, "exato": 0, "imediato": 0},
            )
            for modo, acertos in metricas["geral"]["acertos"].items():
                self.assertEqual(
                    metricas["geral"]["taxas_acerto"][modo], acertos / 6)
            vazia = next(m for m in metricas["curva_diagnostica_score"]
                         if m["limiar"] == 1.0)
            self.assertEqual(vazia["total"], 0)
            self.assertEqual(vazia["fracao_retida"], 0.0)
            self.assertIsNone(vazia["taxa_top_k_ramo"])
            self.assertTrue(all(t is None for t in vazia["taxas_acerto"].values()))

    def test_produtos_deterministicos_e_modelo_serializado_reproduz_sugestoes(self):
        produtos, resumo = self.processar()
        self.assertEqual(self.processar(), (produtos, resumo))
        # Alterar a ordem de entrada não muda os produtos nem a seleção.
        self.questoes.reverse()
        self.rotulos.reverse()
        self.assertEqual(self.processar(), (produtos, resumo))
        selecionada = resumo["receita_selecionada"]
        modelo = json.loads(produtos[f"modelo_{selecionada}.json"])
        questoes_por_id = {q["id"]: q for q in self.questoes}
        for salvo in linhas_json(produtos["sugestoes_avaliacao.jsonl"]):
            refeito = predizer(
                modelo, questoes_por_id[salvo["id"]],
                top_k=self.config["top_k"],
            )
            self.assertEqual(
                salvo, {**refeito, "receita": selecionada,
                        "uso": "sugestao_intermediaria"})

    def test_protocolo_interno_adulterado_nao_pode_inferir_reserva(self):
        self.protocolo["particoes_internas"][0]["validacao_ids"][0] = "R01"
        with (
            patch.object(experimento, "predizer", wraps=predizer) as inferencia,
            self.assertRaisesRegex(ValueError, "Partição interna inválida"),
        ):
            self.processar()
        inferencia.assert_not_called()

    def test_dados_fora_do_protocolo_sao_recusados_antes_do_ajuste(self):
        self.questoes.append({**self.questoes[0], "id": "INTRUSA"})
        with (
            patch.object(experimento, "treinar", wraps=treinar) as ajuste,
            self.assertRaisesRegex(ValueError, "IDs disjuntos do protocolo"),
        ):
            self.processar()
        ajuste.assert_not_called()


class TestPublicacaoExperimento(unittest.TestCase):
    def setUp(self):
        self.area_temporaria = (RAIZ / "tmp").resolve()
        self.area_temporaria.mkdir(exist_ok=True)
        self.temporaria = tempfile.TemporaryDirectory(
            prefix="teste-experimento-", dir=self.area_temporaria)
        self.raiz_temporaria = Path(self.temporaria.name).resolve()
        self.assertTrue(
            self.raiz_temporaria.is_relative_to(self.area_temporaria))
        self.assertNotEqual(self.raiz_temporaria, self.area_temporaria)
        self.saida = self.raiz_temporaria / "saida"
        self.produtos = {
            "protocolo.json": b'{"sintetico": true}\n',
            "sugestoes.jsonl": b'{"id": "TESTE"}\n',
        }

    def tearDown(self):
        # A exclusão recursiva só pode atingir a pasta temporária deste teste.
        destino = self.raiz_temporaria.resolve()
        if (not destino.is_relative_to(self.area_temporaria)
                or destino == self.area_temporaria):
            raise AssertionError("Limpeza fora da pasta temporária permitida.")
        self.temporaria.cleanup()

    def test_publicacao_idempotente_sem_residuos_transitorios(self):
        experimento.publicar_produtos(self.saida, self.produtos)
        antes = {p.name: p.read_bytes() for p in self.saida.iterdir()}
        experimento.publicar_produtos(self.saida, self.produtos)
        depois = {p.name: p.read_bytes() for p in self.saida.iterdir()}
        self.assertEqual(antes, self.produtos)
        self.assertEqual(depois, antes)
        self.assertEqual(list(self.saida.glob(".produto-*.tmp")), [])

    def test_divergencia_preservada_sem_publicacao_parcial(self):
        self.saida.mkdir()
        divergente = self.saida / "protocolo.json"
        divergente.write_bytes(b"conteudo existente divergente\n")
        with self.assertRaisesRegex(ValueError, "Produto divergente"):
            experimento.publicar_produtos(self.saida, self.produtos)
        self.assertEqual(divergente.read_bytes(), b"conteudo existente divergente\n")
        self.assertFalse((self.saida / "sugestoes.jsonl").exists())
        self.assertEqual(list(self.saida.glob(".produto-*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
