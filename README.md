# Integration Hub API

> **Versão de portfólio.** Código real de produção, anonimizado: nomes de empresa, clientes, pessoas, hosts, e-mails e credenciais foram trocados por valores fictícios (`Acme`, `Banco Alfa`, `10.0.0.x`, `empresa.example`). Toda configuração sensível vem do `.env` (modelo em `.env.example`). O código não aponta para nenhum sistema real.

API central (Flask) que integra os sistemas de uma operação de cobrança: consulta e negociação de dívidas no sistema de cobrança (SOAP), emissão de boletos e PIX, envio de SMS, e-mail (SendGrid/Gmail), WhatsApp (Meta e Twilio), RCS (Infobip), áudios de ligações e autenticação via Active Directory. Inclui um consumidor de webhooks do SendGrid em processo dedicado, um bot de Telegram para consultas operacionais e um painel React para upload de arquivos.

**Stack:** Python, Flask (blueprints), Waitress, pyodbc/SQL Server, requests/SOAP, React + Vite + TypeScript + Tailwind

## Destaques

- Arquitetura em camadas: `presentation` (controllers/schemas) → `application` (services/use cases) → `domain` (entidades, estratégias por carteira) → `infrastructure` (repositórios SQL, clientes externos).
- Strategy pattern para regras de parcelamento e regras por cedente (`domain/strategies`, `cedente_rules`).
- Auditoria de requisições com spool local e flush assíncrono para o banco.
- Consumidor de webhooks em processo único (`run_consumer.py`) para evitar concorrência entre workers da API.

## Estrutura

```text
integration-hub-api/
├── arquivos/
│   └── qrcode/
├── documentacao/
│   ├── gmail services/
│   └── negociacao/
├── frontend/
│   └── src/
│       ├── components/
│       ├── lib/
│       └── pages/
├── src/
│   ├── application/
│   │   ├── gateways/
│   │   ├── services/
│   │   └── use_cases/
│   ├── domain/
│   │   ├── dtos/
│   │   ├── entities/
│   │   ├── enums/
│   │   ├── exceptions/
│   │   ├── repositories/
│   │   ├── strategies/
│   │   └── utils/
│   ├── infrastructure/
│   │   ├── database/
│   │   ├── external/
│   │   ├── logging/
│   │   ├── queue/
│   │   ├── repositories/
│   │   ├── security/
│   │   └── servers/
│   ├── presentation/
│   │   ├── controllers/
│   │   ├── error/
│   │   └── schemas/
│   ├── shared/
│   │   └── utils/
│   └── static/
├── app.py
├── requirements.txt
├── run.py
├── run_bot.py
└── run_consumer.py
```

## Como executar

```bash
pip install -r requirements.txt
cp .env.example .env   # ajuste os valores
python run.py            # API
python run_consumer.py   # consumidor de webhooks
python run_bot.py        # bot de Telegram
```
