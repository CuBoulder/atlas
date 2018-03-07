"""
Celery Config, Celerybeat schedule.
"""
from datetime import timedelta
from celery.schedules import crontab

BROKER_URL = 'amqp://guest@localhost//'
CELERY_RESULT_BACKEND = 'mongodb://localhost:27017/'
CELERY_MONGODB_BACKEND_SETTINGS = {
    'database': 'celery',
    'taskmeta_collection': 'taskmeta_collection',
}

CELERY_TIMEZONE = 'MST'
CELERY_ENABLE_UTC = True
# Time in seconds
CELERYD_TASK_TIME_LIMIT = 600

# Setup routing to isolate routine cron from other commands..
CELERY_ROUTES = {
    'atlas.tasks.command_run': {'queue': 'command_queue'},
    'atlas.tasks.cron_run': {'queue': 'cron_queue'},
}

CELERYBEAT_SCHEDULE = {
    'launched_cron': {
        'task': 'atlas.tasks.cron',
        'schedule': timedelta(minutes=60),
        'kwargs': {
            "status": "launched",
        },
    },
    'locked_cron': {
        'task': 'atlas.tasks.cron',
        'schedule': timedelta(hours=6),
        'kwargs': {
            "status": "locked",
        },
    },
    'installed_cron': {
        'task': 'atlas.tasks.cron',
        'schedule': timedelta(hours=3),
        'kwargs': {
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
        'task': 'atlas.tasks.remove_orphan_statistics',
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
    'remove_unused_code': {
        'task': 'atlas.tasks.remove_unused_code',
        'schedule': timedelta(hours=24),
    },
    'remove_old_backups': {
        'task': 'atlas.tasks.remove_old_backups',
        'schedule': timedelta(hours=24),
    },
}
