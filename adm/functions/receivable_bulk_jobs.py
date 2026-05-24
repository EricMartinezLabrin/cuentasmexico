import json
import os
import threading
from datetime import datetime

from django.conf import settings
from django.utils import timezone


JOB_DUE_TODAY = 'due_today'
JOB_DUE_TOMORROW = 'due_tomorrow'
JOB_DUE_5_DAYS = 'due_5_days'
JOB_OVERDUE_PENDING = 'overdue_pending'
ALL_JOBS = [JOB_DUE_TODAY, JOB_DUE_TOMORROW, JOB_DUE_5_DAYS, JOB_OVERDUE_PENDING]

_STATE_LOCK = threading.Lock()


def _state_path():
    logs_dir = os.path.join(settings.BASE_DIR, 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    return os.path.join(logs_dir, 'receivable_bulk_jobs.json')


def _empty_state():
    return {'jobs': {}}


def _load_state():
    path = _state_path()
    if not os.path.exists(path):
        return _empty_state()
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return _empty_state()
        data.setdefault('jobs', {})
        return data
    except Exception:
        return _empty_state()


def _save_state(state):
    with open(_state_path(), 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _iso_now():
    return timezone.now().isoformat()


def init_job(job_key, recipients):
    with _STATE_LOCK:
        state = _load_state()
        state['jobs'][job_key] = {
            'job_key': job_key,
            'status': 'running',
            'started_at': _iso_now(),
            'updated_at': _iso_now(),
            'finished_at': None,
            'control': {'paused': False, 'stop_requested': False},
            'totals': {
                'total': len(recipients),
                'sent': 0,
                'failed': 0,
                'skipped': 0,
                'pending': len(recipients),
            },
            'recipients': recipients,
            'message': 'Proceso iniciado',
        }
        _save_state(state)


def set_job_message(job_key, message):
    with _STATE_LOCK:
        state = _load_state()
        job = state.get('jobs', {}).get(job_key)
        if not job:
            return
        job['message'] = message
        job['updated_at'] = _iso_now()
        _save_state(state)


def update_recipient(job_key, sale_id, status, note=''):
    with _STATE_LOCK:
        state = _load_state()
        job = state.get('jobs', {}).get(job_key)
        if not job:
            return
        for rec in job.get('recipients', []):
            if rec.get('sale_id') == sale_id:
                prev = rec.get('status', 'pending')
                if prev in ('sent', 'failed', 'skipped'):
                    return
                rec['status'] = status
                rec['note'] = note
                rec['updated_at'] = _iso_now()
                break
        _recompute_totals(job)
        job['updated_at'] = _iso_now()
        _save_state(state)


def _recompute_totals(job):
    recs = job.get('recipients', [])
    sent = sum(1 for r in recs if r.get('status') == 'sent')
    failed = sum(1 for r in recs if r.get('status') == 'failed')
    skipped = sum(1 for r in recs if r.get('status') == 'skipped')
    pending = sum(1 for r in recs if r.get('status') == 'pending')
    job['totals'] = {
        'total': len(recs),
        'sent': sent,
        'failed': failed,
        'skipped': skipped,
        'pending': pending,
    }


def finish_job(job_key, message='Proceso finalizado'):
    with _STATE_LOCK:
        state = _load_state()
        job = state.get('jobs', {}).get(job_key)
        if not job:
            return
        if job.get('status') != 'stopped':
            job['status'] = 'completed'
        job['control'] = {'paused': False, 'stop_requested': False}
        _recompute_totals(job)
        job['message'] = message
        job['updated_at'] = _iso_now()
        job['finished_at'] = _iso_now()
        _save_state(state)


def stop_job(job_key, message='Proceso detenido'):
    with _STATE_LOCK:
        state = _load_state()
        job = state.get('jobs', {}).get(job_key)
        if not job:
            return
        job['status'] = 'stopped'
        job['control']['stop_requested'] = True
        job['control']['paused'] = False
        job['message'] = message
        job['updated_at'] = _iso_now()
        job['finished_at'] = _iso_now()
        _save_state(state)


def set_pause(job_key, paused):
    with _STATE_LOCK:
        state = _load_state()
        job = state.get('jobs', {}).get(job_key)
        if not job:
            return False
        if job.get('status') not in ('running', 'paused'):
            return False
        job['control']['paused'] = bool(paused)
        job['status'] = 'paused' if paused else 'running'
        job['message'] = 'Proceso en pausa' if paused else 'Proceso reanudado'
        job['updated_at'] = _iso_now()
        _save_state(state)
        return True


def request_stop(job_key):
    with _STATE_LOCK:
        state = _load_state()
        job = state.get('jobs', {}).get(job_key)
        if not job:
            return False
        job['control']['stop_requested'] = True
        if job.get('status') in ('running', 'paused'):
            job['message'] = 'Detencion solicitada'
            job['updated_at'] = _iso_now()
        _save_state(state)
        return True


def get_control(job_key):
    state = _load_state()
    job = state.get('jobs', {}).get(job_key, {})
    return job.get('control', {'paused': False, 'stop_requested': False})


def get_jobs_snapshot():
    state = _load_state()
    jobs = state.get('jobs', {})
    result = {}
    for key in ALL_JOBS:
        job = jobs.get(key)
        if not job:
            continue
        result[key] = _with_estimate(job)
    return result


def get_job_snapshot(job_key):
    state = _load_state()
    job = state.get('jobs', {}).get(job_key)
    if not job:
        return None
    return _with_estimate(job)


def _with_estimate(job):
    item = dict(job)
    totals = item.get('totals', {})
    processed = totals.get('sent', 0) + totals.get('failed', 0) + totals.get('skipped', 0)
    pending = totals.get('pending', 0)
    eta_seconds = None
    started_raw = item.get('started_at')
    if started_raw and processed > 0 and pending > 0:
        try:
            started = datetime.fromisoformat(str(started_raw).replace('Z', '+00:00'))
            if timezone.is_naive(started):
                started = timezone.make_aware(started)
            elapsed = max(1, int((timezone.now() - started).total_seconds()))
            avg = elapsed / float(processed)
            eta_seconds = int(avg * pending)
        except Exception:
            eta_seconds = None
    item['eta_seconds'] = eta_seconds
    return item


def rollover_cleanup_if_stale(job_key):
    """
    Si el job quedó 'running/paused' en un día anterior, lo cierra como detenido
    para evitar estado colgado entre días.
    """
    with _STATE_LOCK:
        state = _load_state()
        job = state.get('jobs', {}).get(job_key)
        if not job:
            return False

        if job.get('status') not in ('running', 'paused'):
            return False

        started_raw = job.get('started_at')
        if not started_raw:
            return False

        try:
            started = datetime.fromisoformat(str(started_raw).replace('Z', '+00:00'))
            if timezone.is_naive(started):
                started = timezone.make_aware(started)
            started_local_day = timezone.localtime(started).date()
            now_local_day = timezone.localtime(timezone.now()).date()
            if started_local_day >= now_local_day:
                return False
        except Exception:
            # Si no se puede parsear, preferimos limpiarlo para evitar bloqueo.
            pass

        job['status'] = 'stopped'
        job['control'] = {'paused': False, 'stop_requested': False}
        job['message'] = 'Proceso anterior limpiado automáticamente por cambio de día.'
        job['updated_at'] = _iso_now()
        job['finished_at'] = _iso_now()
        _save_state(state)
        return True
