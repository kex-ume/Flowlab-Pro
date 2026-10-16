"""Start the integrated Waitress app and its E&I deadline evaluator."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from integrated_app import application
from core.workflow_worker import start_worker
from waitress import serve


if __name__ == '__main__':
    stop = start_worker()
    try:
        serve(application, host='127.0.0.1', port=5050, threads=8)
    finally:
        stop.set()
