# Pausa segura do módulo 8

Pausa solicitada por João Roberto em 21/10/2026. **Não continuar automaticamente.** Retomar somente quando o usuário pedir.

## Estado preservado

- Módulos 1 a 7 e seus hashes preservados. Nenhuma entrega antiga foi substituída.
- Grade M8 e fontes da decisão congeladas; comparação com E5-small concluída em `artefatos/precisao-m8-small-v1`.
- Resultado parcial: M7 preservado 54/80 por ramo; small com sinais 53/80; small com sinais e hierarquia 54/80. Nenhuma política elegível para publicação.
- Confiança externa parcial: Brier 0,189694 contra 0,225916 da constante. Melhor grupo exploratório com suporte mínimo: 16/17 = 94,12%; não atinge 95%.
- Suíte completa: 482 testes aprovados, em 168,233 segundos. Isso verifica software, não precisão nas 559 questões.
- Preparação E5-large interrompida; **594/1.030 vetores de questões salvos e autenticados** em `.cache-modelos/e5-large/checkpoint-completo`. Faltam 65 questões e 371 temas. Nenhum processo de geração permanece ativo, nem há arquivo temporário ou registro órfão.
- Pesos, ambiente virtual, checkpoints transitórios e prévias de PDF permanecem fora do Git. Não apagá-los: são necessários à retomada local.
- Nenhum commit, push ou envio externo realizado nesta rodada.

O registro estruturado da pausa fica em [pausa_modulo8.json](../artefatos/checkpoints/pausa_modulo8.json). Ele não é um checkpoint de conclusão nem autoriza publicar a entrega.

## Arquivos novos

`classificacao_precisao/` contém motor, sinais, confiança, preparação e exportação. `config/modulo8/` registra a grade, as âncoras e o encoder. Os scripts novos geram a entrega, o diagnóstico estrutural, o benchmark, a reprodução isolada e o relatório. O [registro M8](MODULO8_PRECISAO.md) descreve métodos e resultado parcial.

`entrega-final-v2/` está **incompleta**. Contém roteiro provisório de defesa; ainda não possui CSV, previsão ou PDF finais. As prévias de diagramação em `tmp/pdfs` usam números fictícios, estão identificadas como rascunho e não podem ser entregues.

`README_HISTORICO.md`, na raiz do repositório, preserva o README anterior. Ao finalizar, reescrever o README principal para apontar diretamente à nova entrega. Não mover ou substituir os CSVs/relatórios antigos: os verificadores históricos dependem deles. Não editar README/documentos M5 dentro da etapa, pois estão congelados por hashes.

## Antes de retomar a preparação

1. Confirmar que nenhum processo de preparação está ativo. Não iniciar duas instâncias.
2. **Resolver primeiro a divergência de procedência do protocolo. O comando de retomada está bloqueado por essa verificação.** O índice guarda `config/modulo8/protocolo.json` com SHA `dd178b70592028c3c03351a6d6f478d3a91b04dc4a91cdcfde810115ecf88e99`, enquanto o arquivo atual tem SHA `4ac9d655cf825b98bfc5b2151466e618637fd7d906deeaf0de6e3cd5730ba115`. Entradas, configuração do encoder e todas as outras fontes permanecem idênticas. O protocolo não participa da geração dos vetores; ainda assim, não ignorar a proteção nem sobrescrever a procedência silenciosamente. Antes de uma eventual migração exclusivamente de metadados, preservar o índice original, registrar os dois hashes e a justificativa, verificar novamente entradas e os 594 registros e manter seus bytes intactos. O índice original tem SHA `507d36b0f1ff93a1db64abfaf3f845be508abd7331624208023ee281aa1d6cad`. Nenhuma migração foi feita durante a pausa. **Não alterar `preparar_large.py`, `embeddings_large.json` nem as demais fontes assinadas antes de concluir essa análise.**
3. Corrigir ou esclarecer a procedência histórica do primeiro piloto: o snapshot em `artefatos/embeddings-e5-large-m8/piloto/fontes` foi identificado como divergente do manifesto original. Não apresentá-lo como reprodução válida. Fonte/configuração atuais e segundo piloto `piloto_memoria` são a referência da execução em andamento. Não adulterar manifestos antigos para fazer os hashes coincidirem.
4. Manter memória livre. O script verifica RAM e comprometimento, e interrompe se ultrapassar as guardas; não encerra aplicativos nem altera o sistema.

