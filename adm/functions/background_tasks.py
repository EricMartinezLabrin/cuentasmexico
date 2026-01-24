"""
Sistema de tareas en segundo plano para operaciones pesadas.
Permite ejecutar sincronizaciones sin bloquear el servidor.
"""

import threading
import logging
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Estados posibles de una tarea"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class BackgroundTask:
    """Representa una tarea en segundo plano"""
    task_id: str
    task_type: str
    status: TaskStatus = TaskStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    progress: str = ""


class BackgroundTaskManager:
    """
    Gestor de tareas en segundo plano.

    Características:
    - Ejecuta tareas en hilos separados
    - Permite consultar el estado de las tareas
    - Solo permite una tarea del mismo tipo a la vez
    - Singleton para acceso global
    """

    _instance: Optional['BackgroundTaskManager'] = None
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

        self._tasks: Dict[str, BackgroundTask] = {}
        self._running_types: Dict[str, str] = {}  # task_type -> task_id
        self._tasks_lock = threading.Lock()
        self._initialized = True
        logger.info("BackgroundTaskManager inicializado")

    def is_task_type_running(self, task_type: str) -> bool:
        """Verifica si hay una tarea del tipo especificado en ejecución"""
        with self._tasks_lock:
            if task_type in self._running_types:
                task_id = self._running_types[task_type]
                task = self._tasks.get(task_id)
                if task and task.status == TaskStatus.RUNNING:
                    return True
                # Limpiar si ya no está corriendo
                del self._running_types[task_type]
            return False

    def get_running_task(self, task_type: str) -> Optional[BackgroundTask]:
        """Obtiene la tarea en ejecución del tipo especificado"""
        with self._tasks_lock:
            if task_type in self._running_types:
                task_id = self._running_types[task_type]
                return self._tasks.get(task_id)
            return None

    def get_task(self, task_id: str) -> Optional[BackgroundTask]:
        """Obtiene una tarea por su ID"""
        with self._tasks_lock:
            return self._tasks.get(task_id)

    def start_task(
        self,
        task_type: str,
        func: Callable,
        *args,
        **kwargs
    ) -> tuple[bool, str, Optional[BackgroundTask]]:
        """
        Inicia una tarea en segundo plano.

        Args:
            task_type: Tipo de tarea (ej: "sync_sheets", "verify_accounts")
            func: Función a ejecutar
            *args, **kwargs: Argumentos para la función

        Returns:
            (success, message, task): Tupla con resultado
        """
        # Verificar si ya hay una tarea del mismo tipo corriendo
        if self.is_task_type_running(task_type):
            existing_task = self.get_running_task(task_type)
            return (
                False,
                f"Ya hay una tarea '{task_type}' en ejecución desde {existing_task.started_at}",
                existing_task
            )

        # Crear nueva tarea
        task_id = str(uuid.uuid4())[:8]
        task = BackgroundTask(
            task_id=task_id,
            task_type=task_type,
            status=TaskStatus.RUNNING,
            started_at=datetime.now(),
            progress="Iniciando..."
        )

        with self._tasks_lock:
            self._tasks[task_id] = task
            self._running_types[task_type] = task_id

        # Ejecutar en hilo separado
        thread = threading.Thread(
            target=self._run_task,
            args=(task_id, func, args, kwargs),
            daemon=True,
            name=f"BackgroundTask-{task_type}-{task_id}"
        )
        thread.start()

        logger.info(f"🚀 Tarea '{task_type}' iniciada con ID: {task_id}")
        return (True, f"Tarea iniciada con ID: {task_id}", task)

    def _run_task(
        self,
        task_id: str,
        func: Callable,
        args: tuple,
        kwargs: dict
    ):
        """Ejecuta la tarea en segundo plano"""
        task = self._tasks.get(task_id)
        if not task:
            return

        try:
            task.progress = "Ejecutando..."
            result = func(*args, **kwargs)

            with self._tasks_lock:
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now()
                task.result = result
                task.progress = "Completado"

                # Limpiar de running_types
                if task.task_type in self._running_types:
                    del self._running_types[task.task_type]

            logger.info(f"✅ Tarea {task_id} ({task.task_type}) completada")

        except Exception as e:
            with self._tasks_lock:
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.now()
                task.error = str(e)
                task.progress = f"Error: {str(e)}"

                # Limpiar de running_types
                if task.task_type in self._running_types:
                    del self._running_types[task.task_type]

            logger.error(f"❌ Tarea {task_id} ({task.task_type}) falló: {e}")

    def get_all_tasks(self) -> Dict[str, BackgroundTask]:
        """Obtiene todas las tareas"""
        with self._tasks_lock:
            return dict(self._tasks)

    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """Limpia tareas antiguas completadas/fallidas"""
        now = datetime.now()
        with self._tasks_lock:
            to_delete = []
            for task_id, task in self._tasks.items():
                if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                    if task.completed_at:
                        age = (now - task.completed_at).total_seconds() / 3600
                        if age > max_age_hours:
                            to_delete.append(task_id)

            for task_id in to_delete:
                del self._tasks[task_id]

            if to_delete:
                logger.info(f"🧹 Limpiadas {len(to_delete)} tareas antiguas")


# Instancia global
_task_manager: Optional[BackgroundTaskManager] = None


def get_task_manager() -> BackgroundTaskManager:
    """Obtiene la instancia del gestor de tareas"""
    global _task_manager
    if _task_manager is None:
        _task_manager = BackgroundTaskManager()
    return _task_manager
