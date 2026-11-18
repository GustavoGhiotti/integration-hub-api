# import requests
# from src.shared.utils.env_load import META_WABA_ID, META_ACCESS_TOKEN, META_API_VERSION


# class MetaStatusService:
#     def __init__(self):
#         self.base_url = f"https://graph.facebook.com/{META_API_VERSION}/{META_WABA_ID}/message_templates"

#     def consultar_status(self, nome_template: str):
 
#         params = {
#             "access_token": META_ACCESS_TOKEN,
#             "name": nome_template,
#         }

#         response = requests.get(self.base_url, params=params)
#         data = response.json()

#         if response.status_code >= 400:
#             return {
#                 "erro": True,
#                 "mensagem": data.get("error", {}).get("message"),
#             }

#         templates = data.get("data", [])
#         if not templates:
#             return {"erro": True, "mensagem": "Template não encontrado na Meta"}

#         tpl = templates[0]

#         return {
#             "erro": False,
#             "nome": tpl.get("name"),
#             "status": tpl.get("status"),
#             "categoria": tpl.get("category"),
#             "motivo_rejeicao": tpl.get("rejection_reason"),
#             "ultima_atualizacao": tpl.get("last_updated_time"),
#         }

#     def deletar(self, nome_template: str):

#         params = {
#             "access_token": META_ACCESS_TOKEN,
#             "name": nome_template,
#         }

#         response = requests.delete(self.base_url, params=params)

#         if response.status_code in (200, 204):
#             return {"deletado": True}

#         data = response.json()
#         return {
#             "deletado": False,
#             "erro": data.get("error", {}).get("message"),
#         }

#     @staticmethod
#     def atualizar_status_pela_meta(sync_service, repo):

#         templates = repo.buscar_todos_sids()

#         if not templates:
#             print("[META] Nenhum template encontrado no banco.")
#             return

#         for tpl in templates:
#             sid = tpl["SID_TEMPLATE"]
#             try:
#                 print(f"[META] Atualizando template {sid}...")
#                 sync_service.sincronizar_template_especifico(sid)
#             except Exception as e:
#                 print(f"[META ERRO] Falha ao atualizar {sid} → {e}")
