# Validação final e entrega

Este registro reúne a reprodução do pacote entregue por **João Roberto de Oliveira Felix**, a conferência dos requisitos e as orientações para envio. As classificações e a previsão foram preservadas durante a validação.

## Resultado da execução em 16/10/2026

**Aprovada:** 14 etapas, 36 comparações e nenhuma nova chamada de API. Foram 35 comparações byte a byte, incluindo o PDF, e uma comparação integral do JSON de avaliação após normalizar somente os prefixos locais das fontes. A suíte executou **282 testes: 281 aprovados e um pulado** por permissão para criar symlink real no Windows; essa proteção também tem teste simulado. Duração informada pela suíte: 183,900 s; reprodução completa: 359,501 s.

A execução partiu de um clone local novo do commit `b1e8539021f2417fd3f2513681745d2c50c6a0dc`, inicialmente limpo, sem `.env`, ambiente virtual ou prompts expandidos. Foram copiados apenas o novo verificador e seu teste; essas duas adições ainda não commitadas constam no estado inicial do Git e nos hashes do registro. O ambiente virtual foi criado no clone e as dependências opcionais foram instaladas antes da execução offline. A documentação de fechamento foi atualizada depois e tem hashes no checkpoint do módulo.

Os 610 arquivos de entrada foram preservados. Nos nove diretórios reconstruídos, o inventário conferiu 28 produtos versionados e quatro prompts expandidos regeneráveis, sem ausências ou extras. O [registro da reprodução](../artefatos/verificacao-final/reproducao-checkout-limpo.json) contém comandos, resultados, tempos e hashes; o [checkpoint do módulo 7](../artefatos/checkpoints/modulo7_2026-10-16.json) registra também a conferência do pacote e o fechamento documental.

## Como o avaliador reproduz a entrega

Com Git e Python 3.11+, a partir da raiz de um checkout:

```sh
python -B scripts/verificar_entrega.py --testes
```

O [verificador](../scripts/verificar_entrega.py) lê as fontes versionadas, copia-as para uma pasta temporária e deixa inicialmente ausentes nove diretórios de produtos. Reconstrói preparação, dois pilotos de preparação, lote base, decisões v1, pacote de auditoria, lote de desambiguação, propostas e decisões v2. Os quatro arquivos de prompts expandidos são recriados localmente a partir dos templates; não precisam estar no Git.

O script compara o inventário inteiro desses diretórios, incluindo os quatro prompts regeneráveis, para detectar arquivos ausentes ou produtos inesperados. Compara bytes e hashes dos produtos versionados, o CSV final, a comparação por questão da auditoria e o diagnóstico de cobertura. Depois reconstrói previsão, Markdown e evidências e confere igualdade com a entrega. Qualquer divergência interrompe a execução com código diferente de zero. As fontes da pasta de origem também são conferidas ao final.

As respostas dos modelos, referências, revisões de `fora`, análises históricas dos pilotos e a sensibilidade posterior são entradas preservadas. Q0005 usa seu derivado histórico, cuja origem e seleção cronológica são revalidadas. Não são criados novos julgamentos. Reproduzir esse cálculo não garante que uma nova chamada ao modelo dê a mesma resposta.

O relatório de avaliação v1 contém caminhos absolutos do computador original. A comparação normaliza somente o prefixo local nas chaves de `fontes_sha256`; todos os demais campos, os caminhos relativos e os hashes das fontes precisam coincidir. O CSV da comparação não recebe normalização e precisa ser idêntico byte a byte.

Durante os comandos Python, o verificador bloqueia as chamadas usuais de rede e a leitura do `.env` da cópia. Ele recusa arquivos privados rastreados, caminhos externos ou fontes simbólicas. Isso é uma proteção do processo de reprodução, não um sandbox de sistema operacional. A pasta temporária é removida ao encerrar, sem modificar os produtos de origem.

## Conferência opcional do PDF

