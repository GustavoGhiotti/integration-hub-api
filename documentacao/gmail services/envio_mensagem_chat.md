# Envio de mensagem para o Google Chat

Permite enviar uma mensagem para um espaço do Google Chat previamente cadastrado no banco de dados.

A URL do webhook não deve ser enviada na requisição. Ela é recuperada internamente pela API.

## Endpoint

```http
POST /gmail/chat/enviar
```

## Autenticação

```http
Authorization: Bearer SEU_TOKEN
```

## Corpo da requisição

Utilize:

```http
Content-Type: application/json
```

O espaço pode ser localizado por:

- `id_chat`;
- `nome_chat`.

### Campos

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---:|---|
| `id_chat` | inteiro | Não | Identificador do chat cadastrado no banco. |
| `nome_chat` | texto | Não | Nome do chat cadastrado no banco. |
| `mensagem` | texto | Sim | Mensagem enviada ao espaço do Google Chat. |

É obrigatório informar pelo menos `id_chat` ou `nome_chat`.

Quando os dois campos forem enviados, o `id_chat` terá prioridade.

## Envio pelo ID

```bash
curl --request POST \
  --url http://localhost:8030/gmail/chat/enviar \
  --header "Authorization: Bearer SEU_TOKEN" \
  --header "Content-Type: application/json" \
  --data '{
    "id_chat": 1,
    "mensagem": "Teste de envio para o Google Chat."
  }'
```

## Envio pelo nome

```bash
curl --request POST \
  --url http://localhost:8030/gmail/chat/enviar \
  --header "Authorization: Bearer SEU_TOKEN" \
  --header "Content-Type: application/json" \
  --data '{
    "nome_chat": "Alertas Sistemas",
    "mensagem": "Teste de envio para o Google Chat."
  }'
```

## Envio com ID e nome

```bash
curl --request POST \
  --url http://localhost:8030/gmail/chat/enviar \
  --header "Authorization: Bearer SEU_TOKEN" \
  --header "Content-Type: application/json" \
  --data '{
    "id_chat": 1,
    "nome_chat": "Nome que será ignorado",
    "mensagem": "Teste de envio com prioridade pelo ID."
  }'
```

Nesse caso, o sistema localizará o chat exclusivamente pelo `id_chat`.

Caso o ID não exista, a API não tentará localizar o chat pelo nome.

## Exemplo no PowerShell

```powershell
curl.exe --request POST "http://localhost:8030/gmail/chat/enviar" `
  --header "Authorization: Bearer SEU_TOKEN" `
  --header "Content-Type: application/json" `
  --data-raw '{
    "id_chat": 1,
    "mensagem": "Teste de envio para o Google Chat."
  }'
```

## Resposta de sucesso

```json
{
  "success": true,
  "message": "Mensagem enviada com sucesso para o Google Chat.",
  "data": {
    "id_chat": 1,
    "nome_chat": "Alertas Sistemas"
  }
}
```

## Erro sem identificação do chat

```json
{
  "success": false,
  "message": "Dados inválidos.",
  "errors": {
    "_schema": [
      "Informe o ID ou o nome do chat."
    ]
  }
}
```

## Chat não encontrado

```json
{
  "success": false,
  "message": "Chat com ID 999 não encontrado."
}
```

## Observações de segurança

- Não envie a URL do webhook no corpo da requisição;
- Não exponha o webhook em logs;
- Não armazene webhooks diretamente no código;
- Utilize somente chats previamente cadastrados no banco de dados;
- Substitua `SEU_TOKEN` por um token de autenticação válido;
- Substitua `localhost:8030` pelo endereço real da API.
