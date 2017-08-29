from datetime import timedelta
from celery.schedules import crontab
from kombu import Queue
from config_local import *

BROKER_URL='amqp://guest@localhost//'
CELERY_RESULT_BACKEND = 'mongodb://localhost:27017/'
CELERY_MONGODB_BACKEND_SETTINGS = {
    'database': 'celery',
    'taskmeta_collection': 'taskmeta_collection',
}

CELERY_TIMEZONE = 'MST'
CELERY_ENABLE_UTC = True
# Time in seconds
CELERYD_TASK_TIME_LIMIT = 600

# Setup queues and routing to isolate cron.
CELERY_DEFAULT_QUEUE = 'celery'
CELERY_QUEUES = (
    Queue('celery', routing_key='tasks.#'),
    Queue('cron_queue', routing_key='cron.#'),
    Queue('command_queue', routing_key='command.#'),
)
CELERY_DEFAULT_EXCHANGE = 'tasks'
CELERY_DEFAULT_EXCHANGE_TYPE = 'topic'
CELERY_DEFAULT_ROUTING_KEY = 'tasks.celery'
CELERY_ROUTES = {
    'atlas.tasks.command_run': {
        'queue': 'command_queue',
        'routing_key': 'command.run',
    },
    'atlas.tasks.cron': {
        'queue': 'cron_queue',
        'routing_key': 'cron.run',
    },
}

CELERYBEAT_SCHEDULE = {
    'launched_cron': {
        'task': 'atlas.tasks.cron',
        'schedule': timedelta(minutes=60),
        'kwargs': {
            "type": "express",
            "status": "launched",
        },
    },
    'locked_cron': {
        'task': 'atlas.tasks.cron',
        'schedule': timedelta(hours=6),
        'kwargs': {
            "type": "express",
            "status": "locked",
        },
    },
    'installed_cron': {
        'task': 'atlas.tasks.cron',
        'schedule': timedelta(hours=3),
        'kwargs': {
            "type": "express",
            "status": "installed",
        },
    },
    'available_sites_check': {
        'task': 'atlas.tasks.available_sites_check',
        'schedule': timedelta(minutes=5),
    },
    'delete_stuck_pending_sites': {
        'task': 'atlas.tasks.delete_stuck_pending_sites',
        'schedule': timedelta(minutes=5),
    },
    'remove_stale_available_sites': {
        'task': 'atlas.tasks.delete_all_available_sites',
        'schedule': crontab(minute=0, hour=3),
    },
    'remove_orphan_statistics': {
        'task': 'atlas.tasks.delete_statistics_without_active_instance',
        'schedule': timedelta(minutes=60),
    },
    'remove_stale_installed_sites': {
        'task': 'atlas.tasks.take_down_installed_old_sites',
        'schedule': crontab(minute=0, hour=2),
    },
    'verify_statistics_updating': {
        'task': 'atlas.tasks.verify_statistics',
        'schedule': timedelta(hours=24),
    },
}
