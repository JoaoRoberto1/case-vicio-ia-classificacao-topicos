# Ponto de retomada do case

Quinto bloco do módulo 4 concluído em 15/10/2026. Foram feitas vinte novas chamadas, todas válidas, incluindo Q0103 e Q0104 aceitas na segunda tentativa. Não restam falhas técnicas pendentes entre as questões já processadas. O trabalho está no ponto de revisão e commit do usuário; não há execução de API em andamento. O próximo bloco, quando autorizado, continuará limitado a vinte novas chamadas no total, incluindo eventuais retomadas após falhas. Ao concluir cada bloco ou módulo, apresentar o resultado e parar para revisão e commit antes de seguir.

## Estado salvo

| Parte | Estado |
| --- | --- |
| Módulo 1: dados e árvore | Concluído: 359 questões preparadas, 377 temas validados, 375 ativos |
| Módulo 2: protocolo | Definido: política v1, referências por IA, censo do desenvolvimento e amostra de até 80 demais publicados |
| Módulo 3: integração e pilotos | Concluído: dois pilotos de vinte casos, prompt v2 selecionado |
| Módulo 4: lote completo | 147 respostas tecnicamente válidas, nenhuma falha técnica atual pendente e 212 IDs sem recibo |
| Módulo 5: decisão e avaliação | Funções e testes offline prontos; integração CLI e aplicação aos resultados reais pendentes |
| Módulo 6: relatório e memo | Pendente |
| Módulo 7: entrega final e reprodução | Pendente; esta pausa valida a base, não conclui a entrega |

O lote está em `artefatos/execucoes/lote-v2-35-flash-lite/`. São 146 recibos com sucesso e a recuperação offline anterior de Q0005, totalizando 147 sugestões válidas. Os vinte sucessos do piloto v2 estão incluídos, pois foram reutilizados sem novas chamadas. O novo bloco repetiu Q0103 e Q0104 e processou Q0117 a Q0134. Todas as vinte respostas passaram. Q0103 e Q0104 foram aceitas na segunda tentativa, preservando integralmente as primeiras no histórico. A recuperação de Q0005 em `Q0005.revalidacao.json` continua válida; o recibo original conserva o status histórico de erro, as quatro tentativas e todo o consumo. A recuperação técnica não representa uma decisão de publicação.

As falhas anteriores de Q0103 (evidência descontínua) e Q0104 (ID repetido entre extras e alternativas) foram superadas por novas respostas da API, sem edição manual ou alteração dos validadores. O histórico e o consumo das tentativas rejeitadas continuam contabilizados. A próxima execução começará nos IDs sem recibo, a partir de Q0135, reutilizando os sucessos existentes.

O [checkpoint atual](../artefatos/checkpoints/bloco_2026-10-15_05.json) guarda IDs por estado, hashes dos recibos e da revalidação, além do consumo registrado. São 157 tentativas nessa pasta, incluindo histórico, com 4.642.029 tokens totais informados. O quinto bloco acrescentou 606.116 tokens nas vinte respostas, incluindo as novas tentativas de Q0103 e Q0104. As três falhas HTTP 503 do segundo bloco não informaram consumo e não são tratadas como consumo zero. Não somar novamente o piloto v2 ao contabilizar todo o projeto. Os checkpoints do [quarto bloco](../artefatos/checkpoints/bloco_2026-10-15_04.json), do [terceiro bloco](../artefatos/checkpoints/bloco_2026-10-15_03.json), do [segundo bloco](../artefatos/checkpoints/bloco_2026-10-15_02.json), do [primeiro bloco de 15/10](../artefatos/checkpoints/bloco_2026-10-15_01.json) e da [pausa de 14/10](../artefatos/checkpoints/pausa_2026-10-14.json) permanecem preservados. A interrupção de 14/10 pode ter ocorrido após o envio de uma chamada ainda sem recibo; eventual consumo não registrado também permanece desconhecido.

A execução terminou pelo limite de vinte chamadas em uma única invocação, com código de saída zero, sem erro da API, falha local de validação ou lock residual. Os vinte sucessos do bloco estão salvos. Nenhum processo de API foi deixado rodando para concluir o restante do lote.

## Verificações do quinto bloco de 15 de outubro

