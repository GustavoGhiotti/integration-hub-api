from marshmallow import Schema, fields, validate, post_load
from types import SimpleNamespace


class ActiveDirectoryCriaSchema(Schema):
    nmusuario = fields.String(
        required=True,
        validate=validate.Length(min=1),
        data_key="nmUsuario"
    )
    sobrenome = fields.String(
        required=True,
        validate=validate.Length(min=1),
        data_key="sobreNome"
    )
    displayname = fields.String(
        required=True,
        validate=validate.Length(min=1),
        data_key="displayName"
    )
    nmlogon = fields.String(
        required=True,
        validate=validate.Length(min=1),
        data_key="nmLogon"
    )
    senha = fields.String(
        required=True,
        validate=validate.Length(min=1)
    )
    userdn = fields.String(
        required=True,
        validate=validate.Length(min=1),
        data_key="userDn"
    )
    grupodn = fields.String(
        required=True,
        validate=validate.Length(min=1),
        data_key="grupoDn"
    )
    cpf = fields.String(
        required=True,
        validate=[
            validate.Length(equal=11),
            validate.Regexp(r"^\d{11}$", error="CPF deve conter 11 digitos")
        ],
        data_key="cpf"
    )

    @post_load
    def makeObj(self, data, **kwargs):
        return SimpleNamespace(**data)


class ActiveDirectoryModifySchema(Schema):
    userdnantigo = fields.String(
        required=True,
        validate=validate.Length(min=1),
        data_key="userDnAntigo"
    )
    grupodnantigo = fields.String(
        required=True,
        validate=validate.Length(min=1),
        data_key="grupoDnAntigo"
    )
    userdnnovo = fields.String(
        required=True,
        validate=validate.Length(min=1),
        data_key="userDnNovo"
    )
    grupodnnovo = fields.String(
        required=True,
        validate=validate.Length(min=1),
        data_key="grupoDnNovo"
    )

    @post_load
    def makeObj(self, data, **kwargs):
        return SimpleNamespace(**data)


class ActiveDirectoryUnlockSchema(Schema):
    userdn = fields.String(
        required=True,
        validate=validate.Length(min=1),
        data_key="userDn"
    )
    nmlogon = fields.String(
        required=True,
        validate=validate.Length(min=1),
        data_key="nmLogin"
    )
    displayname = fields.String(
        required=True,
        validate=validate.Length(min=1),
        data_key="nmColaborador"
    )
    senha = fields.String(
        required=True,
        validate=validate.Length(min=1)
    )
    cpf = fields.String(
        required=False,
        allow_none=True,
        validate=validate.Regexp(r"^\d{11}$", error="CPF deve conter 11 digitos"),
        data_key="cpf"
    )
    login_solicitante = fields.String(
        required=False,
        allow_none=True,
        data_key="loginSolicitante"
    )
    host = fields.String(
        required=False,
        allow_none=True,
        data_key="host"
    )

    @post_load
    def makeObj(self, data, **kwargs):
        return SimpleNamespace(**data)


class ActiveDirectoryDisableSchema(Schema):
    userdn = fields.String(
        required=True,
        validate=validate.Length(min=1),
        data_key="userDn"
    )
    cpf = fields.String(
        required=False,
        allow_none=True,
        validate=validate.Regexp(r"^\d{11}$", error="CPF deve conter 11 digitos"),
        data_key="cpf"
    )

    @post_load
    def makeObj(self, data, **kwargs):
        return SimpleNamespace(**data)


class ActiveDirectoryRenameSchema(Schema):
    cpf = fields.String(
        required=True,
        validate=[
            validate.Length(equal=11),
            validate.Regexp(r"^\d{11}$", error="CPF deve conter 11 digitos")
        ],
        data_key="cpf"
    )
    novo_nome = fields.String(
        required=True,
        validate=validate.Length(min=1),
        data_key="novoNome"
    )
    userdn_atual = fields.String(
        required=False,
        allow_none=True,
        data_key="userDnAtual"
    )

    @post_load
    def makeObj(self, data, **kwargs):
        return SimpleNamespace(**data)