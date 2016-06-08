from datetime import timedelta
from celery.schedules import crontab

BROKER_URL = 'mongodb://localhost:27017/atlas'
CELERY_RESULT_BACKEND = 'mongodb://localhost:27017/atlas'

CELERY_TIMEZONE = 'MST'

CELERY_ROUTES = {
    'inventory.tasks.express_launched_cron': {'queue': 'expresscrons'},
}

CELERYBEAT_SCHEDULE = {
    'express-launched-cron': {
        'task': 'inventory.tasks.express_launched_cron',
        'schedule': timedelta(minutes=20),
    },
}