- `python -B -m unittest discover -s tests -q`: 213 testes, 212 aprovados e um pulado por falta de privilégio do Windows para criar link simbólico real. A proteção também possui teste simulado aprovado.
- Todos os recibos presentes tiveram identidade do experimento, checksum e histórico conferidos. As sugestões válidas passaram pelo esquema, IDs ativos e correspondência de evidência. A revalidação confere novamente a origem e a seleção da primeira tentativa tecnicamente válida.
- Dos 129 recibos anteriores, 127 permaneceram byte a byte idênticos. Q0103 e Q0104 receberam a segunda tentativa e preservaram os objetos completos das primeiras no histórico, inclusive checksum e consumo. A revalidação de Q0005 permanece byte a byte idêntica. Código, modelo, prompt, política e regras de validação permaneceram iguais.
- Hashes das fontes originais conferidos; os materiais fornecidos permanecem intactos.
- Em 14/10, preparação e prompts dos pilotos v1, v2 e lote v2 foram reconstruídos em pasta temporária, com hashes idênticos aos produtos existentes. Na retomada, os hashes das fontes e manifestos foram reconferidos.
- `.env` e `contexto_local/` continuam ignorados pelo Git. A busca por padrão de chave Google nos artefatos do bloco não encontrou credencial.
- `.gitattributes` impede conversão de fim de linha dos materiais e artefatos assinados, preservando hashes em checkouts Windows.
- `git diff --check` sem erros de espaços. Nenhum commit ou push realizado pelo assistente.

## Commit deste checkpoint

A base anterior já estava commitada e o repositório estava limpo no início desta retomada, em `d902476`. Este novo commit reúne dezoito novos recibos, as segundas tentativas de Q0103 e Q0104, o checkpoint e a documentação de progresso. O lote permanece incompleto e a retomada reutiliza todos os sucessos, inclusive Q0005 revalidada; a avaliação real ainda não foi executada.

Comandos sugeridos para o usuário, a partir da raiz:

```powershell
git status --short
git add README.md docs/RETOMADA.md docs/PLANO_EXECUCAO.md artefatos/checkpoints/bloco_2026-10-15_05.json artefatos/experimentos/lote-v2-35-flash-lite.json artefatos/execucoes/lote-v2-35-flash-lite
git diff --cached --stat
git diff --cached --name-only
git commit -m "data: registra bloco do lote com 147 respostas validas"
```

Os arquivos grandes `artefatos/piloto/entradas.jsonl`, `artefatos/piloto-v2/entradas.jsonl` e `artefatos/lote-v2/entradas.jsonl` permanecem no computador, mas são ignorados: repetem o catálogo e são regeneráveis. Templates, manifestos, fontes, recibos e análises são versionáveis. Não usar `git add -f` para incluir `.env`, contexto privado ou prompts expandidos.

## Retomada na mesma pasta

Primeiro, ler este registro e conferir `git status --short`. O usuário dispõe de vinte horas estimadas para o projeto; essa previsão não é uma medição automática de tempo já gasto. Não iniciar o lote inteiro nem alterar a política sem avaliar o impacto no protocolo.

Rodar os testes offline. Só quando o usuário retomar o trabalho, executar um bloco:

```powershell
python -B -m unittest discover -s tests -v
$env:GEMINI_MODEL = 'gemini-3.5-flash-lite'
python -B -m classificacao_topicos executar-lote --lote artefatos/lote-v2 --saida artefatos/execucoes/lote-v2-35-flash-lite --limite 20 --intervalo-segundos 10 --continuar-erros-validacao
```

A variável vale para o terminal e prevalece sobre o modelo do `.env`, que não foi editado. A chave permanece local. As cotas informadas para esse modelo eram 15 RPM, 250 mil TPM e 500 RPD; conferir disponibilidade e uso do dia ao retomar. Não ativar faturamento nem usar alternativa paga.

O comando pula sucessos, tenta pendências e limita as novas chamadas. Uma falha local fica salva e os demais IDs avançam; erro da API interrompe. O código de saída pode ser 1 por pendências de validação, mesmo com progresso salvo. Ao finalizar, conferir o resumo e parar para revisão/commit. Para pausas planejadas, aguardar o fim do bloco, evitando interrupções durante uma chamada.

## Retomada em outro checkout

