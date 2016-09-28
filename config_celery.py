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

# Name and email addresses of recipients
ADMINS = (
    ('James Fuller', 'james.w.fuller@colorado.edu'),
)

# Email address used as sender (From field).
SERVER_EMAIL = 'osr_web_deploy@colorado.edu'

# Mailserver configuration
EMAIL_HOST = email_host
EMAIL_PORT = email_port
EMAIL_USE_TLS = email_use_tls
EMAIL_HOST_USER = email_username
EMAIL_HOST_PASSWORD = email_password


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
