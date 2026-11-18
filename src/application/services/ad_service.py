import ldap3
from ldap3 import MODIFY_REPLACE
from ldap3.utils.conv import escape_filter_chars
from ldap3.utils.dn import escape_rdn
from src.shared.utils.env_load import *
from src.infrastructure.logging.logger_config import logging


class ActiveDirectoryService:
    def __init__(self):
        self.usuario_ad = AD_USER
        self.senha_ad = AD_PASS
        self.servidor_ad = AD_SERVER

    def conectar(self) -> ldap3.Connection:
        server = ldap3.Server(self.servidor_ad, use_ssl=True)
        conn = ldap3.Connection(server, user=self.usuario_ad, password=self.senha_ad)

        if not conn.bind():
            raise Exception("Erro ao conectar no AD")

        return conn

    def resultadoSucesso(self, conn: ldap3.Connection) -> bool:
        return conn.result.get('description') == 'success'

    def detalheResultado(self, conn: ldap3.Connection) -> str:
        return str(conn.result.get('message') or conn.result.get('description') or 'sem detalhe')

    def criarUsuario(self, dados):
        """Cria um novo usuario no AD"""
        try:
            conn = self.conectar()

            conn.add(
                f"{dados.userdn}",
                attributes={
                    'objectClass': ['user', 'posixGroup', 'top'],
                    'sn': dados.sobrenome,
                    'gidNumber': 0,
                    'givenName': dados.nmusuario,
                    'DisplayName': dados.displayname,
                    'UserPrincipalName': dados.nmlogon,
                    'SamAccountName': dados.nmlogon.replace('@GRUPO.ACME', ''),
                    'description': dados.cpf
                }
            )

            if conn.result['description'] != 'entryAlreadyExists':
                conn.modify(dados.userdn, {'userAccountControl': (MODIFY_REPLACE, [544])})
                conn.extend.microsoft.modify_password(dados.userdn, dados.senha)
                conn.modify(dados.userdn, {'pwdLastSet': (MODIFY_REPLACE, [0])})
                conn.extend.microsoft.add_members_to_groups(dados.userdn, dados.grupodn)
                conn.unbind()
                logging.info(f"Usuario {dados.displayname} criado com sucesso.")
                return {"retorno": "USUARIO CRIADO COM SUCESSO"}
            else:
                logging.warning(f"Usuario {dados.displayname} ja existente.")
                return {"erro": "USUARIO EXISTENTE"}

        except Exception as e:
            logging.error(f"Erro na criacao de usuario AD: {str(e)}")
            return {"erro": str(e)}

    def modificaUsuario(self, dados):
        """Move o usuario para o novo caminho"""
        try:
            conn = self.conectar()

            conn.modify_dn(
                dados.userdnantigo,
                dados.userdnnovo[:dados.userdnnovo.find(',')],
                new_superior=dados.userdnnovo[dados.userdnnovo.find(',')+1:]
            )

            if conn.result['description'] == 'success':
                conn.modify(dados.grupodnantigo, {
                    'member': [(ldap3.MODIFY_DELETE, [dados.userdnnovo])]
                })

                conn.extend.microsoft.add_members_to_groups(dados.userdnnovo, dados.grupodnnovo)
                conn.bind()

                logging.info(f"Usuario movimentado: {dados.userdnnovo}")
                return {
                    "status": "USUARIO MOVIMENTADO COM SUCESSO",
                    "userDnNovo": dados.userdnnovo,
                    "grupoDnNovo": dados.grupodnnovo
                }

            else:
                logging.error(f"Erro ao mover usuario: {conn.result}")
                return {"erro": "ERRO AO MOVIMENTAR COLABORADOR"}

        except Exception as e:
            logging.error(f"Erro na modificacao de usuario AD: {str(e)}")
            return {"erro": str(e)}
        
    def renomeiaUsuario(self, dados):
        """Renomeia usuario no AD localizando obrigatoriamente pelo CPF na description"""
        conn = None

        try:
            cpf = "".join(ch for ch in str(dados.cpf) if ch.isdigit())
            novo_nome = str(dados.novo_nome).strip()

            if len(cpf) != 11:
                return {"erro": "CPF INVALIDO"}

            if not novo_nome:
                return {"erro": "NOVO NOME INVALIDO"}

            conn = self.conectar()

            search_filter = f"(&(objectClass=user)(description={escape_filter_chars(cpf)}))"

            conn.search(
                search_base="DC=GRUPO,DC=ACME",
                search_filter=search_filter,
                search_scope=ldap3.SUBTREE,
                attributes=[
                    "distinguishedName",
                    "sAMAccountName",
                    "description",
                    "displayName",
                    "cn",
                    "name"
                ]
            )

            total = len(conn.entries)

            if total == 0:
                logging.error(f"Nenhum usuario encontrado para renomeacao pelo CPF {cpf}.")
                return {
                    "erro": "USUARIO NAO ENCONTRADO PELO CPF",
                    "cpf": cpf
                }

            if total > 1:
                usuarios = [str(entry.distinguishedName.value) for entry in conn.entries]
                logging.error(f"CPF duplicado no AD para renomeacao. cpf={cpf} | usuarios={usuarios}")
                return {
                    "erro": "CPF DUPLICADO NO AD",
                    "cpf": cpf,
                    "usuarios": usuarios
                }

            entry = conn.entries[0]
            dn_atual = str(entry.distinguishedName.value)
            cn_atual = str(entry.cn.value or "").strip()

            if "," not in dn_atual:
                return {
                    "erro": "DN ATUAL INVALIDO",
                    "cpf": cpf,
                    "dn_atual": dn_atual
                }

            ou_atual = dn_atual[dn_atual.find(",") + 1:]
            novo_rdn = f"CN={escape_rdn(novo_nome)}"
            novo_dn = f"CN={novo_nome},{ou_atual}"

            if cn_atual.upper() == novo_nome.upper():
                conn.modify(
                    dn_atual,
                    {
                        "displayName": (MODIFY_REPLACE, [novo_nome])
                    }
                )

                logging.info(f"Usuario ja estava com CN correto. cpf={cpf} | dn={dn_atual}")
                return {
                    "status": "USUARIO JA ESTAVA RENOMEADO",
                    "cpf": cpf,
                    "dn_atual": dn_atual,
                    "novo_dn": dn_atual
                }

            conn.modify_dn(
                dn_atual,
                novo_rdn,
                new_superior=ou_atual
            )

            resultado_renomear = dict(conn.result)

            if resultado_renomear.get("description") != "success":
                logging.error(
                    f"Falha ao renomear usuario. cpf={cpf} | dn_atual={dn_atual} | novo_dn={novo_dn} | detalhe={resultado_renomear}"
                )
                return {
                    "erro": "FALHA AO RENOMEAR USUARIO",
                    "cpf": cpf,
                    "dn_atual": dn_atual,
                    "novo_dn_tentado": novo_dn,
                    "detalhe": resultado_renomear
                }

            partes_nome = novo_nome.split()
            given_name = partes_nome[0]
            sn = " ".join(partes_nome[1:]) if len(partes_nome) > 1 else partes_nome[0]

            conn.modify(
                novo_dn,
                {
                    "displayName": (MODIFY_REPLACE, [novo_nome]),
                    "givenName": (MODIFY_REPLACE, [given_name]),
                    "sn": (MODIFY_REPLACE, [sn])
                }
            )

            resultado_atributos = dict(conn.result)

            if resultado_atributos.get("description") != "success":
                logging.warning(
                    f"Usuario renomeado, mas falhou ao atualizar atributos de nome. cpf={cpf} | novo_dn={novo_dn} | detalhe={resultado_atributos}"
                )

            logging.info(f"Usuario renomeado com sucesso. cpf={cpf} | antigo={dn_atual} | novo={novo_dn}")

            return {
                "status": "USUARIO RENOMEADO COM SUCESSO",
                "cpf": cpf,
                "dn_antigo": dn_atual,
                "novo_dn": novo_dn,
                "login": str(entry.sAMAccountName.value or "")
            }

        except Exception as e:
            logging.error(f"Erro ao renomear usuario pelo CPF {getattr(dados, 'cpf', '')}: {str(e)}")
            return {
                "erro": str(e),
                "cpf": getattr(dados, "cpf", None)
            }

        finally:
            if conn:
                conn.unbind()

    def buscarUsuarioPorCpfDescricao(self, conn: ldap3.Connection, cpf: str):
        cpf = "".join(ch for ch in str(cpf or "") if ch.isdigit())

        if len(cpf) != 11:
            return {
                "erro": "CPF INVALIDO",
                "cpf": cpf,
            }
        
        search_filter = f"(&(objectClass=user)(description={escape_filter_chars(cpf)}))"

        conn.search(
            search_base="DC=GRUPO,DC=ACME",
            search_filter=search_filter,
            search_scope=ldap3.SUBTREE,
            attributes=[
                "distinguishedName",
                "sAMAccountName",
                "description",
                "displayName",
                "cn",
                "name",
            ],
        )

        total = len(conn.entries)

        if total == 0:
            return {
                "erro": "USUARIO NAO ENCONTRADO PELO CPF",
                "cpf": cpf,
            }
        
        if total > 1:
            usuarios = [str(entry.distinguishedName.value) for entry in conn.entries]
            return {
                "erro": "CPF DUPLICADO NO AD",
                "cpf": cpf,
                "usuarios": usuarios
            }
        
        entry = conn.entries[0]

        return {
            "dn": str(entry.distinguishedName.value),
            "login": str(entry.sAMAccountName.value or ""),
            "displayName": str(entry.displayName.value or ""),
            "cn": str(entry.cn.value or ""),
        }


    def desbloquearUsuario(self, dados):
        """Desbloqueia usuario existente no Active Directory"""
        conn = None
        try:
            conn = self.conectar()

            cpf = "".join(ch for ch in str(getattr(dados, "cpf", "") or "") if ch.isdigit())

            if cpf:
                usuario_ad = self.buscarUsuarioPorCpfDescricao(conn, cpf)

                if usuario_ad.get("erro"):
                    logging.error(
                        f"Falha ao localizar usuario para desbloqueio por CPF. cpf={cpf} | detalhe={usuario_ad}"
                    )
                    return usuario_ad

                user_dn_real = usuario_ad["dn"]
                login_real = usuario_ad.get("login") or dados.nmlogon
            else:
                user_dn_real = dados.userdn
                login_real = dados.nmlogon
                logging.warning(
                    f"Desbloqueio sem CPF recebido. Usando USER_DN informado como fallback. user_dn={dados.userdn}"
                )

            conn.extend.microsoft.modify_password(user_dn_real, dados.senha)
            if not self.resultadoSucesso(conn):
                detalhe = self.detalheResultado(conn)
                logging.error(f"Erro ao redefinir senha AD para {login_real}: {detalhe}")
                return {
                    "erro": f"ERRO AO REDEFINIR SENHA: {detalhe}",
                    "cpf": cpf,
                    "userDn": user_dn_real,
                }

            conn.modify(user_dn_real, {'userAccountControl': (MODIFY_REPLACE, [544])})
            if not self.resultadoSucesso(conn):
                detalhe = self.detalheResultado(conn)
                logging.error(f"Erro ao habilitar usuario AD {login_real}: {detalhe}")
                return {
                    "erro": f"ERRO AO HABILITAR USUARIO: {detalhe}",
                    "cpf": cpf,
                    "userDn": user_dn_real,
                }

            conn.modify(user_dn_real, {'pwdLastSet': (MODIFY_REPLACE, [0])})
            if not self.resultadoSucesso(conn):
                detalhe = self.detalheResultado(conn)
                logging.error(f"Erro ao expirar senha AD para {login_real}: {detalhe}")
                return {
                    "erro": f"ERRO AO EXPIRAR SENHA: {detalhe}",
                    "cpf": cpf,
                    "userDn": user_dn_real,
                }

            logging.info(
                "Usuario desbloqueado com sucesso. login=%s solicitante=%s host=%s cpf=%s dn=%s",
                login_real,
                getattr(dados, 'login_solicitante', ''),
                getattr(dados, 'host', ''),
                cpf,
                user_dn_real,
            )
            return {
                "status": "USUARIO DESBLOQUEADO COM SUCESSO",
                "nmLogin": login_real,
                "nmColaborador": dados.displayname,
                "novaSenha": dados.senha,
                "userDn": user_dn_real,
                "cpf": cpf,
            }

        except Exception as e:
            logging.error(f"Erro no desbloqueio de usuario AD {getattr(dados, 'nmlogon', '')}: {str(e)}")
            return {"erro": str(e)}
        finally:
            if conn:
                conn.unbind()
    def desativaUsuario(self, dados):
        """Desativa usuarios movendo para a pasta de desligados"""
        conn = None

        try:
            conn = self.conectar()

            cn_name = dados.userdn.split(',')[0]
            destino_desligados = "ou=Users,ou=Desligados,DC=GRUPO,DC=ACME"
            novo_dn = f"{cn_name},{destino_desligados}"

            conn.modify(dados.userdn, {'userAccountControl': (MODIFY_REPLACE, [514])})
            resultado_desativar = dict(conn.result)

            if resultado_desativar.get("description") != "success":
                logging.error(
                    f"Falha ao desativar usuario {dados.userdn}: {resultado_desativar}"
                )
                return {
                    "error": "Falha ao desativar usuario",
                    "detalhe": resultado_desativar,
                    "user_dn": dados.userdn,
                }

            conn.modify_dn(
                dados.userdn,
                cn_name,
                new_superior=destino_desligados
            )
            resultado_mover = dict(conn.result)

            if resultado_mover.get("description") == "success":
                logging.info(f"Usuario {dados.userdn} desativado com sucesso.")
                return {
                    "status": "success",
                    "mensagem": "Usuario movido com sucesso",
                    "novo_dn": novo_dn,
                }
            
            cpf = "".join(ch for ch in str(getattr(dados, "cpf", "") or "") if ch.isdigit())

            if resultado_mover.get("description") == "entryAlreadyExists" and cpf:
                cn_alternativo = f"{cn_name} - {cpf}"
                novo_dn_alternativo = f"{cn_alternativo},{destino_desligados}"

                logging.warning(
                    f"CN ja existe em Desligados. Tentando CN alternativo. "
                    f"user_dn={dados.userdn} | novo_dn={novo_dn_alternativo}"
                )

                conn.modify_dn(
                    dados.userdn,
                    cn_alternativo,
                    new_superior=destino_desligados
                )
                resultado_mover_alternativo = dict(conn.result)

                if resultado_mover_alternativo.get("description") == "success":
                    logging.info(
                        f"Usuario {dados.userdn} desativado com CN alternativo: {novo_dn_alternativo}"
                    )
                    return {
                        "status": "success",
                        "mensagem": "Usuario movido com CN alternativo por conflito no destino",
                        "novo_dn": novo_dn_alternativo,
                    }

                logging.error(
                    f"Falha ao mover usuario com CN alternativo {dados.userdn}: {resultado_mover_alternativo}"
                )
                return {
                    "error": "Falha ao mover usuario com CN alternativo",
                    "detalhe": resultado_mover_alternativo,
                    "detalhe_primeira_tentativa": resultado_mover,
                    "user_dn": dados.userdn,
                    "novo_dn_tentado": novo_dn,
                    "novo_dn_alternativo_tentado": novo_dn_alternativo,
                }

            logging.error(f"Falha ao mover usuario {dados.userdn}: {resultado_mover}")
            return {
                "error": "Falha ao mover usuario",
                "detalhe": resultado_mover,
                "user_dn": dados.userdn,
                "novo_dn_tentado": novo_dn,
            }

        except Exception as e:
            logging.error(f"Erro ao desativar usuario {dados.userdn}: {str(e)}")
            return {
                "error": str(e),
                "user_dn": dados.userdn,
            }

        finally:
            if conn:
                conn.unbind()

