# Rota `/acme/verifica-divida-cedente`

Documento especifico da rota que consulta os contratos ativos/dados detalhados de divida para um cedente de um cliente.

## Resumo

- Metodo: `GET`
- Endpoint: `/acme/verifica-divida-cedente`
- Controller: `src/presentation/controllers/collectsys.py`
- Funcao: `verifica_divida_cedente`
- Autenticacao: JWT Bearer via `@token_require("/acme")`
- Entrada: headers `idCliente`, `cedente` e opcionalmente `data`
- Retorno de sucesso: JSON com `status` e `contratos`
- Possui dois fluxos principais:
  - Vega: `DadosDividaVega().obter_divida_vega(idCliente)`
  - Demais cedentes: `DadosDivida.obter_dados_divida(idCliente, cedente, data)`

## Arquivos envolvidos

```text
src/presentation/controllers/collectsys.py
src/presentation/schemas/collectsys.py
src/infrastructure/security/auth_decorator.py
src/infrastructure/repositories/sql_collectsys_repository.py
src/application/services/collectsys/dados_vega_service.py
src/infrastructure/repositories/sql_vega_repository.py
src/application/services/collectsys/negociacao_service.py
src/application/services/collectsys/valores_dividas_service.py
src/domain/entities/contrato.py
src/domain/entities/divida.py
src/domain/entities/acordo.py
src/domain/entities/cedentes.py
src/infrastructure/external/collectsys/providers/obter_dividas.py
src/infrastructure/external/collectsys/providers/obter_dados_acordo.py
src/infrastructure/external/collectsys/providers/calcular.py
src/infrastructure/external/collectsys/providers/consulta_contrato_detalhe.py
src/shared/utils/xml_tratamentos.py
src/presentation/error/error_domain.py
src/presentation/error/error_collectsys.py
```

## Assinatura da rota

No arquivo `src/presentation/controllers/collectsys.py`:

```python
@bp.get("/verifica-divida-cedente")
@bp.arguments(VerificaDividaCedenteSchema, location="headers")
@bp.response(200, VerificarCedenteResponse, description="Retorno das dividas do cliente")
@bp.response(401, Erro401Schema, description="Retorno de erro")
@token_require("/acme")
def verifica_divida_cedente(body: VerificaDividaCedenteSchema):
    log.info(
        "verifica_divida_cedente iniciado idCliente=%s cedente=%s",
        body.idCliente,
        body.cedente,
    )

    if "vega" in str(body.cedente).lower() or str(body.cedente) == "1":
        contratos = DadosDividaVega().obter_divida_vega(body.idCliente)
    else:
        data_ref = getattr(body, "data", None)
        contratos = asyncio.run(
            DadosDivida.obter_dados_divida(body.idCliente, body.cedente, data_ref)
        )

    log.info("verifica_divida_cedente concluido idCliente=%s", body.idCliente)

    return jsonify({"status": True, "contratos": contratos}), 200
```

## Headers esperados

### `Authorization`

Token JWT:

```text
Authorization: Bearer <token>
```

O token precisa ter permissao para `"/acme"` no claim `rotas`, exceto para usuario com `id_usuario == 1`.

### `idCliente`

Identificador do cliente.

```text
idCliente: 123456
```

### `cedente`

Identifica qual cedente/origem sera consultado.

Exemplos:

```text
cedente: BANCO BETA
cedente: MU
cedente: VEGA
cedente: 1
```

Regra especial:

- se `cedente` contem `vega`, ignorando maiusculas/minusculas, ou se `cedente == "1"`, a rota usa o fluxo Vega.
- qualquer outro valor segue o fluxo CollectSys/Cobranca.

### `data`

Campo opcional.

```text
data: 2026-05-20
```

Quando informado no fluxo nao Vega, e repassado para os calculos de proposta a vista. No schema, e validado como `fields.Date`.

## Validacao de entrada

Schema:

```text
src/presentation/schemas/collectsys.py -> VerificaDividaCedenteSchema
```

Campos:

```python
idCliente = fields.Integer(required=True)
cedente = fields.String(required=True)
data = fields.Date(required=False, allow_none=True)
```

Depois da validacao, o schema retorna um `SimpleNamespace`, permitindo:

```python
body.idCliente
body.cedente
body.data
```

## Autenticacao e permissao

A rota usa:

```python
@token_require("/acme")
```

Arquivo:

```text
src/infrastructure/security/auth_decorator.py
```

Fluxo:

1. Busca o header `Authorization`.
2. Se nao existir, dispara `TokenInvalido("Token de autorizacao ausente")`.
3. Valida o JWT com `verify_jwt_in_request()`.
4. Le o id do usuario com `get_jwt_identity()`.
5. Le os claims com `get_jwt()`.
6. Atualiza o contexto de log.
7. Verifica se `"/acme"` esta no claim `rotas`.
8. Se nao estiver e o usuario nao for `id_usuario == 1`, dispara `TokenInvalido("Acesso negado a esta rota")`.
9. Busca credenciais CollectSys do usuario:

```text
SqlCollectSysRepository(DB_66, "DB_DESENVOLVIMENTO").obter_usuario_collectsys(id_usuario)
```

10. Salva no contexto Flask:

```python
g.collectsys = UsuarioCollectSys(resultado["USUARIO"], resultado["SENHA"])
```

Essas credenciais sao usadas no fluxo CollectSys/Cobranca.

## Fluxo principal

```text
Cliente HTTP
  |
  | GET /acme/verifica-divida-cedente
  | Headers: Authorization, idCliente, cedente, data?
  v
Flask / Blueprint Acme
  |
  v
VerificaDividaCedenteSchema
  |
  | valida idCliente, cedente e data opcional
  v
token_require("/acme")
  |
  | valida JWT
  | valida permissao
  | carrega g.collectsys
  v
verifica_divida_cedente()
  |
  +-- cedente contem "vega" ou cedente == "1"
  |     |
  |     v
  |   DadosDividaVega().obter_divida_vega(idCliente)
  |
  +-- demais cedentes
        |
        v
      DadosDivida.obter_dados_divida(idCliente, cedente, data)
```

# Fluxo Vega

O fluxo Vega e usado quando:

```python
"vega" in str(body.cedente).lower() or str(body.cedente) == "1"
```

Metodo:

```text
DadosDividaVega().obter_divida_vega(id_cliente)
```

Arquivo:

```text
src/application/services/collectsys/dados_vega_service.py
```

## Etapa Vega 1: buscar CPF pelo `idCliente`

Repositorio:

```text
src/infrastructure/repositories/sql_vega_repository.py -> VegaRepository
```

Metodo:

```python
buscar_cpf_por_id_cliente(id_cliente)
```

Banco:

```text
DB_PROC em DB_248
```

Query:

```sql
SELECT NR_CPF
FROM TBL_CLIENTE WITH(NOLOCK)
WHERE ID_CLIENTE = ?
```

Se nao encontrar CPF:

```python
return {"statusCliente": "clienteForaAssessoria"}
```

## Etapa Vega 2: limpar CPF e buscar dados do cliente

O CPF e normalizado para somente digitos:

```python
cpf_limpo = "".join(filter(str.isdigit, str(cpf)))
```

Depois chama:

```python
buscar_dados_cliente(cpf_limpo)
```

Query principal usa:

```sql
dbo.FN_CONSULTA_CLIENTE_VEGA_V2(?)
```

Campos retornados usados:

- `NR_CPF`
- `ID_CLIENTE`
- `NM_CLIENTE`
- `TP_CONTRATO`
- `VL_PRESTACAO`
- `DIAS_ATRASO`
- `FASE`
- `NR_CONTRATO`
- `DIA_VENCIMENTO`
- `NM_PRODUTO`
- `PARCELA_ATRASO`
- `NM_GRUPO_PRODUTO`

Se nao encontrar dados:

```python
return {"statusCliente": "clienteForaAssessoria"}
```

## Etapa Vega 3: buscar email preferencial

Metodo:

```python
buscar_email_cliente(primeiro["ID_CLIENTE"])
```

Banco:

```text
easycollector em DB_170
```

Query:

```sql
SELECT TOP 1 NM_EMAIL
FROM TB_CLIENTE_EMAIL WITH(NOLOCK)
WHERE ID_CLIENTE = ?
  AND TP_PREFERENCIAL = 1
```

Se nao houver email, retorna string vazia.

## Etapa Vega 4: ajustar vencimento

O vencimento vem como:

```python
CONVERT(VARCHAR, GETDATE() + 6, 105) AS DIA_VENCIMENTO
```

Depois a regra faz:

1. Converte `DIA_VENCIMENTO` com formato `%d-%m-%Y`.
2. Carrega feriados do Brasil com `holidays.BR()`.
3. Enquanto a data cair em sabado, domingo ou feriado, volta um dia:

