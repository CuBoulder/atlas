from datetime import timedelta
from celery.schedules import crontab

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

CELERY_ROUTES = {
    'inventory.tasks.express_launched_cron': {'queue': 'expresscrons'},
}

CELERYBEAT_SCHEDULE = {
    'launched-cron': {
        'task': 'atlas.tasks.cron',
        'schedule': timedelta(minutes=5),
        'kwargs': {
            "status": "launched",
            "exclude_packages": ["cu_classes_bundle"]
        },
    },
    'classes-cron': {
        'task': 'atlas.tasks.cron',
        'schedule': timedelta(minutes=60),
        'kwargs': {"include_packages": ["cu_classes_bundle"]},
    },
    'installed-cron': {
        'task': 'atlas.tasks.cron',
        'schedule': timedelta(minutes=120),
        'kwargs': {
            "status": "installed",
            "exclude_packages": ["cu_classes_bundle"]
        },
    },
    'available_sites_check': {
        'task': 'atlas.tasks.available_sites_check',
        'schedule': timedelta(minutes=5),
    },
    'delete_stale_pending_sites': {
        'task': 'atlas.tasks.delete_stale_pending_sites',
        'schedule': timedelta(minutes=5),
    },
    'remove_stale_available_sites': {
        'task': 'atlas.tasks.delete_all_available_sites',
        'schedule': crontab(minute=0, hour=3),
    },
    'remove_stale_installed_sites': {
        'task': 'atlas.tasks.take_down_installed_35_day_old_sites',
        'schedule': crontab(minute=0, hour=2),
    },
}
