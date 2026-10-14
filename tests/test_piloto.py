"""Testes offline do piloto: seleção, integridade, isolamento e contrato técnico."""

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from classificacao_topicos.piloto import esquema_resposta, preparar_piloto, validar_resposta
from classificacao_topicos.preparacao import executar_preparacao


RAIZ = Path(__file__).resolve().parents[1]
DELIBERADOS = ["Q0020", "Q0036", "Q0078", "Q0099", "Q0107", "Q0137", "Q0142", "Q0219", "Q0239", "Q0284"]


def gravar_preparacao(pasta: Path) -> None:
    pasta.mkdir(parents=True)
    questoes = []
    for indice, identificador in enumerate(DELIBERADOS + [f"Q9{i:03d}" for i in range(20)]):
        questoes.append({
            "id": identificador, "enunciado": "Enunciado integral com ${ESQUEMA_JSON} como dado.",
            "comando": "Comando substantivo.",
            "alternativas": {str(n): f"Alternativa {n}." for n in range(2 if indice % 2 else 5)},
            "disciplina_origem": f"Origem somente seleção {indice % 4}",
            "assunto_origem": "RÓTULO HISTÓRICO NÃO É REFERÊNCIA",
        })
    temas = [
        {"tema_id": "T0", "parent_id": "", "nivel": "0", "titulo": "Raiz", "caminho": "Raiz", "descricao": "Disciplina (root). quantidade histórica 123", "status": "active"},
        {"tema_id": "T1", "parent_id": "T0", "nivel": "1", "titulo": "Mesmo título", "caminho": "Raiz > Ramo A > Mesmo título", "descricao": "Conhecimento substantivo sobre A.", "status": "active"},
        {"tema_id": "T2", "parent_id": "T0", "nivel": "1", "titulo": "Mesmo título", "caminho": "Raiz > Ramo B > Mesmo título", "descricao": "Subtema de Raiz. metadado histórico 456", "status": "active"},
        {"tema_id": "T3", "parent_id": "T0", "nivel": "1", "titulo": "Inativo", "caminho": "Raiz > Inativo", "descricao": "Não entra.", "status": "inactive"},
    ]
    produtos = {
        "questoes_preparadas.jsonl": "".join(json.dumps(q, ensure_ascii=False) + "\n" for q in questoes).encode("utf-8"),
        "temas_preparados.json": json.dumps(temas, ensure_ascii=False).encode("utf-8"),
        "diagnostico.json": b'{"total":30}\n',
    }
    for nome, conteudo in produtos.items():
        (pasta / nome).write_bytes(conteudo)
    manifesto = {
        "schema_version": 1, "procedimento": "preparacao-v1",
        "produtos_sha256": {nome: hashlib.sha256(conteudo).hexdigest() for nome, conteudo in produtos.items()},
    }
    (pasta / "manifesto.json").write_text(json.dumps(manifesto), encoding="utf-8")


