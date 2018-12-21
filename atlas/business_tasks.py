"""
    atlas.business_tasks
    ~~~~~~
    Celery tasks for Atlas.
"""
import os
import time
import json

from datetime import datetime, timedelta
from collections import Counter
from bson import json_util
from math import ceil
from random import randint
import requests
from celery import Celery, chord
from celery.utils.log import get_task_logger
from fabric.api import execute
from git import GitCommandError

from atlas import fabric_tasks, utilities, config_celery
from atlas import code_operations, instance_operations, backup_operations

from atlas.config import (ENVIRONMENT, WEBSERVER_USER, DESIRED_SITE_COUNT, EMAIL_HOST,
                          SSL_VERIFICATION, CODE_ROOT, INACTIVE_WARNINGS, INACTIVE_STATUS,
                          TEST_ACCOUNTS, EMAIL_SIGNATURE, BACKUPS_LARGE_INSTANCES, SEND_NOTIFICATION_FROM_EMAIL)

from atlas.config_servers import (BASE_URLS, API_URLS)


@celery.task
def check_instance_inactive():
    """
    Get a list of inactive instances and notify the site owners.

    1. Get a list of instances that are more inactive than `first_inactive_days` and have correct status
    2. Start loop on list of instances
        * Check to see if instance has a site owner, if not exit loop
    3. Check to see if we should send the first message
        * A first message has not been sent in (today - (`first_inactive_days`))
        * A second message has not been send in (today - (`last_inactive_days` - `second_inactive_days`))
    4. If send first message, exit loop
    5. Check to see if we should send the second message
        * A second message has not been sent in (today - (`second_inactive_days`))
        * A first message has been send in (today - (`first_inactive_days` + 1))
    6. If send second message, exit loop
    7. Check to see if we should send the final message
        * A final message has not been sent in (today - (`last_inactive_days`))
        * A first message has been send in (today - (`last_inactive_days` + 1))
        * A second message has been send in (today - (`last_inactive_days` - `second_inactive_days` + 1))
    8. If send final message, exit loop
    9. If send message, do so
        * Also send record to Event endpoint
    10. If take down, do so

    # TODO What if instance doesn't have an owner?
    # TODO Pull function our into another file
    """
    # Loop through the warnings in INACTIVE_WARNINGS
    # The three different keys are "first", "second", "take_down", corresponding values are 30, 55, 60
    for key, value in INACTIVE_WARNINGS.iteritems():
        log.info('Check inactive | %s', key)
        # Get a list of sites that are older than the warning.

        # Start by calling stats, we want any records whose days since last login is greater than the corresponding warning value(days)
        # Build statistics query
        statistics_query = 'where={{"days_since_last_login":{{"$gte":{0}}},"status":{{"$in":{1}}}}}'.format(
            value['days'], json.dumps(INACTIVE_STATUS))

        # Statistics GET request
        statistics = utilities.get_eve('statistics', statistics_query)

        if not statistics['_meta']['total'] == 0:
            log.info('Stats for outdated sites greater than ' +
                     str(value['days']))
            # Loop through each statistic record
            for statistic in statistics['_items']:
                # Verify that statistics item has been updated in the last 24 hours.
                try:
                    log.debug('Check inactive | Statistic Date Check | %s | %s | %s', timedelta(
                        days=1), datetime.utcnow(), datetime.strptime(statistic['_updated'], "%Y-%m-%d %H:%M:%S %Z"))
                    # Return True if 'now' minus 'updated' is less than 1 day
                    up_to_date = bool((datetime.utcnow() - datetime.strptime(
                        statistic['_updated'], "%Y-%m-%d %H:%M:%S %Z")) < timedelta(days=1))
                    log.debug(
                        'Check inactive | Statistic Date Check | Up to date | %s', up_to_date)
                except OutOfDateException:
                    log.info(
                        'Check inactive | Statistic Out of Date | %s', statistics)
                    continue

                check_date = datetime.utcnow() - timedelta(days=60)
                ## Check for same interval messages
                eve_lookup = 'where={{"event_type":"inactive_mail","atlas.instance_id":"{0}","inactive_mail.inactive_mail_type":"{1}","_created":{{"$gte":"{2}"}}}}'.format(
                    str(statistic['site']), key, check_date.strftime("%Y-%m-%d %H:%M:%S GMT"))
                events = utilities.get_eve('event', query=eve_lookup)
                log.debug(
                    'Check inactive | Mail check results | %s | %s', statistic['site'], events)

                ## Check that previous messages have been sent and that enough time has passed in between.
                if key == 'second':
                    # Create date bound to make sure a previous message was sent appropriately long ago.
                    # IE don't send 30 day and 55 day on back to back runs if the instance is really old.
                    interval_date = datetime.utcnow() - timedelta(days=25)
                    # Build the query, check that the email for 'first' warning was sent
                    eve_lookup_first = 'where={{"event_type":"inactive_mail","atlas.instance_id":"{0}","inactive_mail.inactive_mail_type":"first","_created":{{"$gte":"{1}","$lte":"{2}"}}}}'.format(
                        str(statistic['site']), check_date.strftime("%Y-%m-%d %H:%M:%S GMT"), interval_date.strftime("%Y-%m-%d %H:%M:%S GMT"))
                    events_first = utilities.get_eve(
                        'event', query=eve_lookup_first)
                    log.debug('Check inactive | Verify previous mail | %s | %s',
                              statistic['site'], events_first)
                    if events_first['_meta']['total'] == 0:
                        log.info(
                            'Check inactive | Verify previous mail | %s | No first notice', statistic['site'])
                        # Didn't send a previous notice, on to the next loop
                        continue
                    else:
                        log.debug('Check inactive | First Event Exists')

                elif key == 'take_down':
                    # Create date bound to make sure a previous message was sent appropriately long ago.
                    interval_date = datetime.utcnow() - timedelta(days=5)
                    eve_lookup_second = 'where={{"event_type":"inactive_mail","atlas.instance_id":"{0}","inactive_mail.inactive_mail_type":"second","_created":{{"$gte":"{1}","$lte":"{2}"}}}}'.format(
                        str(statistic['site']), check_date.strftime("%Y-%m-%d %H:%M:%S GMT"), interval_date.strftime("%Y-%m-%d %H:%M:%S GMT"))
                    events_second = utilities.get_eve(
                        'event', query=eve_lookup_second)
                    log.debug('Check inactive | Verify previous mail | %s | %s',
                              statistic['site'], events_second)
                    if events_second['_meta']['total'] == 0:
                        log.info(
                            'Check inactive | Verify previous mail | %s | No second notice', statistic['site'])
                        continue

                # If we don't have any mail items, it is okay to send a new one.
                if events['_meta']['total'] == 0:
                    # Get the 'instance' item from Atlas so that we can use the path in the message.
                    site = utilities.get_single_eve('sites', statistic['site'])
                    # TODO: Refactor when we have multiple environments run by a single Atlas.
                    # Get message together.
                    instance_url = "{0}/{1}".format(
                        BASE_URLS[ENVIRONMENT], site['path'])
                    message = '\n\n'.join(
                        [instance_url, value['message'], EMAIL_SIGNATURE])
                    log.debug('Check inactive | Message | %s | %s',
                              statistic['site'], message)

                    # Get site owner
                    try:
                        log.info(statistic['users']
                                 ['email_address']['site_owner'])
                        email_to = [x for x in statistic['users']['email_address']
                                    ['site_owner'] if x not in TEST_ACCOUNTS]
                    except KeyError:
                        email_to = [SEND_NOTIFICATION_FROM_EMAIL]
                        log.info = 'Check inactive | No site owner for inactive site | %s', statistic[
                            'site']

                    utilities.send_email(
                        email_message=message, email_subject=value['subject'], email_to=email_to)

                    # Create an event for the mail item.
                    event_payload = {
                        "event_type": "inactive_mail",
                        "inactive_mail": {
                            "inactive_mail_type": key,
                            "inactive_mail_to": ', '.join(email_to)
                        },
                        "atlas": {
                            "instance_id": statistic['site']
                        }
                    }

                    # POST event
                    utilities.post_eve('event', event_payload)

                    # Take down instance if we need to.
                    if key == 'take_down':
                        atlas_payload = {"status": "take_down"}
                        utilities.patch_eve(
                            'sites', statistic['site'], atlas_payload)
                        log.debug(
                            'Check inactive | Take Down Instance | %s', statistic['site'])
                else:
                    # Recent mail event found. Don't send one now.
                    log.debug(
                        'Check inactive | Recent message exists | %s | %s', statistic['site'], events)

        # No site statistics records exist
        else:
            log.debug('Check inactive | %s | No statistics records found', key)

    return True
