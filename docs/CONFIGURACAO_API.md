# Configuração da API para o piloto

Modelo usado: Gemini Developer API com `gemini-3.5-flash-lite`, no plano gratuito, sujeito às cotas do projeto. A tentativa inicial com `gemini-3.8-flash` encontrou indisponibilidade HTTP 503; o Flash-Lite funcionou no teste sintético e concluiu dois pilotos de vinte casos. Disponibilidade e condições foram consultadas em 14/10/2026. [Modelo](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite), [preços](https://ai.google.dev/gemini-api/docs/pricing).

## Criar e guardar a chave

1. Acesse [Google AI Studio](https://aistudio.google.com/api-keys) com sua conta Google e siga a criação de projeto e chave.
2. Confirme que o projeto está no **Free Tier**. Não configure faturamento ou use um projeto pago para este experimento.
3. Na raiz deste repositório, copie `.env.example` para `.env` pelo editor e preencha `GEMINI_API_KEY` localmente. Use `GEMINI_MODEL=gemini-3.5-flash-lite`. Se já existir um `.env`, preserve-o e selecione o modelo por variável de ambiente.
4. Nunca envie a chave pelo chat. O arquivo `.env` é ignorado pelo Git. Uma variável de ambiente `GEMINI_API_KEY`, se configurada, tem precedência sobre o arquivo.
5. Consulte as cotas efetivas do projeto no AI Studio. Registre somente os limites, sem a chave.

Não é necessário instalar um SDK para o cliente REST deste projeto. O primeiro teste externo deverá usar uma entrada sintética curta; somente após validar autenticação, formato e cotas será executado o piloto com questões.

No projeto utilizado, o usuário informou para o Flash-Lite 15 requisições/minuto, 250 mil tokens/minuto e 500 requisições/dia. O lote usa uma chamada por questão, com pausa de dez segundos após cada resposta, e reaproveita recibos válidos. São limites observados neste projeto, não uma promessa para outras contas. O executor não ativa faturamento, não troca de modelo e não repete falhas automaticamente na mesma invocação.

```powershell
$env:GEMINI_MODEL = 'gemini-3.5-flash-lite'
python -m classificacao_topicos verificar-api
```

O cliente usa `responseFormat.text.mimeType=APPLICATION_JSON`, conforme o enum aceito pelo endpoint e a [referência REST](https://ai.google.dev/api/generate-content?hl=en#TextResponseFormat). O histórico da integração está em [Pilotos](PILOTO_V1.md).

## Custo e dados enviados

As cotas variam por projeto; não há promessa de processar as 359 questões em um único dia. A chave herda a condição de cobrança do projeto. O código não consegue certificar, apenas pela chave, que o projeto está no plano gratuito; a conferência no painel é necessária.

Nos serviços gratuitos, os termos do Google permitem uso de entradas e respostas para melhoria de produtos e revisão humana. Não enviar materiais confidenciais, dados pessoais, contexto privado de candidatura ou credenciais. O case autoriza uso de IA e exige repositório público; as chamadas planejadas usam apenas o conteúdo necessário das questões e a árvore fornecida.

## Fontes oficiais

- [Modelo e capacidades](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite)
- [Preços e plano gratuito](https://ai.google.dev/gemini-api/docs/pricing)
- [Criação e uso de chaves](https://ai.google.dev/gemini-api/docs/api-key)
- [Cotas por projeto](https://ai.google.dev/gemini-api/docs/rate-limits)
- [Faturamento](https://ai.google.dev/gemini-api/docs/billing)
- [Termos dos serviços gratuitos](https://ai.google.dev/gemini-api/terms)
- [Formato estruturado no endpoint generateContent](https://ai.google.dev/gemini-api/docs/generate-content/structured-output)
