# Organizacao da API

Documento criado para registrar como o projeto esta organizado hoje e qual e a responsabilidade de cada pasta e camada.

## Visao geral

O projeto e uma API Python com Flask, organizada em camadas inspiradas em [[Clean Architecture]]:

- `presentation`: entrada HTTP da aplicacao, validacao de payloads, schemas, blueprints e tratamento de erro.
- `application`: casos de uso e servicos que coordenam regras da aplicacao.
- `domain`: entidades, modelos, excecoes, estrategias e utilitarios ligados ao dominio do negocio.
- `infrastructure`: detalhes externos, como banco SQL Server, APIs de terceiros, filas, logs, seguranca e servidores.
- `shared`: utilitarios reutilizaveis por mais d1e uma camada.

Tambem existe um frontend em React/Vite dentro de `frontend`, servido pelo proprio Flask quando o build esta em `frontend/dist`.

## Pontos de entrada

### `app.py`

Arquivo principal de criacao da aplicacao Flask.

Responsabilidades:

- cria o app Flask em `create_app`;
- configura JWT;
- inicia workers de fila;
- inicia agendador de templates;
- configura logger global;
- registra middlewares de auditoria, seguranca e CORS;
- configura rate limit com `Flask-Limiter`;
- registra blueprints da API;
- configura documentacao OpenAPI em `/docs` usando `flask-smorest`;
- serve o frontend compilado em `frontend/dist`;
- registra fallback de SPA para rotas do React;
- registra handlers globais de erro;
- inicia worker assincrono de eventos da SendGrid.

### `run.py`

Arquivo usado para executar a aplicacao em ambiente de servidor com `waitress`.

Responsabilidades:

- importa `create_app`;
- cria a instancia `app`;
- sobe o servidor na porta `8030`;
- opcionalmente inicia o bot do Telegram via variaveis `BOT_AUTOSTART` ou `ENABLE_TELEGRAM_BOT`.

### `run_bot.py`

Arquivo separado para executar o bot do Telegram.

## Estrutura principal

```text
APISistemaAcme/
+-- app.py
+-- run.py
+-- run_bot.py
+-- requirements.txt
+-- .env
+-- src/
|   +-- application/
|   +-- domain/
|   +-- infrastructure/
|   +-- presentation/
|   +-- shared/
|   +-- static/
+-- frontend/
+-- tests/
+-- arquivos/
+-- logs/
+-- documentacao/
```

## Camada `src/presentation`

Camada responsavel por receber requisicoes HTTP e devolver respostas.

### `src/presentation/controllers`

Contem os blueprints Flask da API.

Arquivos principais:

- `auth_routes.py`: rota `/auth/token`, responsavel por gerar token JWT a partir de credenciais Basic.
- `collectsys.py`: rotas `/acme`, como obter dividas, verificar contratos, propostas, formalizacao, tabulacao, boleto, pix e linha digitavel.
- `sendgrid.py`: webhook/eventos relacionados ao SendGrid.
- `sms.py`: rotas de SMS.
- `infobip.py`: rotas relacionadas a Infobip.
- `hvoice.py`: rotas relacionadas a HVoice.
- `digital.py`: rotas de integracoes digitais.
- `ad_controller.py`: rotas de Active Directory.
- `easycollector_controller.py`: rotas da automacao EasyCollector.
- `pesquisa_acionamento.py`: rotas usadas pela pesquisa de acionamento.
- `mensagens_controller.py`: rotas de mensagens/conversas.
- `upload_arquivo.py`: upload de arquivos.
- `webhook_meta.py`: webhook/proxy de eventos Meta/WhatsApp.
- `banco_beta_controller.py`: rotas especificas do Banco Beta.
- `chat_portalacordo.py`: rotas relacionadas ao fluxo Portal Acordo.

O arquivo `__init__.py` centraliza os imports dos blueprints para que `app.py` consiga registrar tudo a partir de `src.presentation.controllers`.

### `src/presentation/schemas`

Contem schemas de entrada e saida usados pelos controllers e pela documentacao OpenAPI.

Exemplos:

- `auth.py` e `auth_schema.py`: schemas de autenticacao.
- `collectsys.py`: schemas das rotas `/acme`.
- `digital.py`, `hvoice.py`, `active_directory.py`: schemas por contexto de integracao.

### `src/presentation/error`

Centraliza tratamento de erros HTTP, erros de dominio e erros especificos CollectSys.

O arquivo `__init__.py` expoe `register_error_handles(app)`, chamado no `app.py`.

