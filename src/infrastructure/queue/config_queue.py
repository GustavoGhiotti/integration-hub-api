from queue import Queue, Empty
import threading
import time
from src.application.services.infobip_service import SmsService     

sms_queue = Queue()
NUM_WORKERS = 3 
BATCH_SIZE = 40        # pega até 40 de uma vez
WAIT_FIRST = 1.0       # espera até 1s pelo primeiro item
WAIT_BATCH = 0.05      # tenta acumular o resto sem travar


def worker_loop():
    while True:
        batch = []

        try:
            # Bloqueia até ter pelo menos um item
            job = sms_queue.get(timeout=WAIT_FIRST)
            batch.append(job)
        except Empty:
            continue

        # Agora tenta pegar mais itens rapidamente
        start_time = time.time()

        while len(batch) < BATCH_SIZE:
            try:
                job = sms_queue.get_nowait()
                batch.append(job)
            except Empty:
                break

            # Tempo limite para acumular lote
            if time.time() - start_time > WAIT_BATCH:
                break

        # Lote pronto → processa tudo de uma vez
        try:
            SmsService.processar_batch(batch)
        except Exception as e:
            pass

def start_workers():
    for _ in range(NUM_WORKERS):
        t = threading.Thread(target=worker_loop, daemon=True)
        t.start()
