# Rota `/acme/propostas-parcelado`

Documento especifico da rota que retorna opcoes de parcelamento para um contrato de divida.

## Resumo

- Metodo: `GET`
- Endpoint: `/acme/propostas-parcelado`
- Controller: `src/presentation/controllers/collectsys.py`
- Funcao: `parcelamento`
- Autenticacao: JWT Bearer via `@token_require("/acme")`
- Entrada: headers `idCliente` e `idContrato`
- Regra principal: `NegociacaoDivida.negociacao_parcelado`
- Retorno de sucesso: JSON com `status` e `parcelamento`

## Arquivos envolvidos

```text
src/presentation/controllers/collectsys.py
src/presentation/schemas/collectsys.py
src/infrastructure/security/auth_decorator.py
src/infrastructure/repositories/sql_collectsys_repository.py
src/application/services/collectsys/negociacao_service.py
src/application/services/collectsys/valores_dividas_service.py
src/application/services/collectsys/meios_pagamentos_service.py
src/domain/entities/contrato.py
src/domain/entities/divida.py
src/domain/entities/cedentes.py
src/infrastructure/external/collectsys/providers/obter_dividas.py
src/infrastructure/external/collectsys/providers/calcular.py
src/infrastructure/external/collectsys/providers/consulta_contrato_detalhe.py
src/infrastructure/external/collectsys/providers/emitir_boleto.py
src/infrastructure/external/collectsys/providers/dados_usuario.py
src/shared/utils/xml_tratamentos.py
src/presentation/error/error_domain.py
src/presentation/error/error_collectsys.py
```

## Assinatura da rota

No arquivo `src/presentation/controllers/collectsys.py`:

```python
@bp.get("/propostas-parcelado")
@bp.arguments(PropostaParceladoSchema, location="headers")
@bp.response(200, PropostasParcelamentoResponse, description="Retorno do parcelamento da divida")
@bp.response(401, Erro401Schema, description="Retorno de erro")
@token_require("/acme")
def parcelamento(body: PropostaParceladoSchema):
    log.info(
        "parcelamento iniciado idCliente=%s idContrato=%s",
        body.idCliente,
        body.idContrato,
    )
    propostas_parceladas = asyncio.run(
        NegociacaoDivida.negociacao_parcelado(body.idCliente, body.idContrato)
    )
    log.info("parcelamento concluido idCliente=%s idContrato=%s", body.idCliente, body.idContrato)

    return jsonify({"status": True, "parcelamento": propostas_parceladas}), 200
```

## Headers esperados

### `Authorization`

Token JWT:

```text
Authorization: Bearer <token>
```

O token precisa ter permissao para a rota `"/acme"` no claim `rotas`, exceto quando o usuario autenticado tem `id_usuario == 1`.

### `idCliente`

Identificador do cliente na CollectSys/EasyCollector.

```text
idCliente: 123456
```

### `idContrato`

Identificador do contrato que sera usado para calcular as propostas.

```text
idContrato: 999999
```

### `data`

Existe no schema como campo opcional:

```python
data = fields.Date(required=False, allow_none=True)
```

Mas, no fluxo atual da rota, esse campo nao e usado pelo controller nem por `NegociacaoDivida.negociacao_parcelado`.

## Validacao de entrada

Schema:

```text
src/presentation/schemas/collectsys.py -> PropostaParceladoSchema
```

Campos:

```python
idCliente = fields.Integer(required=True)
idContrato = fields.Integer(required=True)
data = fields.Date(required=False, allow_none=True)
```

Depois da validacao, o schema retorna um `SimpleNamespace`, permitindo acesso como:

```python
body.idCliente
body.idContrato
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
7. Verifica se `"/acme"` esta em `rotas`.
8. Se nao estiver e o usuario nao for `id_usuario == 1`, dispara `TokenInvalido("Acesso negado a esta rota")`.
9. Busca as credenciais CollectSys do usuario em SQL Server:

```text
SqlCollectSysRepository(DB_66, "DB_DESENVOLVIMENTO").obter_usuario_collectsys(id_usuario)
```

10. Salva no contexto Flask:

```python
g.collectsys = UsuarioCollectSys(resultado["USUARIO"], resultado["SENHA"])
```

Essas credenciais sao usadas pelas chamadas SOAP.

## Fluxo principal

```text
Cliente HTTP
  |
  | GET /acme/propostas-parcelado
  | Headers: Authorization, idCliente, idContrato
  v
