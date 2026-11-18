from src.application.services.twilio_service import TwilioTemplateSyncService
from src.infrastructure.repositories.sql_template_repository import TemplateRepository
# from src.application.services.meta_service import *
import threading
import time
from datetime import datetime


def iniciar_template_scheduler():
    thread = threading.Thread(target=_loop_sincronizacao, daemon=True)
    thread.start()


def _loop_sincronizacao():
    repo = TemplateRepository()
    sync = TwilioTemplateSyncService()


    while True:
        agora = datetime.now()

        if agora.minute % 1 == 0:
            try:
                sync = TwilioTemplateSyncService()

                twilio_resultado = sync.sincronizar_ultimos_7_dias()

                # MetaStatusService.atualizar_status_pela_meta(sync, repo)


            except Exception as e:
                print("[SCHEDULER ERRO] →", e)

            time.sleep(60)

        time.sleep(5)

