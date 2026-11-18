from flask import Blueprint, jsonify
from src.shared.utils.validador import validate_input
from src.application.services.ad_service import ActiveDirectoryService
from src.presentation.schemas.active_directory import (
    ActiveDirectoryCriaSchema,
    ActiveDirectoryDisableSchema,
    ActiveDirectoryModifySchema,
    ActiveDirectoryUnlockSchema,
    ActiveDirectoryRenameSchema,
)
from src.infrastructure.security.auth_decorator import token_require


bp = Blueprint("ad", __name__, url_prefix="/ad")


@bp.post("/criacaoUsuarios")
@token_require("/ad")
@validate_input(ActiveDirectoryCriaSchema, "json")
def criarUsuario(dados: ActiveDirectoryCriaSchema):
    """Cria um novo usuario no AD"""
    service = ActiveDirectoryService()
    resultado = service.criarUsuario(dados)

    status_text = (
        (resultado.get("status") or resultado.get("retorno") or resultado.get("erro") or "").lower()
    )
    sucesso = any(palavra in status_text for palavra in ["sucesso", "success", "criado"])

    status_code = 200 if sucesso else 400
    return jsonify(resultado), status_code


@bp.post("/modificaUsuarios")
@token_require("/ad")
@validate_input(ActiveDirectoryModifySchema, "json")
def modificaUsuario(dados: ActiveDirectoryModifySchema):
    """Move usuarios dentro do AD"""
    service = ActiveDirectoryService()
    resultado = service.modificaUsuario(dados)
    status_text = (
        (resultado.get("status") or resultado.get("retorno") or resultado.get("erro") or "").lower()
    )
    sucesso = any(palavra in status_text for palavra in ["sucesso", "success", "criado"])
    status_code = 200 if sucesso else 400
    return jsonify(resultado), status_code


@bp.post("/desbloqueiaUsuario")
@token_require("/ad")
@validate_input(ActiveDirectoryUnlockSchema, "json")
def desbloqueiaUsuario(dados: ActiveDirectoryUnlockSchema):
    """Desbloqueia usuario existente no Active Directory"""
    service = ActiveDirectoryService()
    resultado = service.desbloquearUsuario(dados)
    status_text = (
        (resultado.get("status") or resultado.get("retorno") or resultado.get("erro") or "").lower()
    )
    sucesso = any(palavra in status_text for palavra in ["sucesso", "success", "desbloqueado"])
    status_code = 200 if sucesso else 400
    return jsonify(resultado), status_code


@bp.post("/desativaUsuario")
@token_require("/ad")
@validate_input(ActiveDirectoryDisableSchema, "json")
def desativaUsuario(dados: ActiveDirectoryDisableSchema):
    """Desativa um usuario e move para Desligados"""
    service = ActiveDirectoryService()
    resultado = service.desativaUsuario(dados)
    print(resultado)
    status_text = resultado.get("status", "").lower()
    sucesso = "sucesso" in status_text or "success" in status_text

    status_code = 200 if sucesso else 400
    return jsonify(resultado), status_code


@bp.post("/renomeiaUsuario")
@token_require("/ad")
@validate_input(ActiveDirectoryRenameSchema, "json")
def renomeiaUsuario(dados: ActiveDirectoryRenameSchema):
    """Renomeia usuario no AD localizando obrigatoriamente pelo CPF na description"""
    service = ActiveDirectoryService()
    resultado = service.renomeiaUsuario(dados)

    status_text = (
        (resultado.get("status") or resultado.get("retorno") or resultado.get("erro") or resultado.get("error") or "").lower()
    )
    sucesso = any(palavra in status_text for palavra in ["sucesso", "success", "ja estava"])

    status_code = 200 if sucesso else 400
    return jsonify(resultado), status_code