```python
while dia_venc.weekday() in (5, 6) or dia_venc in feriados:
    dia_venc -= timedelta(days=1)
```

4. Formata de volta como `dd-mm-YYYY`.

## Retorno Vega

Formato:

```json
{
  "statusCliente": "clienteEmAssessoria",
  "cpf": "12345678909",
  "idCliente": "123456",
  "nome": "JOAO",
  "email": "email@exemplo.com",
  "contratosEmAtraso": 2,
  "contratos": [
    {
      "tpContrato": "1",
      "nmProduto": "Produto",
      "vlPrestacao": "100.00",
      "DiasAtraso": "10",
      "parcelasAtraso": "2",
      "nmGrupoProduto": "Grupo",
      "fase": "Fase",
      "nrContrato": "999999",
      "diaVencimento": "20-05-2026"
    }
  ]
}
```

O controller embrulha esse retorno em:

```json
{
  "status": true,
  "contratos": {
    "statusCliente": "clienteEmAssessoria",
    "contratos": []
  }
}
```

# Fluxo demais cedentes

Para cedentes que nao sao Vega, o controller chama:

```python
data_ref = getattr(body, "data", None)
contratos = asyncio.run(
    DadosDivida.obter_dados_divida(body.idCliente, body.cedente, data_ref)
)
```

Arquivo:

```text
src/application/services/collectsys/negociacao_service.py
```

## Etapa 1: consultar divida ativa por `idCliente`

Metodo:

```python
ObterDivida(servidor).consultar_por_id(id_cliente)
```

Neste fluxo, o valor de `servidor` e o header `cedente`.

Provider:

```text
src/infrastructure/external/collectsys/providers/obter_dividas.py
```

Operacao SOAP:

```text
ObterDividaAtiva
```

Campos enviados:

- `logonUsuario`: usuario de `g.collectsys`;
- `senhaUsuario`: senha de `g.collectsys`;
- `idCliente`: recebido no header.

## Etapa 2: tratar ausencia de divida

Mensagens verificadas:

```text
Nenhum cliente localizado com este CPFCNPJ.
O cliente nao possui divida ativa.
Cliente nao localizado.
```

Se qualquer uma aparecer:

```python
raise NenhumaDividaException(
    "No momento, nao constam dividas ativas do cliente em nossa assessoria."
)
```

Tratamento:

```text
src/presentation/error/error_domain.py
```

Resposta:

```json
{
  "status": true,
  "msg": "No momento, nao constam dividas ativas do cliente em nossa assessoria."
}
```

Status HTTP:

```text
200
```

## Etapa 3: extrair dados gerais do XML

Do XML retornado pela CollectSys, extrai:

- `<NmCedente>` -> `nome_cedente`
- `<IdCedente>` -> `id_cedente`
- `<IdCliente>` -> `id_cliente`

Depois percorre todos os blocos:

```text
<DividaAtiva>...</DividaAtiva>
```

## Etapa 4: separar acordos e dividas normais

Para cada `<DividaAtiva>`, extrai:

```text
<TipoDivida>
```

Se o tipo contem `acordo`, trata como acordo.

Caso contrario, trata como divida/contrato normal.

## Regra para acordos

Quando e acordo:

1. Extrai `<IdAcordo>`.
2. Extrai `<NumeroPrestacao>`.
3. Consulta faturas do acordo:

```python
DadosAcordo(nome_cedente, id_cliente, id_acordo).obter_faturas()
```

Provider:

```text
src/infrastructure/external/collectsys/providers/obter_dados_acordo.py
```

Operacao SOAP:

```text
ConsultarAcordoFaturas
```

4. Monta entidade `Acordo`:

```python
Contrato(resultado, nome_cedente, id_cedente, id_cliente).acordo(numero_prestacao)
```

5. Adiciona na lista `contratos`.

Depois, na montagem final, acordos viram itens agrupados por `idAcordo`:

```python
{
    "grupo": contrato.nome_cedente,
    "parcelas": [
        {
            "idAcordo": contrato.id_acordo,
            "valor": contrato.valor,
            "parcela": contrato.numero_parcelas,
            "dataVencimento": contrato.vencimento_boleto
        }
    ]
}
```

## Regra para dividas normais

Quando nao e acordo:

1. Para cedente `60`, substitui o XML da divida pelo conteudo de:

```text
<ArrayOfDividaAtiva>...</ArrayOfDividaAtiva>
```