## Camada `src/application`

Camada de coordenacao da regra de aplicacao. Os controllers chamam esta camada para executar operacoes de negocio sem misturar detalhes HTTP com integracoes externas ou SQL.

### `src/application/services`

Servicos por contexto funcional.

Exemplos:

- `auth_service.py`: valida credenciais, consulta usuario no repositorio e gera JWT.
- `sendgrid_service.py`: processamento de eventos do SendGrid.
- `infobip_service.py` e `infobip_whatsapp_service.py`: envio/processamento via Infobip.
- `sms_services.py`: servicos de SMS.
- `twilio_service.py` e `twilio_chat_service.py`: integracao Twilio.
- `hvoice_service.py`: integracao HVoice.
- `easycollector_service.py`: coordenacao dos fluxos EasyCollector.
- `ad_service.py`: integracao com Active Directory.
- `upload_arquivo_service.py`: regras de upload.
- `acionamento_service.py`: regras da pesquisa/acionamento.
- `meta_service.py` e `webhook_meta_service.py`: regras ligadas a Meta/WhatsApp.
- `banco_beta.py`: fluxo Banco Beta.
- `users_service.py`: regras de usuario.

### `src/application/services/collectsys`

Servicos especificos da negociacao Acme/CollectSys.

Exemplos:

- `cliente_service.py`: dados do cliente.
- `cedente_service.py`: dados de cedentes.
- `dados_vega_service.py`: tratamentos especificos da Vega.
- `negociacao_service.py`: propostas e negociacao.
- `formalizar_service.py`: formalizacao de acordo.
- `meios_pagamentos_service.py`: boleto, pix, QR Code e linha digitavel.
- `tabular_service.py`: tabulacao de acionamento.
- `valores_dividas_service.py`: valores de dividas.

### `src/application/use_cases`

Casos de uso mais explicitos, separados dos servicos gerais.

Arquivos atuais:

- `login_user.py`;
- `parcelamento_max_case.py`.

## Camada `src/domain`

Camada que representa conceitos do negocio e regras que nao deveriam depender diretamente de Flask, SQL Server ou APIs externas.

### `src/domain/entities`

Entidades do dominio, varias usando Pydantic.

Exemplos:

- `acordo.py`: estrutura de acordo.
- `cedentes.py`: cedente.
- `contrato.py`: contrato.
- `divida.py`: divida.
- `documento.py`: documento.
- `job_easycollector.py`: job de execucao EasyCollector.
- `user_auth.py`: usuario autenticado.
- `usuario_collectsys.py`: credenciais/contexto CollectSys.

### `src/domain/models`

Modelos auxiliares de requisicao e eventos.

Exemplos:

- `email_event.py`;
- `user_request.py`;
- `requests/base_request.py`.

### `src/domain/exceptions`

Excecoes de negocio.

Exemplos:

- `collectsys_exception.py`;
- `usuario_exception.py`;
- `beta_boleto_exception.py`.

### `src/domain/strategies/carteiras`

Estrategias por carteira/cedente.

Exemplos:

- `base_strategy.py`: contrato/base das estrategias.
- `default_strategy.py`: comportamento padrao.
- `banco_beta_strategy.py`;
- `mu_strategy.py`;
- `nu_strategy.py`;
- `definir_strategy.py`: seleciona ou direciona a estrategia adequada.

### `src/domain/utils`

Funcoes utilitarias ligadas ao dominio.

Exemplos:

- `agendador.py`: agendamento usado na inicializacao.
- `ajusta_telefone.py`;
- `audios.py`;
- `metadados.py`;
- `parser_infobip.py`.

### `src/domain/repositories`

Contratos/abstracoes de repositorio do dominio.

Arquivo atual:

- `email_event_repository.py`.

## Camada `src/infrastructure`

Camada que implementa detalhes tecnicos e acessos externos.

### `src/infrastructure/database`

Infraestrutura de banco de dados.

- `base_connection.py`: classe abstrata de conexao.
- `sql_server_connection.py`: implementacao SQL Server com `pyodbc`, retry para deadlock e metodos `execute`/`executemany`.
- `db_utils.py`: utilitarios de banco.

### `src/infrastructure/repositories`

Implementacoes concretas de acesso a dados.

Exemplos:

