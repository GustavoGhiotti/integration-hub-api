# Envio de e-mail

Permite enviar um e-mail em texto simples, com possibilidade de anexo conforme a configuração da API.

## Endpoint

```http
POST /gmail/email/enviar
```

## Autenticação

```http
Authorization: Bearer SEU_TOKEN
```

## Envio sem anexo

Utilize:

```http
Content-Type: application/json
```

### Exemplo com cURL

```bash
curl --request POST \
  --url http://localhost:8030/gmail/email/enviar \
  --header "Authorization: Bearer SEU_TOKEN" \
  --header "Content-Type: application/json" \
  --data '{
    "destinatarios": [
      "destinatario@empresa.com.br"
    ],
    "assunto": "Teste de envio",
    "mensagem": "Este é um teste de envio de e-mail pela API."
  }'
```

> Ajuste os nomes dos campos conforme o `EnviarEmailSchema` utilizado na aplicação.

## Envio com anexo

Para enviar um anexo, utilize:

```http
Content-Type: multipart/form-data
```

### Exemplo com cURL

```bash
curl --request POST \
  --url http://localhost:8030/gmail/email/enviar \
  --header "Authorization: Bearer SEU_TOKEN" \
  --form 'destinatarios=destinatario@empresa.com.br' \
  --form 'assunto=Teste com anexo' \
  --form 'mensagem=Este é um teste de envio com anexo.' \
  --form 'anexo=@C:/Documentos/arquivo.pdf'
```

## Resposta de sucesso

```json
{
  "success": true,
  "message": "E-mail enviado com sucesso.",
  "data": {
    "messageId": "IDENTIFICADOR_DA_MENSAGEM"
  }
}
```

## Exemplo de erro de validação

```json
{
  "success": false,
  "message": "Dados inválidos.",
  "errors": {
    "destinatarios": [
      "Informe pelo menos um destinatário."
    ]
  }
}
```