2. Extrai:

- `<NumeroPrestacao>` -> numero da prestacao;
- `<Atraso>` -> dias de atraso.

3. Cria entidade `Divida`:

```python
Contrato(divida, nome_cedente, id_cedente, id_cliente).divida()
```

4. Para Banco Beta (`id_cedente in (81, 104)`), consulta nome do produto:

```python
ConsultaContratoDetalhe(id_cliente, contrato.id_contrato).consultar_nm_produto()
```

Provider:

```text
src/infrastructure/external/collectsys/providers/consulta_contrato_detalhe.py
```

Operacao SOAP:

```text
ConsultarContratoDetalhes
```

5. Se for Banco Beta, produto de cartao e atraso menor ou igual a 35:

```python
contrato.skip_desconto = True
```

Produto de cartao e definido por:

```python
BancoBeta.eh_produto_cartao(nm_produto)
```

Regra:

- contem `CARTAO`;
- nao contem `RENEG`;
- nao contem `EMPRESTIMO`.

6. Atualiza o total de parcelas por contrato usando o maior `NumeroPrestacao`.
7. Se a parcela esta em atraso, registra a prestacao em `parcelas_em_atraso_por_contrato`.
8. Se o contrato ja existe na lista, concatena o XML usando `atualizar_xml`.
9. Se ainda nao existe, adiciona a entidade `Divida`.

## Regras internas de `Contrato.divida()`

Arquivo:

```text
src/domain/entities/contrato.py
```

Extrai:

- `<IdContrato>`;
- `<NumeroPrestacao>`;
- `<Atraso>`.

Regras por cedente:

- Cedente `3`: ajusta o grupo com `Mu.grupo(xml)`.
- Cedentes `65` e `73`: troca `<Marcado>false</Marcado>` por `<Marcado>true</Marcado>`.
- Se receber valor e cedente for `81` ou `104`, mantem o valor.
- Se receber valor para outros cedentes, aplica `round(valor * 0.12, 2)`.
- Se nao receber valor, usa `0.0`.
- Encapsula o XML em `<ArrayOfDividaAtiva>...</ArrayOfDividaAtiva>`.

Nesta rota, a criacao de contrato normal nao passa valor no construtor, entao `valor` normalmente inicia como `0.0`.

## Etapa 5: calcular valores

Depois de montar a lista de contratos/acordos, chama:

```python
resultados = await ValoresDividas.calcular_valores(contratos, data)
```

Arquivo:

```text
src/application/services/collectsys/valores_dividas_service.py
```

### Acordos

Se o item e `Acordo`, ele nao entra nos calculos de valores:

```python
if isinstance(contrato, Acordo):
    continue
```

### Dividas normais

Para cada `Divida`, cria tarefas:

1. Valor sem desconto:

```python
Calcular(...).calcular_divida()
```

2. Valor com desconto/proposta a vista:

So cria essa tarefa se:

```python
not contrato.skip_desconto and contrato.id_cedente != 1
```

Se o cedente nao esta em `CEDENTES_CALCULO_DETALHE`, usa:

```python
Calcular(..., data).calcular_acordo()
```

Se o cedente esta em `CEDENTES_CALCULO_DETALHE`, usa:

```python
Calcular(..., data).calcular_acordo_com_detalhes()
```

Cedentes com calculo por detalhe:

```text
(60, 65, 51, 73, 64, 70, 71, 83, 90, 81, 77, 103, 104)
```

As tarefas rodam em paralelo com:

```python
ThreadPoolExecutor(max_workers=20)
asyncio.gather(...)
```

## Etapa 6: montar dicionario de retorno

O metodo monta `contratos_dict`.

### Dividas normais

Para cada `Divida`, inicia:

```python
{
    "contrato": id_contrato,
    "valorOriginal": {},
    "propostaAvista": {},
    "grupo": contrato.nome_cedente
}
```

Se for Banco Beta e houver produto consultado:

```python
"produto": produtos_por_contrato[id_contrato]
```

### Acordos

Para cada `Acordo`, agrupa por `id_acordo`:

```python
{
    "grupo": contrato.nome_cedente,
    "parcelas": [
        {
            "idAcordo": contrato.id_acordo,
            "valor": contrato.valor,
            "parcela": contrato.numero_parcelas,
            "dataVencimento": contrato.vencimento_boleto
        }
    ]
}
```

## Etapa 7: aplicar resultados de calculo

Cada item calculado tem:

```python
{
    "resultado": resultado,
    "idContrato": id_contrato,
    "tipo": "semDesconto" ou "comDesconto"
}
```

### Tratamento de erro de calculo

Se o resultado contem `<RetornoErro>`, extrai `<Mensagem>`.

Regra especifica para cedente `77`:

- se o erro for no calculo `comDesconto`;
- e a mensagem contem `plano minimo e`;
- extrai o numero minimo e grava em `propostaAvista`:

```python
{
    "mensagem": "o minimo de parcelas para esse contrato = X"
}
```

Regra especifica para Banco Beta (`81`, `104`):

- se a mensagem contem `Falha ao calcular divida`, retorna:

```python
{
    "mensagem": "Contrato nao pode ser negociado no momento."
}
```

Para outros erros, retorna:

```python
{
    "mensagem": mensagem
}
```

### Resultado `semDesconto`

Quando `tipo == "semDesconto"`:

1. Soma os valores `<ValorAtualizado>` de todas as dividas:

```python
ValoresDividas.soma_valores_sem_desc(resultado)
```

2. Extrai:

- `<Atraso>` -> atraso;
- `<DataVencimento>` -> data original, removendo parte `T...`;
- parcelas em atraso registradas anteriormente;
- total de parcelas por contrato.

Para cedente `14`, retorna mais detalhes:

```python
{
    "valor": valor,
    "atraso": atraso,
    "atrasadoDesde": vencimento,
    "parcelasEmAtraso": parcelas_em_atraso,
    "quantidadeParcelasEmAtraso": len(parcelas_em_atraso),
    "quantidadeParcelas": quantidade_parcelas
}
```

Para demais cedentes:

```python
{
    "valor": valor,
    "atraso": atraso,
    "atrasadoDesde": vencimento
}
```

### Resultado `comDesconto`

Quando `tipo == "comDesconto"`:

1. Extrai `<ValorParcela>`.
2. Converte para float.
3. Extrai `<DataParcela>` e remove parte `T...`.
4. Grava:

```python
{
    "valor": valor,
    "pagamento": pagamento
}
```

Se `<ValorParcela>` nao existir ou nao for conversivel, pode gerar `ValueError` e cair no handler generico.

## Etapa 8: proposta a vista original para Banco Beta cartao ate 35 dias

Depois dos calculos, existe uma regra adicional:

Para cada contrato:

- precisa ser `Divida`;
- `id_cedente` em `(81, 104)`;
- `skip_desconto == True`;
- ainda nao ter `propostaAvista`.

Nesse caso chama:

```python
ValoresDividas.proposta_avista_cartao_35(contrato, incluir_boleto=False)
```

Essa regra:

1. Chama `EmitirBoleto(...).emitir_original(contrato.xml)`.
2. Extrai `<VALOR_DOCUMENTO>`.
3. Define `dataPagamento = date.today() + 1 dia`.
4. Retorna:

```python
{
    "valorEntrada": valor,
    "dataPagamento": data_pagamento
}
```

Na resposta da rota, grava:

```python
{
    "valor": proposta_avista["valorEntrada"],
    "pagamento": proposta_avista["dataPagamento"].isoformat()
}
```

## Retorno do fluxo nao Vega

Formato comum:

```json
{
  "status": true,
  "contratos": {
    "999999": {
      "contrato": 999999,
      "grupo": "BANCO BETA",
      "produto": "CARTAO EXEMPLO",
      "valorOriginal": {
        "valor": 1000.0,
        "atraso": 30,
        "atrasadoDesde": "2026-04-10"
      },
      "propostaAvista": {
        "valor": 800.0,
        "pagamento": "2026-05-20"
      }
    }
  }
}
```

Quando houver acordos:

```json
{
  "status": true,
  "contratos": {
    "8888": {
      "grupo": "MU",
      "parcelas": [
        {
          "idAcordo": 8888,
          "valor": 120.0,
          "parcela": 2,
          "dataVencimento": "2026-05-20"
        }
      ]
    }
  }
}
```

Observacao:

- O retorno real de `contratos` no fluxo nao Vega e um dicionario indexado por id de contrato ou id de acordo.
- O schema `VerificarCedenteResponse` descreve `contratos` como lista, mas a implementacao atual retorna dicionario no fluxo nao Vega e objeto no fluxo Vega.

## Erros e respostas tratadas

### Header obrigatorio ausente ou invalido

Origem:

```text
VerificaDividaCedenteSchema
```