- `sql_auth_token.py`: consulta usuarios/tokens da API.
- `sql_collectsys_repository.py`: dados relacionados a CollectSys.
- `sql_email_event_repository.py`: eventos de email.
- `sql_sms_repository.py`: dados de SMS.
- `sql_infobip_repository.py`: dados Infobip.
- `sql_hvoice_repository.py`: dados HVoice.
- `sql_easycollector_carga_repository.py` e `sql_easycollector_tarefa_repository.py`: dados EasyCollector.
- `sql_acionamento_repository.py`: dados de acionamento.
- `users_repository.py`: usuarios.
- `cedente_repository.py`: cedentes.

### `src/infrastructure/external`

Clientes e automacoes de sistemas externos.

Subpastas:

- `collectsys`: integracao SOAP/HTTP com EasyCollector/CollectSys, credenciais, DTOs, mappers, providers e regras por cedente.
- `infobip`: cliente Infobip.
- `twilio`: cliente e parser Twilio.
- `banco_beta`: token e emissao de boleto Banco Beta.
- `easycollector`: automacao com Playwright para login, navegacao, consulta e screenshots.
- `telegram`: bot do Telegram.

### `src/infrastructure/external/collectsys`

Pasta mais detalhada da integracao CollectSys.

- `providers`: chamadas para consultar cliente, contratos, dividas, calcular proposta, confirmar acordo, emitir boleto, envio de email, tabular etc.
- `credentials`: carregamento/fornecimento de credenciais.
- `cedente_rules`: regras especificas por cedente, como Beta, Mu, GAMA, Rho, Delta, Nu e outras.
- `dto`: objetos de transporte para chamadas externas.
- `mappers`: conversao de respostas externas para modelos internos.

### `src/infrastructure/queue`

Filas em memoria baseadas em `queue.Queue` e threads.

- `config_queue.py`: fila de SMS em lote, com workers daemon.
- `event_queue.py`: worker assincrono para eventos, usado por SendGrid.

### `src/infrastructure/security`

Seguranca de rotas.

- `auth_decorator.py`: decoradores `token_require` e `token_required_collectsys`.

Esses decoradores validam JWT ou token CollectSys, atualizam contexto de log e, no caso de `/acme`, carregam credenciais CollectSys em `g.collectsys`.

### `src/infrastructure/logging`

Configuracao de logs.

- `logger_config.py`: logger global, logger por modulo e contexto da requisicao.

### `src/infrastructure/servers`

Arquivos auxiliares de servidor/conexao.

- `conexao.py`;
- `servidor.py`.

## Camada `src/shared`

Utilitarios compartilhados por mais de uma camada.

### `src/shared/utils`

Exemplos:

- `env_load.py`: carrega variaveis do `.env`, como banco, JWT, SendGrid, AD, Meta, Infobip, Twilio, SMB, EasyCollector e Telegram.
- `xml_tratamentos.py`: tratamentos e extracoes de XML.
- `validador.py`: validacoes reutilizaveis.
- `tratativa_detalhe.py`: tratamento de detalhes.
- `data.py`: utilitarios de data.

## Pasta `src/static`

Arquivos estaticos usados pelo backend.

Atualmente contem:

- `images/favicon.ico`: favicon usado pela documentacao e pela aplicacao.

## Frontend `frontend`

Aplicacao React com Vite, TypeScript, Tailwind e componentes de UI.

Estrutura principal:

```text
frontend/
+-- src/
|   +-- App.tsx
|   +-- main.tsx
|   +-- login.tsx
|   +-- pesquisaAcionamento.tsx
|   +-- portalacordo.tsx
|   +-- BaixarConversa.tsx
|   +-- NotFound.tsx
|   +-- components/ui/
|   +-- lib/
+-- public/
+-- package.json
+-- vite.config.js
+-- tailwind.config.js
+-- tsconfig.json
```

Rotas React atuais:

- `/pesquisaAcionamento/login`;
- `/pesquisaAcionamento/home`;
- `/pesquisaAcionamento/portalacordo`;
- fallback `*` para `NotFound`.

O Flask serve o arquivo `frontend/dist/index.html` na rota `/` e usa fallback para permitir navegacao SPA.

## Pastas auxiliares

### `arquivos`

Pasta para arquivos gerados ou armazenados pela aplicacao.

Subpastas atuais:

- `boletos`: armazenamento/controle de boletos.
- `qrcode`: armazenamento/controle de QR Codes.

Os arquivos `.gitkeep` mantem as pastas versionadas mesmo quando vazias.

### `logs`

Pasta esperada para arquivos de log gerados pela aplicacao.

### `tests`

Pasta de testes.

Arquivo atual:

- `test_sendgrid.py`: teste relacionado ao processamento SendGrid.

### `documentacao`

Pasta de documentacao do projeto, usada tambem como vault do Obsidian.

Arquivos atuais:

- `Bem-vindo.md`;
- `Contexto Geral.md`;
- `Clean Code - Guia de Contexto para Python.md`;
- `Organizacao da API.md`.

## Fluxo de uma requisicao

Fluxo comum:

1. A requisicao entra no Flask criado em `app.py`.
2. Middlewares registram tempo, request id, contexto de log, CORS e headers de seguranca.
3. O blueprint correto em `src/presentation/controllers` recebe a rota.
4. O schema em `src/presentation/schemas` valida headers, query ou JSON quando a rota usa `@bp.arguments`.
5. O decorator de seguranca valida JWT ou token especifico, quando aplicado.
6. O controller chama um service ou use case em `src/application`.
7. O service coordena entidades, estrategias, repositorios e clientes externos.
8. Repositorios em `src/infrastructure/repositories` acessam SQL Server.
9. Clientes em `src/infrastructure/external` chamam sistemas externos.
10. A resposta volta para o controller, que retorna JSON.
11. Handlers globais tratam excecoes padronizadas.

## Documentacao da API

A documentacao OpenAPI e configurada em `app.py` pela funcao `create_docs`.

Endpoint:

- `/docs`: Swagger UI.
- `/docs/openapi.json`: especificacao OpenAPI.

Nem todas as rotas entram na documentacao. Algumas sao registradas diretamente no Flask sem `flask-smorest`, como SendGrid, SMS, AD, Infobip, EasyCollector, Acionamento, Mensagens e Webhook Meta.

## Autenticacao e autorizacao

Existem dois fluxos principais:

- JWT interno:
  - rota de geracao: `/auth/token`;
  - implementacao: `AuthService`;
  - repositorio: `UserAPI` em `sql_auth_token.py`;
  - validacao: `token_require`.

- Token CollectSys:
  - validacao por `token_required_collectsys`;
  - consulta em `AuthAPI`;
  - credenciais carregadas em `g.collectsys`.

Para rotas `/acme`, o decorator tambem busca credenciais CollectSys vinculadas ao usuario e disponibiliza no contexto Flask.

## Variaveis de ambiente

O arquivo `src/shared/utils/env_load.py` centraliza o carregamento das variaveis do `.env`.

Categorias atuais:

- banco de dados: `DB_USER`, `DB_PASSWORD`, `DB_66`, `DB_71`, `DB_72`, `DB_65`, `DB_248`, `DB_170`;
- tokens e seguranca: `JWT_SECRET`, `TOKEN_DB_API`, `TOKEN_KEY`, `KEY_CRIPTO`;
- SendGrid;
- Active Directory;
- Twilio;
- SMB;
- Meta/WhatsApp;
- Infobip;
- EasyCollector;
- Telegram.

## Convencao recomendada para novos codigos

Ao criar uma nova funcionalidade:

1. Criar ou atualizar o controller em `src/presentation/controllers`.
2. Criar schemas de entrada/saida em `src/presentation/schemas`.
3. Colocar regra de aplicacao em `src/application/services` ou `src/application/use_cases`.
4. Criar entidades/modelos/excecoes no `src/domain` quando forem conceitos de negocio.
5. Criar repositorios em `src/infrastructure/repositories` quando houver acesso a banco.
6. Criar cliente externo em `src/infrastructure/external` quando houver chamada para outro sistema.
7. Registrar o blueprint em `src/presentation/controllers/__init__.py` e em `app.py`.
8. Adicionar testes em `tests` quando a regra tiver impacto de negocio ou integracao relevante.

## Observacoes tecnicas

- A aplicacao usa `waitress` em `run.py` para servir em producao.
- O servidor Flask usa porta `8030`.
- O rate limit global esta configurado como `10 per seconds`.
- Webhooks importantes, como SendGrid, Infobip e Meta, sao isentos do rate limiter para evitar perda de eventos.
- A conexao SQL Server usa `ODBC Driver 17 for SQL Server`.
- Existem pastas `__pycache__` no projeto local; elas sao artefatos gerados pelo Python e nao fazem parte da arquitetura.
- A pasta `venv` e ambiente virtual local e nao deve ser tratada como codigo da aplicacao.


## Documentação rota

[[Rota acme obter-dividas-ativa]]
[[Rota acme verifica-divida-cedente]]
[[Rota acme propostas-parcelado]]
[[]]
