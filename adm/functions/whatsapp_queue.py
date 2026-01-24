"""
Cola asíncrona para mensajes de WhatsApp.
Evita bloqueos por spam enviando mensajes con delays aleatorios.
"""

import threading
import queue
import random
import time
import logging
from typing import Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class WhatsAppMessage:
    """Estructura para un mensaje de WhatsApp en cola"""
    message: str
    lada: str
    phone_number: str


class WhatsAppQueue:
    """
    Cola asíncrona para enviar mensajes de WhatsApp.

    Características:
    - Envía mensajes en un hilo separado (no bloquea el proceso principal)
    - Delay aleatorio entre 7-20 segundos entre TODOS los mensajes
    - Thread-safe usando queue.Queue
    - Singleton para evitar múltiples hilos
    - Rastrea el último envío para garantizar el delay incluso entre requests
    """

    _instance: Optional['WhatsAppQueue'] = None
    _lock = threading.Lock()

    def __new__(cls):
        """Implementación Singleton thread-safe"""
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
        self._min_delay = 7  # segundos
        self._max_delay = 20  # segundos
        self._last_send_time: Optional[datetime] = None  # Rastrea último envío
        self._send_lock = threading.Lock()  # Lock para el tiempo de envío
        self._initialized = True
        self._is_first_message = True  # Primer mensaje no necesita delay
        logger.info("WhatsAppQueue inicializada")

    def _wait_for_rate_limit(self):
        """
        Espera el tiempo necesario para respetar el rate limit.
        SIEMPRE espera entre 7-20 segundos después del último mensaje.
        """
        with self._send_lock:
            if self._last_send_time is not None:
                # Calcular tiempo desde último envío
                elapsed = (datetime.now() - self._last_send_time).total_seconds()

                # Generar delay aleatorio requerido
                required_delay = random.uniform(self._min_delay, self._max_delay)

                # Si no ha pasado suficiente tiempo, esperar
                if elapsed < required_delay:
                    wait_time = required_delay - elapsed
                    logger.info(f"⏳ Rate limit: esperando {wait_time:.1f}s más (elapsed: {elapsed:.1f}s, required: {required_delay:.1f}s)")

                    # Esperar en intervalos pequeños para poder responder a stop_event
                    waited = 0
                    while waited < wait_time and not self._stop_event.is_set():
                        time.sleep(0.5)
                        waited += 0.5

    def _update_last_send_time(self):
        """Actualiza el timestamp del último envío"""
        with self._send_lock:
            self._last_send_time = datetime.now()

    def _worker(self):
        """
        Worker que procesa la cola de mensajes.
        Se ejecuta en un hilo separado.
        SIEMPRE aplica delay entre mensajes.
        """
        from adm.functions.send_whatsapp_notification import Notification

        logger.info("🚀 WhatsApp Queue Worker iniciado")
        messages_sent = 0

        while not self._stop_event.is_set() or not self._queue.empty():
            try:
                # Intentar obtener mensaje con timeout para poder verificar stop_event
                try:
                    msg = self._queue.get(timeout=1)
                except queue.Empty:
                    continue

                # SIEMPRE esperar rate limit antes de enviar (excepto primer mensaje)
                if messages_sent > 0:
                    self._wait_for_rate_limit()

                # Enviar mensaje
                try:
                    logger.info(f"📤 Enviando WhatsApp a {msg.lada}{msg.phone_number}... (mensaje #{messages_sent + 1}, cola: {self._queue.qsize()} restantes)")
                    Notification.send_whatsapp_notification(
                        msg.message,
                        msg.lada,
                        msg.phone_number
                    )
                    self._update_last_send_time()
                    messages_sent += 1
                    logger.info(f"✅ WhatsApp enviado exitosamente a {msg.lada}{msg.phone_number}")
                except Exception as e:
                    logger.error(f"❌ Error enviando WhatsApp a {msg.lada}{msg.phone_number}: {e}")
                    # Aún así actualizar tiempo para no bombardear en caso de error
                    self._update_last_send_time()
                finally:
                    self._queue.task_done()

            except Exception as e:
                logger.error(f"❌ Error en WhatsApp Queue Worker: {e}")

        logger.info(f"🏁 WhatsApp Queue Worker terminado (total enviados: {messages_sent})")

    def _ensure_worker_running(self):
        """Asegura que el worker esté corriendo"""
        if self._worker_thread is None or not self._worker_thread.is_alive():
            self._stop_event.clear()
            self._worker_thread = threading.Thread(
                target=self._worker,
                daemon=True,  # El hilo se cerrará cuando termine el proceso principal
                name="WhatsAppQueueWorker"
            )
            self._worker_thread.start()

    def enqueue(self, message: str, lada: str, phone_number: str):
        """
        Agrega un mensaje a la cola para envío asíncrono.

        Args:
            message: Texto del mensaje
            lada: Código de país (ej: 52 para México)
            phone_number: Número de teléfono sin código de país
        """
        msg = WhatsAppMessage(
            message=message,
            lada=lada,
            phone_number=phone_number
        )
        self._queue.put(msg)
        logger.info(f"Mensaje encolado para {lada}{phone_number} (cola: {self._queue.qsize()} mensajes)")

        # Iniciar worker si no está corriendo
        self._ensure_worker_running()

    def queue_size(self) -> int:
        """Retorna el número de mensajes pendientes en la cola"""
        return self._queue.qsize()

    def wait_until_empty(self, timeout: Optional[float] = None) -> bool:
        """
        Espera hasta que la cola esté vacía.

        Args:
            timeout: Tiempo máximo de espera en segundos (None = indefinido)

        Returns:
            True si la cola se vació, False si se alcanzó el timeout
        """
        try:
            self._queue.join()
            return True
        except Exception:
            return False

    def stop(self):
        """Detiene el worker (procesa mensajes pendientes primero)"""
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=60)  # Esperar máximo 60s


# Instancia global para uso directo
_whatsapp_queue: Optional[WhatsAppQueue] = None


def get_whatsapp_queue() -> WhatsAppQueue:
    """Obtiene la instancia singleton de la cola de WhatsApp"""
    global _whatsapp_queue
    if _whatsapp_queue is None:
        _whatsapp_queue = WhatsAppQueue()
    return _whatsapp_queue


def enqueue_whatsapp(message: str, lada: str, phone_number: str):
    """
    Función de conveniencia para encolar un mensaje de WhatsApp.

    Args:
        message: Texto del mensaje
        lada: Código de país (ej: 52 para México)
        phone_number: Número de teléfono sin código de país
    """
    get_whatsapp_queue().enqueue(message, lada, phone_number)
