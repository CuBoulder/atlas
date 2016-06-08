"""
    atlas.tasks
    ~~~~~~~~~

    Celery tasks for Atlas.

"""
import sys
import time
import re
import random
import logging

from celery import Celery
from jinja2 import Environment, PackageLoader
from atlas import config_celerybeat

path = '/data/code'
if path not in sys.path:
    sys.path.append(path)

# Tell Jinja where our templates live.
env = Environment(loader=PackageLoader('atlas', 'templates'))

# Create the celery object
celery = Celery('tasks')
celery.config_from_object(config_celerybeat)