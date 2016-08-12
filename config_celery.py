from datetime import timedelta
from celery.schedules import crontab

BROKER_URL='amqp://guest@localhost//'
CELERY_RESULT_BACKEND = 'mongodb://localhost:27017/'
CELERY_MONGODB_BACKEND_SETTINGS = {
    'database': 'celery',
    'taskmeta_collection': 'taskmeta_collection',
}

# TODO: Setup error emailing: http://docs.celeryproject.org/en/latest/configuration.html#error-e-mails

CELERY_TIMEZONE = 'MST'
CELERY_ENABLE_UTC = True
# Time in seconds
CELERYD_TASK_TIME_LIMIT = 600

CELERY_ROUTES = {
    'inventory.tasks.express_launched_cron': {'queue': 'expresscrons'},
}

CELERYBEAT_SCHEDULE = {
    'express-launched-cron': {
        'task': 'inventory.tasks.express_launched_cron',
        'schedule': timedelta(minutes=20),
    },
}