Campos obrigatorios:

- `idCliente`
- `cedente`

`idCliente` precisa ser inteiro e `data`, se informada, precisa ser data valida.

### Token ausente, invalido ou sem permissao

Origem:

```text
token_require("/acme")
```

Exception:

```text
TokenInvalido
```

Resposta:

```json
{
  "status": false,
  "erro": "Acesso negado a esta rota"
}
```

Status HTTP:

```text
401
```

### Cliente ou divida nao encontrados no fluxo CollectSys

Origem:

```text
DadosDivida.obter_dados_divida()
```

Exception:

```text
NenhumaDividaException
```

Resposta:

```json
{
  "status": true,
  "msg": "No momento, nao constam dividas ativas do cliente em nossa assessoria."
}
```

Status HTTP:

```text
200
```

### Cliente fora da assessoria no fluxo Vega

Origem:

```text
DadosDividaVega.obter_divida_vega()
```

Resposta:

```json
{
  "status": true,
  "contratos": {
    "statusCliente": "clienteForaAssessoria"
  }
}
```

Status HTTP:

```text
200
```

### Erro de calculo CollectSys

Origem:

```text
Calcular.calcular_divida()
Calcular.calcular_acordo()
Calcular.calcular_acordo_com_detalhes()
```

Dependendo do ponto, pode retornar uma mensagem dentro de `contratos` ou disparar exception.

Para `CollectSysException`, o handler retorna:

```json
{
  "status": false,
  "erro": "mensagem tratada"
}
```

Status HTTP:

```text
401
```

### Erro nao tratado

Qualquer exception nao mapeada cai no handler generico:

```text
src/presentation/error/error_http_v2.py
```

Resposta:

```json
{
  "error": "Erro interno no servidor",
  "code": 500
}
```

Status HTTP:

```text
500
```

## Exemplo de chamada Vega

```bash
curl -X GET "http://localhost:8030/acme/verifica-divida-cedente" \
  -H "Authorization: Bearer <token>" \
  -H "idCliente: 123456" \
  -H "cedente: VEGA"
```

## Exemplo de chamada demais cedentes

```bash
curl -X GET "http://localhost:8030/acme/verifica-divida-cedente" \
  -H "Authorization: Bearer <token>" \
  -H "idCliente: 123456" \
  -H "cedente: BANCO BETA" \
  -H "data: 2026-05-20"
```

## Regras importantes da rota

- A decisao entre Vega e demais cedentes depende do texto do header `cedente`.
- `cedente == "1"` tambem e tratado como Vega.
- O fluxo Vega nao chama SOAP CollectSys; consulta SQL Server e funcao `FN_CONSULTA_CLIENTE_VEGA_V2`.
- O fluxo Vega ajusta vencimento para nao cair em fim de semana ou feriado nacional.
- O fluxo nao Vega usa SOAP `ObterDividaAtiva`.
- Acordos sao consultados com `ConsultarAcordoFaturas`.
- Dividas normais recebem calculo de valor original por `CalcularDivida`.
- Proposta a vista usa `CalcularAcordo` ou `CalcularAcordoComDetalhe`, dependendo do cedente.
- Cedentes em `CEDENTES_CALCULO_DETALHE` usam `CalcularAcordoComDetalhe`.
- Banco Beta (`81`, `104`) consulta produto por `ConsultarContratoDetalhes`.
- Banco Beta cartao com atraso ate 35 dias pula desconto normal e tenta proposta a vista original pelo boleto.
- O parametro `data` so influencia o fluxo nao Vega, sendo passado para o calculo da proposta a vista.

## Dependencias externas

- SQL Server:
  - credenciais CollectSys do usuario autenticado;
  - dados Vega em `DB_PROC` e `easycollector`.
- CollectSys/EasyCollector SOAP:
  - `ObterDividaAtiva`;
  - `ConsultarAcordoFaturas`;
  - `CalcularDivida`;
  - `CalcularAcordo`;
  - `CalcularAcordoComDetalhe`;
  - `ConsultarContratoDetalhes`, para Banco Beta;
  - `EmitirBoleto`, para proposta original Banco Beta cartao ate 35 dias.

## Observacao sobre performance

No fluxo nao Vega, os calculos de valor original e proposta a vista usam `ThreadPoolExecutor(max_workers=20)` com `asyncio.gather`.

Isso permite calcular varios contratos em paralelo, mas cada chamada SOAP continua bloqueante internamente porque usa `requests.post`.