Os prompts expandidos não estarão no Git. Reconstruí-los antes de executar ou validar recibos:

```powershell
python -B -m classificacao_topicos preparar
python -B -m classificacao_topicos preparar-piloto
python -B -m classificacao_topicos preparar-piloto --saida artefatos/piloto-v2 --prompt prompts/classificacao_v2.txt --versao-prompt classificacao-v2
python -B -m classificacao_topicos preparar-lote --piloto-desenvolvimento artefatos/piloto-v2 --saida artefatos/lote-v2 --prompt prompts/classificacao_v2.txt --versao-prompt classificacao-v2
```

Esses quatro comandos são offline. A chave deve ser configurada localmente conforme `CONFIGURACAO_API.md`. Não executar `verificar-api` repetidamente se a integração já estiver funcionando: cada teste sintético é uma chamada real.

## Próximos módulos após o lote

### Recuperação técnica de Q0005

A primeira resposta salva passa integralmente na validação atual, que já tolerava caixa e espaços. A revalidação foi implementada como arquivo adjacente `Q0005.revalidacao.json`; o recibo original, suas quatro tentativas e seus 122.031 tokens permanecem intactos. Não houve escolha manual de tema, relaxamento adicional de evidência ou chamada de API para a recuperação.

```powershell
python -B -m classificacao_topicos revalidar-recibo --lote artefatos/lote-v2 --execucao artefatos/execucoes/lote-v2-35-flash-lite --id Q0005
```

O comando é offline e idempotente quando o derivado existente é válido. O executor e o módulo de decisões validam o derivado e usam a sugestão recuperada; o histórico original continua sendo a fonte exclusiva do consumo. Um derivado adulterado ou incompatível interrompe o processamento. Não editar o status do recibo original para fazê-lo parecer uma nova resposta bem-sucedida.

Ao conferir o lote por scripts, selecionar recibos por `Q[0-9]{4}\.json`, pois `Q*.json` inclui também os derivados. Manter separados o status original do recibo e o status efetivo após revalidação. A função `carregar_revalidacao` verifica a origem e a seleção antes do uso de `status_efetivo` ou `sugestao_efetiva`.

### Entregas restantes

1. Resolver pendências técnicas até obter 359 sugestões válidas. Não inventar tema para contornar erro, nem aceitar paráfrase como evidência literal.
2. Integrar à CLI as funções já prontas: `decisoes.preparar_decisoes`, `auditoria.preparar_auditoria` e `avaliacao.avaliar_auditoria`. Suas interfaces e contratos estão nos módulos e testes. Hoje não existem comandos CLI correspondentes.
3. Aplicar `config/politica_v1.json`. Confirmar separadamente os candidatos sem tema antes de gerar `publicacao.csv`; os demais candidatos pendentes impedem uma exportação oficial incompleta.
4. Congelar as decisões e sortear o pacote cego: censo dos publicados entre vinte casos de desenvolvimento; amostra sem reposição de `min(80,N)` demais publicados, semente `2026101401`.
5. Produzir referências de IA sem acesso às respostas Gemini e calcular cenários conservador/otimista com intervalos condicionais à referência. Não transformar concordância entre IAs em precisão jurídica validada.
6. Preencher `previsao.txt`, produzir relatório de até cinco páginas com memo de uma página e proposta para 50 mil questões/semana, e validar a entrega. Não publicar repositório nem enviar materiais sem instrução do usuário.

## Decisões que devem ser preservadas

O usuário não tem apoio jurídico disponível. Não há gabarito oficial. O limiar 0,95 é operacional e a confiança é autodeclarada, não calibrada. A política foi registrada antes de inspecionar as novas classificações do lote; não ajustá-la sobre a própria amostra e depois chamar a mesma avaliação de independente.

Na avaliação local, igualdade de ID ou relação imediata pai/filho é aceita; irmãos e ancestrais distantes permanecem distintos. É uma interpretação conservadora explicitada do texto do case. A confiança de `fora` será zero como sentinela de não aplicável; a cobertura do lote terá intervalo degenerado porque é contagem observada. Essas convenções estão em `AVALIACAO.md`.

Para retomar a conversa, basta: **“Leia docs/RETOMADA.md e continue somente o próximo bloco do módulo 4; pare ao concluir para eu revisar e commitar.”**
