"""
Celery configuration for SnapFood project.
"""

import os
from celery import Celery

# Set default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

app = Celery('snapfood')

# Load config from Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all registered Django apps
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    """
    Debug task to verify Celery is working
    """
    print(f'Request: {self.request!r}')


@app.task
def health_check():
    """
    Simple health check task
    """
    return {'status': 'ok', 'celery': 'running'}
