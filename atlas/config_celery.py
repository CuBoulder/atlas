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
CELERYD_TASK_TIME_LIMIT = 900

CELERY_ROUTES = {
    'atlas.tasks.code_deploy': {
        'queue': 'update_queue'
    },
    'atlas.tasks.code_update': {
        'queue': 'update_queue'
    },
    'atlas.tasks.code_remove': {
        'queue': 'update_queue'
    },
    'atlas.tasks.site_provision': {
        'queue': 'atlas_queue'
    },
    'atlas.tasks.site_update': {
        'queue': 'update_queue'
    },
    'atlas.tasks.site_remove': {
        'queue': 'atlas_queue'
    },
    'atlas.tasks.drush_prepare': {
        'queue': 'command_queue'
    },
    'atlas.tasks.drush_command_run': {
        'queue': 'command_queue'
    },
    'atlas.tasks.cron': {
        'queue': 'cron_queue'
    },
    'atlas.tasks.cron_run': {
        'queue': 'cron_queue'
    },
    'atlas.tasks.available_sites_check': {
        'queue': 'atlas_queue'
    },
    'atlas.tasks.delete_stuck_pending_sites': {
        'queue': 'atlas_queue'
    },
    'atlas.tasks.delete_statistics_without_active_instance': {
        'queue': 'atlas_queue'
    },
    'atlas.tasks.take_down_installed_old_sites': {
        'queue': 'atlas_queue'
    },
    'atlas.tasks.verify_statistics': {
        'queue': 'atlas_queue'
    },
    'atlas.tasks.remove_old_backups': {
        'queue': 'atlas_queue'
    },
    'atlas.tasks.remove_extra_backups': {
        'queue': 'atlas_queue'
    },
    'atlas.tasks.remove_failed_backups': {
        'queue': 'atlas_queue'
    },
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
    'available_cron': {
        'task': 'atlas.tasks.cron',
        'schedule': timedelta(hours=3),
        'kwargs': {
            "status": "available",
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
    'remove_orphan_statistics': {
        'task': 'atlas.tasks.remove_orphan_statistics',
        'schedule': timedelta(minutes=60),
    },
    'remove_stale_installed_sites': {
        'task': 'atlas.tasks.take_down_installed_old_sites',
        'schedule': crontab(minute=0, hour=2),
    },
    'remove_unused_code': {
        'task': 'atlas.tasks.remove_unused_code',
        'schedule': timedelta(hours=24),
    },
    'remove_old_backups': {
        'task': 'atlas.tasks.remove_old_backups',
        'schedule': timedelta(hours=24),
    },
    'remove_extra_backups': {
        'task': 'atlas.tasks.remove_extra_backups',
        'schedule': timedelta(hours=6),
    },
    'remove_failed_backups': {
        'task': 'atlas.tasks.remove_failed_backups',
        'schedule': timedelta(hours=24),
    },
    'routine_backups': {
        'task': 'atlas.tasks.backup_instances_all',
        'schedule': crontab(minute=0, hour=21)
    },
    'routine_backups_large': {
        'task': 'atlas.tasks.backup_instances_large',
        'schedule': crontab(day_of_week=6, minute=0, hour=22)
    },
    'report_routine_backups': {
        'task': 'atlas.tasks.report_routine_backups',
        'schedule': crontab(minute=0, hour=6)
    },
    'verify_statistics_updating': {
        'task': 'atlas.tasks.verify_statistics',
        'schedule': crontab(minute=0, hour=6),
    },
}
