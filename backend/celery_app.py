from celery import Celery
from app import create_app
from config import Config

def make_celery(app):
    celery = Celery(app.import_name, broker=app.config.get("CELERY_BROKER_URL"))
    celery.conf.update(app.config)
    # Ensure tasks run within the Flask app context
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    celery.Task = ContextTask
    return celery

app = create_app()
celery = make_celery(app)

# Import tasks from the root directory (tasks.py is not inside the app package)
import tasks

# Update beat schedule to reference the correct task name
celery.conf.beat_schedule = {
    'send-reminders-every-10-minutes': {
        'task': 'tasks.send_reminder_emails',  # Task name as defined in tasks.py
        'schedule': 600.0,  # Run every 10 minutes
    },
}

if __name__ == '__main__':
    celery.start()
