"""
Cola asincrona para mensajes de WhatsApp.
Evita bloqueos por spam enviando mensajes con delays aleatorios.
"""

import logging
import queue
import random
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

from adm.functions.whatsapp_delivery_log import append_whatsapp_delivery_log


logger = logging.getLogger(__name__)


@dataclass
class WhatsAppMessage:
    message: str
    lada: str
    phone_number: str
    event_id: str
    metadata: Dict


class WhatsAppQueue:
    """
    Cola asincrona para enviar mensajes de WhatsApp.

    - Envia mensajes en un hilo separado.
    - Aplica delay entre mensajes para evitar bloqueos por spam.
    - Persiste logs de cola/envio/error para diagnostico web.
    """

    _instance: Optional["WhatsAppQueue"] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._queue: queue.Queue[WhatsAppMessage] = queue.Queue()
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._min_delay = 180
        self._max_delay = 300
        self._same_recipient_delay = 3
        self._last_send_time: Optional[datetime] = None
        self._last_recipient: Optional[str] = None
        self._send_lock = threading.Lock()
        self._initialized = True
        logger.info("WhatsAppQueue inicializada")

    def _wait_for_rate_limit(self, current_recipient: str):
        with self._send_lock:
            if self._last_send_time is None:
                return

            elapsed = (datetime.now() - self._last_send_time).total_seconds()
            if self._last_recipient and self._last_recipient == current_recipient:
                required_delay = float(self._same_recipient_delay)
            else:
                required_delay = random.uniform(self._min_delay, self._max_delay)

            if elapsed >= required_delay:
                return

            wait_time = required_delay - elapsed
            logger.info(
                "Rate limit WhatsApp: esperando %.1fs mas (elapsed %.1fs, required %.1fs)",
                wait_time,
                elapsed,
                required_delay,
            )
            waited = 0
            while waited < wait_time and not self._stop_event.is_set():
                time.sleep(0.5)
                waited += 0.5

    def _update_last_send_time(self, recipient: str):
        with self._send_lock:
            self._last_send_time = datetime.now()
            self._last_recipient = recipient

    def _worker(self):
        from adm.functions.send_whatsapp_notification import Notification

        logger.info("WhatsApp Queue Worker iniciado")
        messages_sent = 0

        while not self._stop_event.is_set() or not self._queue.empty():
            try:
                try:
                    msg = self._queue.get(timeout=1)
                except queue.Empty:
                    continue

                current_recipient = Notification.format_whatsapp_number(msg.lada, msg.phone_number)
                if messages_sent > 0:
                    self._wait_for_rate_limit(current_recipient)

                try:
                    append_whatsapp_delivery_log({
                        "event_id": msg.event_id,
                        "event": "sending",
                        "level": "info",
                        "message": "Intentando enviar WhatsApp por Evolution API.",
                        "lada": msg.lada,
                        "phone_number": msg.phone_number,
                        "full_phone": current_recipient,
                        "queue_remaining": self._queue.qsize(),
                        "metadata": msg.metadata,
                    })
                    result = Notification.send_whatsapp_notification_details(
                        msg.message,
                        msg.lada,
                        msg.phone_number,
                    )
                    self._update_last_send_time(current_recipient)

                    if result.get("success"):
                        messages_sent += 1
                        append_whatsapp_delivery_log({
                            "event_id": msg.event_id,
                            "event": "sent",
                            "level": "success",
                            "message": "Evolution API acepto el WhatsApp.",
                            "lada": msg.lada,
                            "phone_number": msg.phone_number,
                            "full_phone": result.get("full_phone") or current_recipient,
                            "status_code": result.get("status_code"),
                            "response_body": result.get("response_body"),
                            "metadata": msg.metadata,
                        })
                        logger.info("WhatsApp enviado exitosamente a %s", current_recipient)
                    else:
                        detail = result.get("detail") or result.get("error") or "Error desconocido enviando WhatsApp."
                        append_whatsapp_delivery_log({
                            "event_id": msg.event_id,
                            "event": "failed",
                            "level": "error",
                            "message": "No se pudo enviar el WhatsApp.",
                            "lada": msg.lada,
                            "phone_number": msg.phone_number,
                            "full_phone": result.get("full_phone") or current_recipient,
                            "status_code": result.get("status_code"),
                            "error": result.get("error"),
                            "detail": detail,
                            "response_body": result.get("response_body"),
                            "metadata": msg.metadata,
                        })
                        logger.error("Error enviando WhatsApp a %s: %s", current_recipient, detail)
                except Exception as exc:
                    self._update_last_send_time(current_recipient)
                    append_whatsapp_delivery_log({
                        "event_id": msg.event_id,
                        "event": "failed",
                        "level": "error",
                        "message": "Excepcion no controlada en el worker de WhatsApp.",
                        "lada": msg.lada,
                        "phone_number": msg.phone_number,
                        "full_phone": current_recipient,
                        "error": type(exc).__name__,
                        "detail": str(exc),
                        "metadata": msg.metadata,
                    })
                    logger.exception("Error en WhatsApp Queue Worker para %s", current_recipient)
                finally:
                    self._queue.task_done()
            except Exception as exc:
                logger.exception("Error general en WhatsApp Queue Worker: %s", exc)

        logger.info("WhatsApp Queue Worker terminado (total enviados: %s)", messages_sent)

    def _ensure_worker_running(self):
        if self._worker_thread is None or not self._worker_thread.is_alive():
            self._stop_event.clear()
            self._worker_thread = threading.Thread(
                target=self._worker,
                daemon=True,
                name="WhatsAppQueueWorker",
            )
            self._worker_thread.start()

    def enqueue(self, message: str, lada: str, phone_number: str, metadata: Optional[Dict] = None):
        from adm.functions.send_whatsapp_notification import Notification

        event_id = str(uuid.uuid4())
        metadata = dict(metadata or {})
        msg = WhatsAppMessage(
            message=message,
            lada=str(lada or "").strip(),
            phone_number=str(phone_number or "").strip(),
            event_id=event_id,
            metadata=metadata,
        )
        self._queue.put(msg)
        append_whatsapp_delivery_log({
            "event_id": event_id,
            "event": "queued",
            "level": "info",
            "message": "WhatsApp agregado a la cola local; aun no significa que Evolution API lo haya aceptado.",
            "lada": msg.lada,
            "phone_number": msg.phone_number,
            "full_phone": Notification.format_whatsapp_number(msg.lada, msg.phone_number),
            "queue_size": self._queue.qsize(),
            "metadata": metadata,
        })
        logger.info(
            "Mensaje encolado para %s (cola: %s mensajes)",
            Notification.format_whatsapp_number(msg.lada, msg.phone_number),
            self._queue.qsize(),
        )
        self._ensure_worker_running()

    def queue_size(self) -> int:
        return self._queue.qsize()

    def wait_until_empty(self, timeout: Optional[float] = None) -> bool:
        try:
            self._queue.join()
            return True
        except Exception:
            return False

    def stop(self):
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=60)


_whatsapp_queue: Optional[WhatsAppQueue] = None


def get_whatsapp_queue() -> WhatsAppQueue:
    global _whatsapp_queue
    if _whatsapp_queue is None:
        _whatsapp_queue = WhatsAppQueue()
    return _whatsapp_queue


def enqueue_whatsapp(message: str, lada: str, phone_number: str, metadata: Optional[Dict] = None):
    get_whatsapp_queue().enqueue(message, lada, phone_number, metadata=metadata)
