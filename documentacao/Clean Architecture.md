## Objetivo

Clean Code é a prática de escrever código claro, simples, legível, testável e fácil de manter.

O código deve comunicar intenção, reduzir ambiguidade e facilitar evolução sem gerar medo de alterar o sistema.

---

## Princípios Gerais

### 1. Código deve ser lido como texto

Código é lido muito mais vezes do que é escrito.  
Priorize clareza antes de truques técnicos.

### Evite

```python
x = u.a and u.b
r = calc(u) if x else None
```

### Prefira

```python
user_has_permission = user.is_active and user.has_profile

result = calculate_result(user) if user_has_permission else None
```

---

## Nomes Claros

### Regras

- Use nomes que revelem intenção.
- Evite abreviações sem contexto.
- Nomes devem explicar o significado da informação.
- Variáveis booleanas devem parecer perguntas.
- Em Python, prefira `snake_case` para variáveis e funções.

### Evite

```python
x = True
usr = {}
data = []
```

### Prefira

```python
is_payment_approved = True
authenticated_user = {}
pending_invoices = []
```

---

## Funções

### Regras

- Funções devem fazer uma única coisa.
- Devem ter nomes claros.
- Devem ser pequenas.
- Evite muitos parâmetros.
- Prefira retornos antecipados para evitar muitos níveis de indentação.

### Exemplo ruim

```python
def process(user):
    if user:
        if user.is_active:
            if user.email:
                send_email(user.email)
```

### Exemplo melhor

```python
def notify_active_user(user):
    if not user:
        return

    if not user.is_active:
        return

    if not user.email:
        return

    send_email(user.email)
```

---

## Responsabilidade Única

Cada função, classe ou módulo deve ter uma responsabilidade clara.

### Ruim

```python
class UserService:
    def create_user(self):
        pass

    def send_email(self):
        pass

    def generate_report(self):
        pass

    def export_pdf(self):
        pass
```

### Melhor

```python
class UserService:
    def create_user(self):
        pass


class EmailService:
    def send_email(self):
        pass


class ReportService:
    def generate_report(self):
        pass


class PdfExporter:
    def export(self):
        pass
```

---

## Comentários

Comentários não devem explicar código confuso.  
Primeiro tente melhorar o código. Comente apenas decisões importantes, regras de negócio ou limitações técnicas.

### Evite

```python
# Verifica se o usuário está ativo
if user.is_active:
    pass
```

### Prefira

```python
# Regra de negócio: usuários inativos não podem receber cobranças automáticas
if not user.is_active:
    return
```

---

## Tratamento de Erros

### Regras

- Erros devem ser explícitos.
- Não esconda exceções.
- Use mensagens úteis.
- Evite retornar `None` sem contexto.
- Crie exceções de domínio quando necessário.

### Exemplo

```python
class UserNotFoundError(Exception):
    pass


def get_user_or_fail(user_id):
    user = user_repository.find_by_id(user_id)

    if user is None:
        raise UserNotFoundError(f"Usuário não encontrado para o ID {user_id}")

    return user
```

---

## Estrutura de Código

### Organização recomendada

```txt
src/
  modules/
    users/
      controllers/
      services/
      repositories/
      entities/
      schemas/
      tests/
  shared/
    errors/
    utils/
    database/
    middlewares/
```

### Regras

- Separe regra de negócio de infraestrutura.
- Controllers ou rotas não devem conter regra de negócio pesada.
- Services coordenam casos de uso.
- Repositories acessam dados.
- Entities representam conceitos do domínio.
- Schemas validam entrada e saída de dados.

---

## Padrões de Arquitetura

## Controller / Route

Responsável por receber a requisição, validar entrada básica e chamar o caso de uso.

```python
from fastapi import APIRouter, status

router = APIRouter()


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(payload: dict):
    user = create_user_service.execute(payload)

    return user
```

---

## Service / Use Case

Responsável pela regra de negócio.

```python
class EmailAlreadyInUseError(Exception):
    pass


class CreateUserService:
    def __init__(self, user_repository):
        self.user_repository = user_repository

    def execute(self, data):
        user_already_exists = self.user_repository.find_by_email(data["email"])

        if user_already_exists:
            raise EmailAlreadyInUseError("E-mail já está em uso")

        return self.user_repository.create(data)
```