Somente depois de resolver e documentar os pontos de procedência acima, na pasta `etapa-complementar`:

```console
.venv/Scripts/python.exe -E -X utf8 -B -m classificacao_precisao.preparar_large preparar
```

Com a identidade validada, o comando reaproveita os registros autenticados e gera somente os faltantes. A meta do cache completo é 659 questões + 371 temas = 1.030 registros, com 1.053 janelas. Só ao concluir são gravados `vetores.json`, `manifesto.json` e a evidência da execução na raiz de `artefatos/embeddings-e5-large-m8`.

## Pendências materiais da apresentação

- `DEFESA_TECNICA.md` ainda descreve ranking supervisionado e reajuste nas 100 referências de maneira incondicional. Se vencer `large_rrf20`, o ranking é fixo; rótulos servem à seleção e confiança. Nessa receita, sinais específicos alimentam confiança/política, sem mudar a fusão RRF.
- As receitas Large da implementação atual também calculam atributos Small. Para questões novas, a projeção de preparação deve incluir ambos os encoders; contar somente Large subestima custo.
- **Após esta pausa haverá reutilização de checkpoints.** `execucao.json` medirá a execução de retomada, não todo o trabalho desde o início. Não dividir esse tempo pelo total de 1.030 e apresentá-lo como custo integral. Registrar as execuções separadas ou qualificar a estimativa como parcial; não inventar tempo acumulado. Corrigir `gerar_relatorio_precisao.py` antes de gerar o relatório final.
- A diagramação provisória coube em quatro páginas. O gerador recebeu correção de espaçamento depois da prévia; renderizar e inspecionar novamente o PDF final, com números reais.

## Ordem para concluir depois

1. Finalizar e validar cache Large e sua procedência, sem consultar temas/rótulos de questões via LLM.
2. Executar `python -E -X utf8 -B -S scripts/entregar_precisao.py`. Ele compara a grade completa, só depois diagnostica as 20 já conhecidas e gera as 559 sugestões finais. A grade não deve ser alterada para favorecer o resultado observado.
3. Gerar diagnóstico com `python -E -X utf8 -B -S scripts/diagnosticar_precisao.py`.
4. Medir a aplicação das 559 sugestões com `python -E -X utf8 -B -S scripts/medir_precisao.py --evidencia artefatos/checkpoints/benchmark_modulo8.json`.
5. Corrigir os pontos editoriais acima, gerar o relatório com `../.venv/Scripts/python.exe -E -X utf8 -B scripts/gerar_relatorio_precisao.py`, renderizar suas quatro páginas e conferir nome, texto, números e layout.
6. Atualizar README principal, README final, defesa e registro M8 com os resultados efetivos. Não chamar as 20 referências de novo teste independente; não confundir acerto global com precisão de publicação.
7. Reproduzir em cópia permitida: `python -E -X utf8 -B -S scripts/verificar_precisao.py`. Isso recompõe o experimento e as três entregas sem rede, credenciais ou encoder. Destinos de evidência não podem existir previamente.
8. Conferir arquivos/hashes, links e Git; criar checkpoint M8 de conclusão somente após terminar as etapas anteriores. Commit/push permanecem com o usuário, salvo nova instrução explícita.

O marcador de operação PDF da habilidade já foi executado com sucesso nesta conversa. Não repeti-lo como se uma nova operação tivesse começado; ainda falta criar o PDF final, e só prévias temporárias foram produzidas.

## Restrições mantidas

Nenhum LLM pode escolher, votar, julgar ou validar temas das questões avaliadas. Processamento numérico dos rótulos humanos e métricas agregadas é permitido; não expor questões com rótulos/predições para adjudicação semântica. Preparação do catálogo e embeddings ocorre antes da decisão, documentada e versionada. As 100 referências já foram reutilizadas: não há novo teste independente nem garantia de precisão populacional. Não prometer perfeição ou contratação.