Para verificar também o PDF, use as dependências separadas de autoria, em ambiente novo:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-relatorio.txt
.venv/Scripts/python.exe -B scripts/verificar_entrega.py --pdf --testes
```

Em Linux/macOS, usar `.venv/bin/python`. A instalação de pacotes pode acessar o índice de dependências; as etapas de classificação, avaliação e geração posterior são offline. O pipeline sem PDF usa somente a biblioteca padrão. A execução local de aceitação foi feita no Windows com Python 3.14.7; não foi executada uma matriz de sistemas operacionais ou de todas as versões de Python anunciadas.

Use `--registro caminho/novo.json` para salvar comandos, duração, comparação dos produtos, estado inicial do Git, hash do verificador e hashes das fontes. O script recusa substituir um registro existente. A inclusão explícita do verificador e de seus testes permite conferir essas duas adições antes do primeiro commit; o registro diferencia o commit base das alterações presentes.

## Requisitos e integridade

| Item | Conferência |
| --- | --- |
| CSV oficial | 359 linhas e IDs únicos, mesma ordem da fonte, seis colunas exigidas |
| Decisões | 77 `publicar`, 278 `revisar`, quatro `fora`; raiz igual à versão v2 |
| Temas e extras | Centrais e 149 associações extras ativos, sem repetição de extras; motivos obrigatórios presentes |
| Confiança | Valores entre zero e um; origem autodeclarada e ausência de calibração descritas |
| Previsão | Quatro campos oficiais, ponto e intervalos conferidos, hash do CSV correspondente |
| Relatório | Cinco páginas; João Roberto de Oliveira Felix no início e na autoria; memo completo somente na quinta página |
| Escopo da evidência | Concordância de IA separada de precisão jurídica; seleção posterior e previsão subjetiva explicitadas |
| Privacidade | Nenhum `.env`, contexto privado ou ambiente virtual rastreado; apenas `.env.example` público |

A auditoria inicial examinou 608 arquivos rastreados, 17 commits alcançáveis e 818 objetos/caminhos. Não encontrou padrões conhecidos de chave Google ou cabeçalhos de chave privada PEM, nem caminhos privados no histórico. Isso registra o alcance da verificação; não constitui garantia contra todo formato possível de segredo. As 193 referências locais encontradas nos 13 Markdown examinados estavam válidas. O template do relatório usa caminhos relativos à raiz da saída. Os links externos não foram exercitados novamente nesta auditoria offline.

O PDF foi comparado ao hash aprovado no [ajuste de autoria](../artefatos/checkpoints/ajuste_relatorio_nome_2026-10-16.json). A inspeção visual das cinco páginas desse ajuste permanece válida para o mesmo arquivo. Modificações futuras devem ser feitas no modelo Markdown e regeneradas, com nova revisão visual.

## Fechamento para envio

Após revisar as alterações do módulo 7 e fazer o commit/push:

1. Abrir o repositório no GitHub sem autenticação para confirmar acesso público. Essa visibilidade externa não é demonstrada pela clonagem local.
2. Abrir `publicacao.csv`, `previsao.txt` e `relatorio.pdf` no repositório publicado; conferir o nome e o último commit.
3. Ensaiar o [roteiro de cinco minutos e as perguntas de defesa](APRESENTACAO.md), principalmente cobertura, previsão subjetiva e diferença entre concordância e precisão.
4. Enviar o link conforme o enunciado. A validação local não realiza publicação do repositório ou envio de e-mail.

Rascunho para o próprio candidato enviar:

> Para: carla@viciodeumaestudante.com.br
>
> Assunto: Entrega do case de IA - João Roberto de Oliveira Felix
>
> Olá, Carla.
>
> Segue o repositório público com minha entrega do case de classificação de tópicos: **[inserir o link público do repositório]**.
>
> O README apresenta os arquivos finais e os comandos de reprodução. Incluí o CSV das 359 questões, a previsão, o relatório de cinco páginas com memo ao professor, o código e as evidências das decisões.
>
> Obrigado pela oportunidade. Fico à disposição para apresentar o trabalho e discutir as escolhas e limitações.
>
> João Roberto de Oliveira Felix

O prazo do enunciado é domingo, **18/10/2026**. O envio e a confirmação de recebimento ficam com o candidato.
