"""
Commands for the command endpoint
"""

import logging
from datetime import datetime, timedelta
from json import dumps

from eve.methods.post import post_internal

from atlas import utilities
from atlas.config import (EMAIL_SIGNATURE, EXPRESS_URL,
                          INACTIVE_WARNINGS, INACTIVE_STATUS, TEST_ACCOUNTS)

log = logging.getLogger('atlas.commands')

COMMANDS = [
    {
        'machine_name': u'clear_php_cache',
        'description': u'Clear the PHP script cache on all webservers.',
    },
    {
        'machine_name': u'import_code',
        'description': u'Import code from another Atlas instance. When running the command include the target environment (dev, test, prod) as a payload in the format `{"env":"dev"}`.',
    },
    {
        'machine_name': u'rebalance_update_groups',
        'description': u'Resort the members of groups 0-10 so that they are evenly distributed.',
    },
    {
        'machine_name': u'update_settings_files',
        'description': u'Update the Drupal settings file.',
    },
    {
        'machine_name': u'update_homepage_files',
        'description': u'Update `.htaccess` and `robots.txt` files',
    },
    {
        'machine_name': u'heal_code',
        'description': u'Check that all code is present and on the correct hash. Fix any that are not.',
    },
    {
        'machine_name': u'heal_instances',
        'description': u'Check that all instances are present and the directory structure is correct. Fix any instances that are irregular.',
    },
    {
        'machine_name': u'sync_instances',
        'description': u'Sync instances to web servers.',
    },
    {
        'machine_name': u'correct_file_permissions',
        'description': u'Correct the file and directory permissions for an instance.',
    },
    {
        'machine_name': u'backup_all_instances',
        'description': u'Start the process of generating an On Demand backup for all instances.',
    },
]

# Custom Exception Handling
class OutOfDateException(Exception):
    pass


def check_instance_inactive():
    """
    Notify owners of inactive instances.
    """
    # Loop through the warnings.
    for key, value in INACTIVE_WARNINGS.iteritems():
        log.info('Check inactive | %s', key)
        # Get a list of sites that are older than the warning.

        # Start by calling stats.
        statistics_query = 'where={{"days_since_last_edit":{{"$gte":{0}}},"status":{{"$in":{1}}}}}'.format(
            value['days'], dumps(INACTIVE_STATUS))
        statistics = utilities.get_eve('statistics', statistics_query)

        log.debug('Check inactive | %s | %s', key, statistics)

        if not statistics['_meta']['total'] == 0:
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
                # Setup query Bondo for Event items that are: 'inactive_mail', related to this
                # instance, of the same 'inactive_mail' type (first, second, take_down), and created
                # more recently than the date from above.
                # eve_lookup = '?where={{"event_type":"inactive_mail","atlas.instance_id":"{0}","inactive_mail":"{1}","_created":{{"$gte":"{2}"}}}}'.format(
                #     str(statistic['site']), key, date.strftime("%Y-%m-%d %H:%M:%S GMT"))
                eve_lookup = 'where={{"event_type":"inactive_mail","atlas.instance_id":"{0}","inactive_mail.inactive_mail_type":"{1}","_created":{{"$gte":"{2}"}}}}'.format(
                    str(statistic['site']), key, check_date.strftime("%Y-%m-%d %H:%M:%S GMT"))
                # Run the query
                log.debug('Check inactive | Mail check query | %s', eve_lookup)
                # TODO Fix this
                # Currently get_internal is getting jacked when Eve parses the lookup in eve/utils.py#L124
                # The fact that we are POST to 'commands' is getting in the middle.
                # events = {}
                # events['response'], events['last_modified'], events['etag'], events['status'], events['headers'] = get_internal(
                #     'event', lookup=eve_lookup)
                # WORKAROUND using the requests library.
                events = utilities.get_eve('event', query=eve_lookup)
                log.debug(
                    'Check inactive | Mail check results | %s | %s', statistic['site'], events)

                ## Check that previous messages have been sent and that enough time has passed in between.
                if key == 'second':
                    # Create date bound to make sure a previous message was sent appropriately long ago.
                    # IE don't send 30 day and 55 day on back to back runs if the instance is really old.
                    interval_date = datetime.utcnow() - timedelta(days=25)
                    # Build the query
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
                    site = utilities.get_eve('sites', statistic['site'])
                    # TODO: Refactor when we have multiple environments run by a single Atlas.

                    # Get message together.
                    instance_url = "{0}/{1}".format(EXPRESS_URL, site['path'])
                    message = '\n\n'.join(
                        [instance_url, value['message'], EMAIL_SIGNATURE])
                    log.debug('Check inactive | Message | %s | %s',
                              statistic['site'], message)

                    # Remove test accounts.
                    email_to = [x for x in statistic['users']['email_address']
                                ['site_contact'] if x not in TEST_ACCOUNTS]
                    # Send mail
                    utilities.send_email(
                        email_message=message, email_subject=value['subject'], email_to=email_to)

                    # Create an event for the mail item.
                    event_payload = {
                        "event_type": "inactive_mail",
                        "inactive_mail": {
                            "inactive_mail_type": key,
                            "inactive_mail_to": ', '.join(statistic['users']['email_address']['site_contact'])
                        },
                        "atlas": {
                            "instance_id": statistic['site']
                        }
                    }
                    post_internal(resource='event', payl=event_payload)

                    # Take down instance if we need to.
                    if key == 'take_down':
                        atlas_payload = {"status": "take_down"}
                        utilities.patch_eve(
                            'sites', statistic['site'], atlas_payload)
                else:
                    # Recent mail event found. Don't send one now.
                    log.debug(
                        'Check inactive | Recent message exists | %s | %s', statistic['site'], events)

        else:
            # No Statistics found.
            log.debug('Check inactive | %s | 0 statistics records found', key)

    return True
