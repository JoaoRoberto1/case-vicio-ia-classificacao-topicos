# Ponto de retomada do case

Primeiro bloco do módulo 4 de 16/10/2026 concluído. Foram feitas vinte novas chamadas, com quinze sucessos e cinco falhas HTTP 503 superadas nas retomadas. Não restam falhas técnicas pendentes entre as questões já processadas. O trabalho está no ponto de revisão e commit do usuário; não há execução de API em andamento. O próximo bloco, quando autorizado, continuará limitado a vinte novas chamadas no total, incluindo eventuais retomadas após falhas. Ao concluir cada bloco ou módulo, apresentar o resultado e parar para revisão e commit antes de seguir.

## Estado salvo

| Parte | Estado |
| --- | --- |
| Módulo 1: dados e árvore | Concluído: 359 questões preparadas, 377 temas validados, 375 ativos |
| Módulo 2: protocolo | Definido: política v1, referências por IA, censo do desenvolvimento e amostra de até 80 demais publicados |
| Módulo 3: integração e pilotos | Concluído: dois pilotos de vinte casos, prompt v2 selecionado |
| Módulo 4: lote completo | 162 respostas tecnicamente válidas, nenhuma falha técnica atual pendente e 197 IDs sem recibo |
| Módulo 5: decisão e avaliação | Funções e testes offline prontos; integração CLI e aplicação aos resultados reais pendentes |
| Módulo 6: relatório e memo | Pendente |
| Módulo 7: entrega final e reprodução | Pendente; esta pausa valida a base, não conclui a entrega |

O lote está em `artefatos/execucoes/lote-v2-35-flash-lite/`. São 161 recibos com sucesso e a recuperação offline anterior de Q0005, totalizando 162 sugestões válidas. Os vinte sucessos do piloto v2 estão incluídos, pois foram reutilizados sem novas chamadas. O novo bloco processou Q0135, Q0136, Q0138 a Q0141 e Q0143 a Q0151; Q0137 e Q0142 já vinham do piloto. Todos esses quinze IDs terminaram com respostas válidas. A recuperação de Q0005 em `Q0005.revalidacao.json` continua válida; o recibo original conserva o status histórico de erro, as quatro tentativas e todo o consumo. A recuperação técnica não representa uma decisão de publicação.

Houve cinco falhas HTTP 503 por alta demanda do provedor: duas em Q0135 e uma em cada Q0145, Q0149 e Q0151. As retomadas após espera recuperaram todos esses IDs, preservando as tentativas anteriores. Os limites das seis invocações foram 20, 19, 18, 9, 4 e 1; elas consumiram, respectivamente, 1, 1, 9, 5, 3 e 1 chamadas, totalizando vinte. A próxima execução começará nos IDs sem recibo, a partir de Q0152, reutilizando os sucessos existentes.

O [checkpoint atual](../artefatos/checkpoints/bloco_2026-10-16_01.json) guarda IDs por estado, hashes dos recibos e da revalidação, além do consumo registrado. São 177 tentativas nessa pasta, incluindo histórico, com 5.093.357 tokens totais informados. O bloco de 16/10 acrescentou 451.328 tokens conhecidos nas quinze respostas válidas; as cinco falhas HTTP 503 não informaram uso. Somadas às três falhas anteriores sem metadados, são oito tentativas com consumo desconhecido, que não é tratado como zero. Não somar novamente o piloto v2 ao contabilizar todo o projeto. Os checkpoints dos blocos [cinco](../artefatos/checkpoints/bloco_2026-10-15_05.json), [quatro](../artefatos/checkpoints/bloco_2026-10-15_04.json), [três](../artefatos/checkpoints/bloco_2026-10-15_03.json), [dois](../artefatos/checkpoints/bloco_2026-10-15_02.json) e [um de 15/10](../artefatos/checkpoints/bloco_2026-10-15_01.json), além da [pausa de 14/10](../artefatos/checkpoints/pausa_2026-10-14.json), permanecem preservados. A interrupção de 14/10 pode ter ocorrido após o envio de uma chamada ainda sem recibo; eventual consumo não registrado também permanece desconhecido.