class PrepararPilotoTest(unittest.TestCase):
    def setUp(self):
        self.temporaria = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporaria.cleanup)
        self.pasta = Path(self.temporaria.name)
        self.preparacao = self.pasta / "preparacao"
        self.saida = self.pasta / "piloto"
        gravar_preparacao(self.preparacao)

    def test_selecao_reproduzivel_inclui_deliberados_e_diversifica(self):
        manifesto = preparar_piloto(self.preparacao, self.saida)
        primeira = {p.name: p.read_bytes() for p in self.saida.iterdir()}
        repetido = preparar_piloto(self.preparacao, self.saida)
        self.assertEqual(primeira, {p.name: p.read_bytes() for p in self.saida.iterdir()})
        self.assertEqual(manifesto, repetido)
        self.assertEqual(manifesto["ids"][:10], DELIBERADOS)
        self.assertEqual(len(set(manifesto["ids"])), 20)
        self.assertEqual(len(manifesto["restante_ids"]), 10)
        self.assertFalse(set(manifesto["ids"]) & set(manifesto["restante_ids"]))
        self.assertIn("não auditoria", manifesto["data_exposure"])
        self.assertIn("não são dados nunca vistos", manifesto["restante_uso"])
        registros = [json.loads(linha) for linha in (self.preparacao / "questoes_preparadas.jsonl").read_text(encoding="utf-8").splitlines()]
        selecionados = [q for q in registros if q["id"] in manifesto["ids"]]
        self.assertEqual(len({q["disciplina_origem"] for q in selecionados}), 4)
        self.assertEqual({len(q["alternativas"]) for q in selecionados}, {2, 5})
        outro = preparar_piloto(self.preparacao, self.pasta / "outro", semente=1)
        self.assertNotEqual(manifesto["ids"][10:], outro["ids"][10:])

    def test_prompt_completo_sem_origem_e_sem_fundir_titulos_iguais(self):
        manifesto = preparar_piloto(self.preparacao, self.saida)
        entradas = [json.loads(linha) for linha in (self.saida / "entradas.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(entradas), 20)
        for entrada in entradas:
            prompt = entrada["prompt"]
            self.assertIn("Enunciado integral com ${ESQUEMA_JSON} como dado.", prompt)
            self.assertIn("Comando substantivo.", prompt)
            self.assertIn("Alternativa 0.", prompt)
            self.assertNotIn("Origem somente seleção", prompt)
            self.assertNotIn("RÓTULO HISTÓRICO", prompt)
            self.assertIn('"id": "T1"', prompt)
            self.assertIn('"id": "T2"', prompt)
            self.assertNotIn('"id": "T3"', prompt)
            self.assertIn("Conhecimento substantivo sobre A.", prompt)
            self.assertNotIn("quantidade histórica 123", prompt)
            self.assertNotIn("metadado histórico 456", prompt)
            self.assertEqual(entrada["sha256_prompt"], hashlib.sha256(prompt.encode("utf-8")).hexdigest())
        self.assertEqual(manifesto["total_temas_ativos_no_prompt"], 3)
        self.assertEqual(manifesto["descricoes_metadados_omitidas_ids"], ["T0", "T2"])
        self.assertEqual(manifesto["produtos_sha256"]["entradas.jsonl"], hashlib.sha256((self.saida / "entradas.jsonl").read_bytes()).hexdigest())
        self.assertEqual(manifesto["preparacao_sha256"], hashlib.sha256((self.preparacao / "manifesto.json").read_bytes()).hexdigest())
        self.assertEqual(manifesto["prompt_sha256"], hashlib.sha256((RAIZ / "prompts" / "classificacao_v1.txt").read_bytes()).hexdigest())

    def test_valida_todos_os_hashes_inclusive_produto_nao_consumido(self):
        (self.preparacao / "diagnostico.json").write_text("alterado", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Hash divergente"):
            preparar_piloto(self.preparacao, self.saida)
        self.assertFalse(self.saida.exists())

    def test_template_customizado_registra_versao_hash_e_preserva_padrao(self):
        padrao = preparar_piloto(self.preparacao, self.saida, 20, 20261014)
        produtos_antes = {p.name: p.read_bytes() for p in self.saida.iterdir()}
        caminho_prompt = self.pasta / "variante.txt"
        texto = "Variante para comparação.\n${ESQUEMA_JSON}\n${CATALOGO_JSONL}\n${QUESTAO_JSON}\n"
        caminho_prompt.write_bytes(texto.encode("utf-8"))
        saida_variante = self.pasta / "piloto_variante"
        variante = preparar_piloto(
            self.preparacao, saida_variante, prompt_path=caminho_prompt,
            prompt_version="classificacao-v2.teste_1",
        )
        self.assertEqual(variante["prompt_version"], "classificacao-v2.teste_1")
        self.assertEqual(variante["prompt_sha256"], hashlib.sha256(caminho_prompt.read_bytes()).hexdigest())
        self.assertNotEqual(variante["prompt_sha256"], padrao["prompt_sha256"])
        self.assertEqual(variante["ids"], padrao["ids"])
        self.assertEqual(produtos_antes, {p.name: p.read_bytes() for p in self.saida.iterdir()})
        entradas = [json.loads(linha) for linha in (saida_variante / "entradas.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertTrue(all(e["prompt"].startswith("Variante para comparação.") for e in entradas))
        repetido = preparar_piloto(self.preparacao, self.saida)
        self.assertEqual(repetido, padrao)
        self.assertEqual(padrao["prompt_version"], "classificacao-v1")

    def test_rejeita_versao_de_prompt_invalida_antes_de_gravar(self):
        for versao in ("", "com espaço", "../v2", "v2/v3", "v2\\v3", "v2\n", "á-v2", "v" * 81, None, True, 2):
            with self.subTest(versao=versao), self.assertRaisesRegex(ValueError, "Versão do prompt"):
                preparar_piloto(self.preparacao, self.saida, prompt_version=versao)
        self.assertFalse(self.saida.exists())

    def test_rejeita_template_sem_utf8_ou_sem_dados_obrigatorios(self):
        caminho_prompt = self.pasta / "variante.txt"
        caminho_prompt.write_bytes(b"\xff")
        with self.assertRaisesRegex(ValueError, "UTF-8"):
            preparar_piloto(self.preparacao, self.saida, prompt_path=caminho_prompt, prompt_version="v2")
        for texto in ("Sem marcadores", "${QUESTAO_JSON}", "${QUESTAO_JSON}\n${CATALOGO_JSONL}\n${ESQUEMA_JSON}\n${NAO_EXISTE}"):
            caminho_prompt.write_text(texto, encoding="utf-8")
            with self.subTest(texto=texto), self.assertRaisesRegex(ValueError, "marcadores"):
                preparar_piloto(self.preparacao, self.saida, prompt_path=caminho_prompt, prompt_version="v2")
        self.assertFalse(self.saida.exists())

    def test_rejeita_template_customizado_sinalizado_como_link(self):
        caminho_prompt = self.pasta / "variante.txt"
        caminho_prompt.write_text("${QUESTAO_JSON}\n${CATALOGO_JSONL}\n${ESQUEMA_JSON}", encoding="utf-8")
        original = Path.is_symlink
        with patch.object(Path, "is_symlink", lambda caminho: caminho == caminho_prompt or original(caminho)):
            with self.assertRaisesRegex(ValueError, "arquivo comum"):
                preparar_piloto(self.preparacao, self.saida, prompt_path=caminho_prompt, prompt_version="v2")
        self.assertFalse(self.saida.exists())

    def test_rejeita_manifesto_com_travessia_de_diretorio(self):
        caminho = self.preparacao / "manifesto.json"
        manifesto = json.loads(caminho.read_text(encoding="utf-8"))
        manifesto["produtos_sha256"]["../externo"] = "0" * 64
        caminho.write_text(json.dumps(manifesto), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "inseguro"):
            preparar_piloto(self.preparacao, self.saida)
        self.assertFalse(self.saida.exists())

    def test_rejeita_versao_de_manifesto_e_tamanho_invalidos(self):
        for tamanho in (0, -1, True, 31, 5):
            with self.subTest(tamanho=tamanho), self.assertRaises(ValueError):
                preparar_piloto(self.preparacao, self.saida, tamanho=tamanho)
        with self.assertRaisesRegex(ValueError, "semente"):
            preparar_piloto(self.preparacao, self.saida, semente=True)
        caminho = self.preparacao / "manifesto.json"
        manifesto = json.loads(caminho.read_text(encoding="utf-8"))
        manifesto["schema_version"] = True
        caminho.write_text(json.dumps(manifesto), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Versão"):
            preparar_piloto(self.preparacao, self.saida)

    def test_rejeita_destinos_protegidos_sem_escrever(self):
        for destino in (
            self.preparacao, self.preparacao / "piloto", self.pasta,
            self.pasta / ".git" / "piloto", self.pasta / "contexto_local" / "piloto",
            RAIZ, RAIZ / "prompts" / "piloto",
        ):
            with self.subTest(destino=destino), self.assertRaises(ValueError):
                preparar_piloto(self.preparacao, destino)

    def test_rejeita_produto_de_saida_que_e_diretorio(self):
        (self.saida / "entradas.jsonl").mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "arquivo comum"):
            preparar_piloto(self.preparacao, self.saida)
        self.assertFalse((self.saida / "manifesto_piloto.json").exists())

    def test_rejeita_links_simbolicos_de_entrada_e_saida(self):
        alvo = self.pasta / "alvo.txt"
        alvo.write_text("preservar", encoding="utf-8")
        self.saida.mkdir()
        link = self.saida / "entradas.jsonl"
        try:
            link.symlink_to(alvo)
        except OSError as erro:
            self.skipTest(f"Sistema não permite criar link simbólico neste teste: {erro}")
        with self.assertRaisesRegex(ValueError, "arquivo comum"):
            preparar_piloto(self.preparacao, self.saida)
        self.assertEqual(alvo.read_text(encoding="utf-8"), "preservar")
        link.unlink()
        produto = self.preparacao / "diagnostico.json"
        salvo = self.pasta / "diagnostico_original.json"
        produto.replace(salvo)
        produto.symlink_to(salvo)
        with self.assertRaisesRegex(ValueError, "arquivo comum"):
            preparar_piloto(self.preparacao, self.saida)

    def test_rejeicao_de_links_e_verificada_mesmo_sem_privilegio_do_windows(self):
        original = Path.is_symlink
        for alvo in (
            self.preparacao / "manifesto.json", self.preparacao / "diagnostico.json",
            self.saida / "entradas.jsonl", self.saida / "manifesto_piloto.json",
        ):
            alvo = alvo.resolve()
            with self.subTest(alvo=alvo):
                with patch.object(Path, "is_symlink", lambda caminho: caminho == alvo or original(caminho)):
                    with self.assertRaisesRegex(ValueError, "arquivo comum"):
                        preparar_piloto(self.preparacao, self.saida)
                self.assertFalse(self.saida.exists())

    def test_lote_real_tem_20_entradas_e_todos_os_375_temas_ativos(self):
        preparacao_real = self.pasta / "preparacao_real"
        executar_preparacao(RAIZ, preparacao_real)
        manifesto = preparar_piloto(preparacao_real, self.saida)
        self.assertEqual(len(manifesto["ids"]), 20)
        self.assertEqual(len(manifesto["restante_ids"]), 339)
        self.assertEqual(manifesto["total_temas_ativos_no_prompt"], 375)
        entradas = [json.loads(linha) for linha in (self.saida / "entradas.jsonl").read_text(encoding="utf-8").splitlines()]
        temas = json.loads((preparacao_real / "temas_preparados.json").read_text(encoding="utf-8"))
        prompt = entradas[0]["prompt"]
        for tema in temas:
            marcador = '"id": ' + json.dumps(tema["tema_id"])
            if tema["status"] == "active":
                self.assertIn(marcador, prompt)
            else:
                self.assertNotIn(marcador, prompt)
        comando = next(json.loads(linha)["comando"] for linha in (preparacao_real / "questoes_preparadas.jsonl").read_text(encoding="utf-8").splitlines() if json.loads(linha)["id"] == "Q0107")
        entrada = next(e for e in entradas if e["id"] == "Q0107")
        self.assertIn(comando, entrada["prompt"])


class ValidarRespostaTest(unittest.TestCase):
    def setUp(self):
        self.temas = {"T1": {"status": "active"}, "T2": {"status": "active"}, "T3": {"status": "inactive"}}
        self.resposta = {
            "id": "Q0107", "tema_central_id": "T1", "extras_ids": [], "temas_alternativos": [],
            "sem_tema": False, "confianca_autodeclarada": 0.8,
            "motivo": "Tema sustentado pelo comando.", "evidencia": "crime de falsa identidade",
            "requer_revisao": False,
        }

    def test_resposta_valida_e_copia_sem_politica_de_publicacao(self):
        validada = validar_resposta(self.resposta, "Q0107", self.temas)
        self.assertEqual(validada, self.resposta)
        validada["extras_ids"].append("T2")
        self.assertEqual(self.resposta["extras_ids"], [])
        self.assertNotIn("decisao", validada)

    def test_esquema_exige_todos_os_campos_sem_enum_de_taxonomia(self):
        esquema = esquema_resposta()
        self.assertEqual(set(esquema["required"]), set(self.resposta))
        self.assertFalse(esquema["additionalProperties"])
        self.assertNotIn('"enum"', json.dumps(esquema))

    def test_rejeita_campos_ausentes_ou_extra_e_id_de_outra_questao(self):
        for mutacao in ({"id": "Q0001"}, {"publicar": True}):
            resposta = {**self.resposta, **mutacao}
            with self.subTest(mutacao=mutacao), self.assertRaises(ValueError):
                validar_resposta(resposta, "Q0107", self.temas)
        resposta = dict(self.resposta)
        del resposta["evidencia"]
        with self.assertRaises(ValueError):
            validar_resposta(resposta, "Q0107", self.temas)

    def test_rejeita_ids_inexistentes_inativos_ou_com_espacos_em_todas_as_listas(self):
        for invalido in ("T3", "inventado", " T1 "):
            for campo in ("tema_central_id", "extras_ids", "temas_alternativos"):
                resposta = copy.deepcopy(self.resposta)
                resposta[campo] = invalido if campo == "tema_central_id" else [invalido]
                with self.subTest(invalido=invalido, campo=campo), self.assertRaisesRegex(ValueError, "inexistente ou inativo"):
                    validar_resposta(resposta, "Q0107", self.temas)

    def test_rejeita_duplicatas_e_sobreposicao_de_papeis(self):
        for extras, alternativas in ((["T2", "T2"], []), (["T1"], []), ([], ["T1"]), (["T2"], ["T2"])):
            resposta = {**self.resposta, "extras_ids": extras, "temas_alternativos": alternativas}
            with self.subTest(extras=extras, alternativas=alternativas), self.assertRaises(ValueError):
                validar_resposta(resposta, "Q0107", self.temas)

    def test_booleanos_e_confianca_sao_estritos(self):
        for campo in ("sem_tema", "requer_revisao"):
            for valor in (0, 1, "true", None):
                with self.subTest(campo=campo, valor=valor), self.assertRaises(ValueError):
                    validar_resposta({**self.resposta, campo: valor}, "Q0107", self.temas)
        for valor in (True, False, float("nan"), float("inf"), -float("inf"), -0.1, 1.1, "0.8", 10 ** 1000):
            with self.subTest(valor=str(valor)[:20]), self.assertRaisesRegex(ValueError, "Confiança"):
                validar_resposta({**self.resposta, "confianca_autodeclarada": valor}, "Q0107", self.temas)

    def test_motivo_e_evidencia_nao_podem_ser_vazios(self):
        for campo in ("motivo", "evidencia"):
            for valor in ("", " \n ", None, 1):
                with self.subTest(campo=campo, valor=valor), self.assertRaises(ValueError):
                    validar_resposta({**self.resposta, campo: valor}, "Q0107", self.temas)

    def test_sem_tema_exige_central_e_extras_vazios(self):
        resposta = {**self.resposta, "sem_tema": True, "tema_central_id": "", "requer_revisao": True}
        self.assertEqual(validar_resposta(resposta, "Q0107", self.temas), resposta)
        for central, extras in (("T1", []), ("", ["T2"])):
            with self.subTest(central=central, extras=extras), self.assertRaisesRegex(ValueError, "sem_tema"):
                validar_resposta({**resposta, "tema_central_id": central, "extras_ids": extras}, "Q0107", self.temas)
        with self.assertRaisesRegex(ValueError, "tema_central_id"):
            validar_resposta({**self.resposta, "tema_central_id": ""}, "Q0107", self.temas)


if __name__ == "__main__":
    unittest.main()
