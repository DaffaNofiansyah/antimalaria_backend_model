import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
# This line is crucial so that Celery knows how to find the Django project.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'antimalaria_ml.settings')

# Create the Celery application instance.
# The first argument is the name of the current module.
app = Celery('antimalaria_ml')

# Load configuration from Django's settings.py.
# The namespace='CELERY' means all celery-related configuration keys
# should have a `CELERY_` prefix in your settings.py.
# Example: CELERY_BROKER_URL, CELERY_RESULT_BACKEND
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover task modules from all registered Django apps.
# Celery will look for a `tasks.py` file in each app directory
# and automatically load the tasks defined there.
app.autodiscover_tasks()

# (Optional) A sample task to verify the setup
@app.task(bind=True)
def debug_task(self):
    """A sample task that prints its own request information."""
    print(f'Request: {self.request!r}')