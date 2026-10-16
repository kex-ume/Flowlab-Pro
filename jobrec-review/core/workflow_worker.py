"""Periodic evaluation runs while the integrated server is running."""
import logging
import threading
from django.db import close_old_connections
from .ei_workflow import evaluate_clocks


def start_worker(interval=60):
    stop = threading.Event()
    def run():
        while not stop.is_set():
            try:
                close_old_connections()
                evaluate_clocks()
                from .personnel_records import evaluate_personnel_reviews
                evaluate_personnel_reviews()
                from .equipment_records import evaluate_programme
                evaluate_programme()
            except Exception:
                logging.getLogger(__name__).exception('E&I workflow timer failed; will retry.')
            finally:
                close_old_connections()
            stop.wait(interval)
    thread = threading.Thread(target=run, daemon=True, name='ei-workflow-clock')
    thread.start()
    return stop
