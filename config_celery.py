from datetime import timedelta
from celery.schedules import crontab
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

# Enables error emails.
CELERY_SEND_TASK_ERROR_EMAILS = send_error_emails

# Email address used as sender (From field).
SERVER_EMAIL = send_from_email

# Mailserver configuration
EMAIL_HOST = email_host
EMAIL_PORT = email_port
EMAIL_USE_TLS = email_use_tls
EMAIL_HOST_USER = email_username
EMAIL_HOST_PASSWORD = email_password

# Setup routing so that we don't overwhelm the server wh.
CELERY_ROUTES = {
    'atlas.tasks.command_run': {'queue': 'command_queue'},
}

CELERYBEAT_SCHEDULE = {
    'launched_cron': {
        'task': 'atlas.tasks.cron',
        'schedule': timedelta(minutes=60),
        'kwargs': {
            "type": "express",
            "status": "launched",
            "exclude_packages": ["cu_classes_bundle"]
        },
    },
    'classes_cron': {
        'task': 'atlas.tasks.cron',
        'schedule': timedelta(hours=2),
        'kwargs': {
            "include_packages": ["cu_classes_bundle"]
        },
    },
    'installed_cron': {
        'task': 'atlas.tasks.cron',
        'schedule': timedelta(hours=3),
        'kwargs': {
            "type": "express",
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
    'remove_orphan_statistics': {
        'task': 'atlas.tasks.delete_statistics_without_active_instance',
        'schedule': crontab(minute=45, hour=2),
    },
    'remove_stale_installed_sites': {
        'task': 'atlas.tasks.take_down_installed_old_sites',
        'schedule': crontab(minute=0, hour=2),
    },
}