A execução terminou pelo limite agregado de vinte chamadas. A última invocação retornou código zero; não houve falha local de validação, e nenhum erro de API ficou pendente. Os quinze sucessos do bloco estão salvos, sem lock residual. Nenhum processo de API foi deixado rodando para concluir o restante do lote.

## Verificações do bloco de 16 de outubro

- `python -B -m unittest discover -s tests -q`: 213 testes, 212 aprovados e um pulado por falta de privilégio do Windows para criar link simbólico real. A proteção também possui teste simulado aprovado.
- Todos os recibos presentes tiveram identidade do experimento, checksum e histórico conferidos. As sugestões válidas passaram pelo esquema, IDs ativos e correspondência de evidência. A revalidação confere novamente a origem e a seleção da primeira tentativa tecnicamente válida.
- Os 147 recibos anteriores e a revalidação de Q0005 permaneceram byte a byte idênticos. As novas tentativas e os erros de API estão preservados nos quinze recibos acrescentados. Código, modelo, prompt, política e regras de validação permaneceram iguais.
- Hashes das fontes originais conferidos; os materiais fornecidos permanecem intactos.
- Em 14/10, preparação e prompts dos pilotos v1, v2 e lote v2 foram reconstruídos em pasta temporária, com hashes idênticos aos produtos existentes. Na retomada, os hashes das fontes e manifestos foram reconferidos.
- `.env` e `contexto_local/` continuam ignorados pelo Git. A busca por padrão de chave Google nos artefatos do bloco não encontrou credencial.
- `.gitattributes` marca os materiais e artefatos assinados para preservar bytes. Foi identificada uma divergência preexistente de fins de linha entre o blob de `temas.csv` no Git e a fonte local; a correção para o próximo commit está abaixo.
- `git diff --check` sem erros de espaços. Nenhum commit ou push realizado pelo assistente.

## Ajuste de reprodução a incluir neste commit

O `temas.csv` local usa CRLF e coincide exatamente com o hash do manifesto (`9c6e98a6cd568816671c0fa14e2449b152cee10e20cb1327b3b097c1c5ce4cbc`). O blob no HEAD usa LF (`260c1826a6604a64ce26be0883ddc63e2ba768f1e55dcf88f323db42be36325c`). O texto é idêntico; apenas os fins de linha diferem. Essa diferença anterior a este bloco não afeta a execução local, mas precisa ser corrigida antes de reproduzir os hashes em outro checkout.

O comando `git add --renormalize -- temas.csv`, com o atributo atual `-text`, prepara no índice os bytes exatos da fonte local. Ele foi comprovado em índice e armazenamento de objetos temporários, fora do repositório. A fonte e o índice real permaneceram intactos; o comando ainda deve ser executado pelo usuário junto ao commit abaixo. Após executá-lo, `git ls-files --eol temas.csv` deve mostrar `i/crlf w/crlf attr/-text`. A comparação ignorando fins de linha não deve mostrar mudança textual.

## Commit deste checkpoint

A base anterior já estava commitada e o repositório estava limpo no início desta retomada, em `b5b2cb2`. Este novo commit reúne quinze novos recibos, o checkpoint, a documentação de progresso e o ajuste dos bytes de `temas.csv` no Git descrito acima. O lote permanece incompleto e a retomada reutiliza todos os sucessos, inclusive Q0005 revalidada; a avaliação real ainda não foi executada.

Comandos sugeridos para o usuário, a partir da raiz:

```powershell
git status --short
git add --renormalize -- temas.csv
git ls-files --eol temas.csv
git diff --cached --ignore-space-at-eol -- temas.csv
git add README.md docs/RETOMADA.md docs/PLANO_EXECUCAO.md artefatos/checkpoints/bloco_2026-10-16_01.json artefatos/experimentos/lote-v2-35-flash-lite.json artefatos/execucoes/lote-v2-35-flash-lite
git diff --cached --stat
git diff --cached --name-only
git commit -m "data: registra 162 respostas validas e preserva bytes da taxonomia"
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