---

## Repository

Responsável pela comunicação com banco de dados.

```python
class UserRepository:
    def find_by_email(self, email: str):
        pass

    def find_by_id(self, user_id: int):
        pass

    def create(self, data: dict):
        pass
```

---

## Schema / DTO

Define o formato dos dados trafegados entre camadas.

```python
from pydantic import BaseModel, EmailStr


class CreateUserSchema(BaseModel):
    name: str
    email: EmailStr
    password: str
```

---

## Boas Práticas

## Evite código duplicado

Se uma regra aparece várias vezes, extraia para função, service ou helper.

```python
def calculate_discount(price: float, percentage: float) -> float:
    return price * (percentage / 100)
```

---

## Evite números mágicos

### Ruim

```python
if attempts > 3:
    block_user()
```

### Melhor

```python
MAX_LOGIN_ATTEMPTS = 3

if attempts > MAX_LOGIN_ATTEMPTS:
    block_user()
```

---

## Prefira código explícito

### Ruim

```python
return user.status == 1
```

### Melhor

```python
USER_STATUS_ACTIVE = 1

return user.status == USER_STATUS_ACTIVE
```

Ou melhor ainda:

```python
from enum import Enum


class UserStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


return user.status == UserStatus.ACTIVE
```

---

## Testabilidade

Código limpo é fácil de testar.

### Regras

- Evite dependências globais.
- Injete dependências externas.
- Separe regra de negócio de framework.
- Teste comportamento, não implementação interna.

```python
class CreateUserService:
    def __init__(self, user_repository):
        self.user_repository = user_repository

    def execute(self, data):
        return self.user_repository.create(data)
```

### Exemplo de teste

```python
class FakeUserRepository:
    def create(self, data):
        return {
            "id": 1,
            **data,
        }


def test_should_create_user():
    repository = FakeUserRepository()
    service = CreateUserService(repository)

    user = service.execute({
        "name": "Ana",
        "email": "ana@email.com",
    })

    assert user["id"] == 1
    assert user["email"] == "ana@email.com"
```

---

## SOLID em Python

## S — Single Responsibility Principle

Uma classe deve ter apenas um motivo para mudar.

### Exemplo

```python
class InvoiceCalculator:
    def calculate_total(self, items):
        return sum(item.price for item in items)


class InvoiceRepository:
    def save(self, invoice):
        pass
```

---

## O — Open/Closed Principle

O código deve estar aberto para extensão e fechado para modificação.

### Ruim

```python
def calculate_discount(customer_type, price):
    if customer_type == "regular":
        return price * 0.05

    if customer_type == "premium":
        return price * 0.10

    return 0
```

### Melhor

```python
class DiscountStrategy:
    def calculate(self, price):
        raise NotImplementedError


class RegularDiscount(DiscountStrategy):
    def calculate(self, price):
        return price * 0.05


class PremiumDiscount(DiscountStrategy):
    def calculate(self, price):
        return price * 0.10


def calculate_discount(strategy: DiscountStrategy, price: float):
    return strategy.calculate(price)
```

---

## D — Dependency Inversion Principle

Dependa de abstrações, não de implementações concretas.

```python
from typing import Protocol


class UserRepositoryProtocol(Protocol):
    def create(self, data: dict) -> dict:
        ...


class CreateUserService:
    def __init__(self, user_repository: UserRepositoryProtocol):
        self.user_repository = user_repository

    def execute(self, data: dict) -> dict:
        return self.user_repository.create(data)
```

---

## Checklist de Clean Code

Antes de finalizar uma tarefa, revise:

- Os nomes deixam clara a intenção?
- A função faz apenas uma coisa?
- Existe código duplicado?
- Existem números mágicos?
- O código está fácil de testar?
- A regra de negócio está separada da infraestrutura?
- Existem comentários desnecessários?
- Os erros são claros?
- O código está simples ou complexo demais?
- Outro desenvolvedor entenderia isso rapidamente?

---

## Padrão Mental

> Código bom não é o que apenas funciona.  
> Código bom é o que continua funcionando mesmo depois de crescer, mudar e ser mantido por outras pessoas.

---

## Regra Final

Sempre escreva código pensando no próximo desenvolvedor que vai manter o sistema.

Esse próximo desenvolvedor pode ser você no futuro.