Flask / Blueprint Acme
  |
  v
PropostaParceladoSchema
  |
  | valida idCliente e idContrato como inteiros
  v
token_require("/acme")
  |
  | valida JWT
  | valida permissao
  | carrega g.collectsys
  v
parcelamento()
  |
  | NegociacaoDivida.negociacao_parcelado(idCliente, idContrato)
  v
ObterDivida("COBRANCA").consultar_por_id(idCliente)
  |
  | filtra o XML do idContrato
  v
Contrato(...).divida()
  |
  | define dados do contrato e regras por cedente
  v
Define parcelamento maximo
  |
  | regra geral, excecoes ou regra Banco Beta
  v
ValoresDividas.valores_parcelados()
  |
  | calcula propostas para 1, maximo, max/2 e max/4
  v
JSON final
```

## Etapa 1: consultar divida por `idCliente`

Metodo chamado:

```text
NegociacaoDivida.negociacao_parcelado(id_cliente, id_contrato)
```

Arquivo:

```text
src/application/services/collectsys/negociacao_service.py
```

Primeira chamada externa:

```python
dividas = ObterDivida("COBRANCA").consultar_por_id(id_cliente)
```

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

## Etapa 2: tratar cliente/divida inexistente

A resposta da CollectSys e verificada contra as mensagens:

```text
Nenhum cliente localizado com este CPFCNPJ.
O cliente nao possui divida ativa.
Cliente nao localizado.
```

Se qualquer uma aparecer, dispara:

```python
NenhumaDividaException(
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

## Etapa 3: localizar o contrato no XML

O codigo extrai do XML principal:

- `<NmCedente>` -> `nome_cedente`;
- `<IdCedente>` -> `id_cedente`.

Depois monta `xml_divida`.

### Regra para `id_cedente == 60`

Se o cedente for `60`, usa o XML completo dentro de:

```text
<ArrayOfDividaAtiva>...</ArrayOfDividaAtiva>
```

### Regra para os demais cedentes

Percorre cada bloco:

```text
<DividaAtiva>...</DividaAtiva>
```

Para cada item:

1. Extrai `<IdContrato>`.
2. Compara com `idContrato` recebido no header.
3. Se for o contrato solicitado, concatena esse bloco em `xml_divida`.
4. Remove o bloco processado do XML original e continua.

Se nenhum XML for encontrado para o contrato:

```python
raise NenhumaDividaException(
    "No momento, nao constam dividas ativas do cliente em nossa assessoria."
)
```

## Etapa 4: definir valor base do contrato

Regra atual:

```python
if id_cedente in (65, 73, 81, 104):
    valor_str = extrair_tag(xml_divida, "<ValorDividaIntegral>", "</ValorDividaIntegral>")
else:
    valor_str = "0.0"
```

Se `valor_str` estiver vazio, dispara `NenhumaDividaException`.

Depois converte:

```python
valor = float(valor_str)
```

## Etapa 5: criar entidade `Divida`

O contrato e criado assim:

```python
contrato = Contrato(xml_divida, nome_cedente, id_cedente, id_cliente, valor).divida()
```

Arquivo:

```text
src/domain/entities/contrato.py
```

`Contrato.divida()` extrai:

- `<IdContrato>`;
- `<NumeroPrestacao>`;
- `<Atraso>`.

Regras internas:

- Cedente `3`: ajusta o grupo pelo `Mu.grupo(xml)`.
- Cedentes `65` e `73`: marca todos os contratos como selecionados via `Delta.selecionar_contratos(xml)`.
- Cedentes `81` e `104`: mantem o valor recebido.
- Outros cedentes com valor: aplica `round(valor * 0.12, 2)`.
- Sem valor: usa `0.0`.
- Encapsula o XML em `<ArrayOfDividaAtiva>...</ArrayOfDividaAtiva>`.

Entidade final:

```text
src/domain/entities/divida.py -> Divida
```

Campos importantes usados nessa rota:

- `nome_cedente`;
- `id_cedente`;
- `id_cliente`;
- `id_contrato`;
- `atraso`;
- `xml`;
- `valor`;
- `parcelamento_max`, valor inicial `99`;
- `qtd_parcelas`, valor inicial `1`;
- `data_pagamento`;
- `valor_parcelas`.

## Etapa 6: definir parcelamento maximo

Variaveis iniciais:

```python
valor_min = None
valor_max = None
cartao_35 = None
```

### Cedentes comuns

Para cedentes que nao sao `33`, `14`, `81` ou `104`, chama:

```python
await ValoresDividas.obter_parcelamento_max(contrato)
```

Arquivo:

```text
src/application/services/collectsys/valores_dividas_service.py
```

Regras:

- Cedentes `65` e `73`: `parcelamento_max = 30`.
- Cedente `3`: tenta obter `<PlanoMaximo>` por `Calcular(...).obter_parcelamento_max()`.
- Demais cedentes:
  - testa inicialmente as parcelas `10`, `20` e `30`;
  - chama `CalcularAcordo` ou `CalcularAcordoComDetalhe`;
  - considera sucesso quando nao ha `<RetornoErro>`;
  - se todos funcionarem, testa faixas maiores ate o limite;
  - depois refina o intervalo restante em paralelo;
  - limita o maximo em `36`.

Observacao tecnica:

- No arquivo atual `src/infrastructure/external/collectsys/providers/calcular.py`, nao foi encontrado o metodo `obter_parcelamento_max()`, embora `ValoresDividas.obter_parcelamento_max()` chame esse metodo para o cedente `3`. Se essa rota cair nesse caminho, existe risco de erro em tempo de execucao, a menos que o metodo venha de alguma alteracao nao versionada ou outro mecanismo externo.

### Cedentes `33` e `14`

Nao calcula parcelamento maximo.

Regra:

```python
contrato.parcelamento_max = 1
```

Ou seja, a rota tende a retornar apenas proposta a vista.

### Banco Beta: cedentes `81` e `104`

Fluxo especifico:

1. Cria um `Calcular` com:

```python
plano = min(contrato.parcelamento_max, 36)
```

2. Consulta o nome do produto:

```python
nm_produto = ConsultaContratoDetalhe(id_cliente, id_contrato).consultar_nm_produto()
```

Provider:

```text
src/infrastructure/external/collectsys/providers/consulta_contrato_detalhe.py
```

Operacao SOAP:

```text
ConsultarContratoDetalhes
```

3. Extrai atraso do XML:

```python
atraso = int(extrair_tag(xml_divida, "<Atraso>", "</Atraso>"))
```

4. Se o produto for cartao e atraso for ate 35 dias:

```python
cartao_35 = "SIM"
```

Produto de cartao e definido por `BancoBeta.eh_produto_cartao(nome_produto)`:

- precisa conter `CARTAO`;
- nao pode conter `RENEG`;
- nao pode conter `EMPRESTIMO`.

5. Chama:

```python
calcular_acordo_com_detalhes(
    parcelado="VALOR ENTRADA",
    cartao_35=cartao_35,
)
```

6. O retorno esperado e uma tupla com 5 posicoes:

```text
(valor_min, valor_max, parcela_min, parcela_max, cartao_35)
```

7. Se nao vier uma tupla com 5 itens, dispara:

```python
CollectSysException(mensagem=str(retorno_parcelamento))
```

8. Atualiza:

```python
contrato.parcelamento_max = parcela_max
contrato.valor = valor_max
```

## Etapa 7: calcular propostas parceladas

Depois do parcelamento maximo:

```python
contratos_parcelados = await ValoresDividas.valores_parcelados(
    contrato,
    valor_min,
    valor_max,
    cartao_35
)
```

### Metodo usado

Arquivo:

```text
src/application/services/collectsys/valores_dividas_service.py
```

Metodo:

```text
ValoresDividas.valores_parcelados()
```

### Escolha do metodo de calculo

Se o cedente estiver em `CEDENTES_CALCULO_DETALHE`, usa:

```text
Calcular.calcular_acordo_com_detalhes()
```

Caso contrario, usa:

```text
Calcular.calcular_acordo()
```

Cedentes com calculo por detalhe:

```text
(60, 65, 51, 73, 64, 70, 71, 83, 90, 81, 77, 103, 104)
```

### Quantidades de parcelas testadas

A rota nao retorna todas as parcelas possiveis. Ela monta um conjunto de opcoes:

1. Sempre inclui `1`.
2. Inclui `contrato.parcelamento_max`, se for maior ou igual a `1`.
3. Inclui metade do parcelamento maximo:

```python
contrato.parcelamento_div2()
```

4. Inclui um quarto do parcelamento maximo:

```python
contrato.parcelamento_div4()
```

5. Remove duplicidades com `set`.
6. Ordena as parcelas em ordem crescente.

Exemplo:

```text
parcelamento_max = 30
opcoes testadas = [1, 7, 15, 30]
```

Porque `int(30 / 4) = 7` e `int(30 / 2) = 15`.

### Regra Banco Beta cartao ate 35 dias

Se:

```python
contrato.id_cedente in (81, 104) and cartao_35 == "SIM"
```

As parcelas ficam restritas a:

```text
1, 4, 5
```

Desde que respeitem o `parcelamento_max`.

### Valor de entrada para Banco Beta

Para cedentes `81` e `104`, o valor de entrada e calculado por:

```python
BancoBeta.valor_entrada(contrato.xml, parcelas, valor_min, valor_max)
```

Regra:

- parcelas `21` a `36`: divide `valor_max` por `9`;
- parcelas `11` a `20`: divide por `7`;
- parcelas `5` a `10`: divide por `5`;
- parcelas `2` a `4`: divide por `2`;
- parcela `1`: divide por `1`;
- se a entrada ficar menor que `50`, usa `50`;
- retorna com duas casas decimais.

## Etapa 8: chamada SOAP de calculo

Para cada quantidade de parcelas escolhida, a rota cria uma tarefa no executor:

```python
_run_calc(lambda: metodo_calculo(...))
```

O executor e:

```python
ThreadPoolExecutor(max_workers=20)
```

Isso permite calcular varias opcoes em paralelo.

### `CalcularAcordo`

Usado para cedentes fora de `CEDENTES_CALCULO_DETALHE`.

Provider:

```text
src/infrastructure/external/collectsys/providers/calcular.py
```

Operacao SOAP:

```text
CalcularAcordo
```

Regras importantes:

- desconto `199` para cedente `3`;
- desconto `100` para os demais;
- se nao houver vencimento, usa `date.today() + 7 dias`;
- valida/procura dia util via `validacao_dia_util`;
- tenta tratar erros de data, desconto maximo e valor;
- se estiver em fluxo parcelado e nao houver tratativa aplicavel, retorna o erro.

### `CalcularAcordoComDetalhe`

Usado para cedentes em `CEDENTES_CALCULO_DETALHE`.

Operacao SOAP:

```text
CalcularAcordoComDetalhe
```

Regras importantes:

- Usa `get_cedente_rule(id_cedente)` para montar XML de detalhe e tratar retorno.
- Passa contexto com produto, parcelado, `cartao_35`, plano, valor de entrada, desconto e XML da divida.
- Para Banco Beta com `parcelado="VALOR ENTRADA"`, pode retornar a tupla de limites de entrada e parcelas.
- Tenta ate 5 vezes antes de finalizar falha ou retornar erro no fluxo parcelado.

## Etapa 9: montar objetos `Divida` com propostas validas

Depois que todas as chamadas retornam, `valores_parcelados()` analisa cada resultado.

### Data base

Antes de montar as propostas, busca uma data base:

- prefere a primeira `<DataParcela>` de uma proposta com mais de 1 parcela;
- se nao houver, usa a primeira data encontrada.

Essa data e aplicada nas propostas para padronizar `dataPagamento`.

### Proposta Banco Beta cartao ate 35 dias a vista

Se:

```python
id_cedente in (81, 104)
cartao_35 == "SIM"
qtd_parcelas == 1
```

Nao usa o resultado normal do `CalcularAcordoComDetalhe`.

Em vez disso, chama:

```python
ValoresDividas.proposta_avista_cartao_35(contrato_copia)
```

Essa regra:

1. Busca boleto original:

```python
Boleto.obter_original_por_divida_parcelado(...)
```

2. Chama `EmitirBoleto(...).emitir_original(contrato.xml)`.
3. Extrai `<VALOR_DOCUMENTO>`.
4. Define `dataPagamento = date.today() + 1 dia`.
5. Retorna `valorEntrada`, `dataPagamento` e `boleto`.

Se nao encontrar valor do documento, descarta essa proposta.

### Descarte de propostas invalidas

Uma proposta e descartada se:

- o XML contem `<RetornoErro>`;
- ou nao contem `<ParcelaAcordo>`.

O descarte e registrado no logger `collectsys_parcelado_debug`.

### Extracao dos valores

Para proposta valida:

1. Extrai o primeiro bloco `<ParcelaAcordo>`.
2. Pega `<ValorParcela>` como `valorEntrada`.
3. Se tiver mais de 1 parcela:
   - remove o primeiro bloco;
   - extrai o proximo `<ParcelaAcordo>`;
   - pega `<ValorParcela>` como `valorParcelas`.
4. Atualiza a copia do contrato:

```python
contrato_copia.atualizar_valores(
    valor,
    valor_parcelas,
    contrato.parcelamento_max,
    qtd_parcelas
)
```

5. Atualiza a data com `contrato_copia.atualizar_data(data_base)`.

### Ajuste final de parcelamento maximo

Se ao menos uma proposta foi aceita:

```python
max_qtd = max(c.qtd_parcelas for c in contratos)
for c in contratos:
    c.parcelamento_max = max_qtd
```

Ou seja, o `parcelamentoMax` retornado na resposta e o maior plano realmente aceito entre as propostas calculadas, nao necessariamente o maximo descoberto antes.

## Etapa 10: montar resposta final

Se `contratos_parcelados == []`, retorna:

```python
{
    "nomeCedente": nome_cedente,
    "idCliente": id_cliente,
    "idCedente": id_cedente,
    "propostas": "Nao a propostas no momento"
}
```

Se for Banco Beta (`81` ou `104`), tambem inclui:

```python
"produto": nm_produto
```

Se houver propostas, monta:

```python
{
    "valorEntrada": contrato_parcela.valor,
    "valorParcelas": contrato_parcela.valor_parcelas,
    "qtdParcelas": contrato_parcela.qtd_parcelas,
    "parcelamentoMax": contrato_parcela.parcelamento_max,
    "dataPagamento": contrato_parcela.data_pagamento
}
```

Se a proposta tiver boleto, inclui:

```python
"boleto": contrato_parcela.boleto
```

Se for Banco Beta, adiciona detalhes por:

```python
BancoBeta.detalhe_proposta(nm_produto, qtd_parcelas, cartao_35)
```

Regras do detalhe:

- Produto cartao, `cartao_35 == "SIM"` e parcela `1`: nao adiciona detalhe.
- Produto cartao e parcela `1`: `"Somente parcelas em atraso a vista."`
- Produto cartao e parcelado: `"Parcelamento das faturas em atraso."`
- Outros produtos Banco Beta: `"Renegociacao."`

Resposta final:

```python
{
    "nomeCedente": nome_cedente,
    "idCliente": id_cliente,
    "idCedente": id_cedente,
    "propostas": propostas_parcelamento
}
```

Se for Banco Beta:

```python
"produto": nm_produto
```

O controller embrulha em:

```python
{
    "status": True,
    "parcelamento": propostas_parceladas
}
```

## Exemplo de resposta

```json
{
  "status": true,
  "parcelamento": {
    "nomeCedente": "BANCO BETA",
    "idCliente": 123456,
    "idCedente": 81,
    "produto": "CARTAO EXEMPLO",
    "propostas": [
      {
        "valorEntrada": 100.0,
        "valorParcelas": 0.0,
        "qtdParcelas": 1,
        "parcelamentoMax": 5,
        "dataPagamento": "2026-05-15",
        "boleto": {
          "nomeBoleto": "boleto.pdf",
          "urlBoleto": "/arquivos/boletos/boleto.pdf",
          "linhaDigitavel": "..."
        }
      },
      {
        "valorEntrada": 120.0,
        "valorParcelas": 80.0,
        "qtdParcelas": 5,
        "parcelamentoMax": 5,
        "dataPagamento": "2026-05-20",
        "detalhe": "Parcelamento das faturas em atraso."
      }
    ]
  }
}
```

## Erros e respostas tratadas

### Header obrigatorio ausente ou invalido

Origem:

```text
PropostaParceladoSchema
```

Como `idCliente` e `idContrato` sao obrigatorios e inteiros, erros de validacao caem no tratamento HTTP/Marshmallow configurado pela aplicacao.

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

### Cliente, contrato ou divida nao encontrados

Origem:

```text
NegociacaoDivida.negociacao_parcelado()
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

### Erro de calculo CollectSys

Origem:

```text
Calcular.calcular_acordo()
Calcular.calcular_acordo_com_detalhes()
NegociacaoDivida.negociacao_parcelado()
```

Exception:

```text
CollectSysException
```

Resposta:

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

### Erro de formalizacao/calculo especifico

Em algumas regras de parcelamento maximo, pode ocorrer:

```text
ErroFormalizarAcordo
```

Resposta:

```json
{
  "status": false,
  "erro": "mensagem"
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

## Exemplo de chamada

```bash
curl -X GET "http://localhost:8030/acme/propostas-parcelado" \
  -H "Authorization: Bearer <token>" \
  -H "idCliente: 123456" \
  -H "idContrato: 999999"
```

## Regras importantes da rota

- A rota consulta somente o servidor de cobranca: `ObterDivida("COBRANCA")`.
- A rota trabalha com um contrato especifico, filtrado por `idContrato`.
- A rota retorna algumas opcoes de parcelamento, nao todas as possibilidades.
- As opcoes padrao sao: a vista, maximo, metade do maximo e um quarto do maximo.
- Cedentes em `CEDENTES_CALCULO_DETALHE` usam `CalcularAcordoComDetalhe`.
- Demais cedentes usam `CalcularAcordo`.
- Cedentes `33` e `14` sao tratados como proposta a vista.
- Cedentes `65` e `73` fixam `parcelamento_max = 30`.
- Cedentes `81` e `104` possuem fluxo especial Banco Beta, com consulta de produto e valor de entrada calculado.
- Banco Beta cartao com atraso ate 35 dias restringe opcoes para `1`, `4` e `5` parcelas.
- Propostas com `<RetornoErro>` ou sem `<ParcelaAcordo>` sao descartadas.
- Se nenhuma proposta for aceita, a rota retorna `"Nao a propostas no momento"` dentro de `propostas`.
- O campo opcional `data` existe no schema, mas nao e usado por esta rota atualmente.

## Dependencias externas

- SQL Server:
  - busca credenciais CollectSys do usuario autenticado.
- CollectSys/EasyCollector SOAP:
  - `ObterDividaAtiva`;
  - `CalcularAcordo`;
  - `CalcularAcordoComDetalhe`;
  - `ConsultarContratoDetalhes`, para Banco Beta;
  - `EmitirBoleto`, para proposta a vista original de cartao Banco Beta ate 35 dias.

## Observacao sobre performance

O calculo das propostas usa `ThreadPoolExecutor(max_workers=20)` e `asyncio.gather` para executar varias simulacoes de parcelas em paralelo.

Isso acelera o retorno quando ha varias tentativas de plano, mas cada chamada SOAP continua bloqueante internamente, pois usa `requests.post`.
