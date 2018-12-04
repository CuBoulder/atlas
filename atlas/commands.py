"""
Commands for the command endpoint
"""

import logging

from atlas import utilities

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
    {
        'machine_name': u'remove_extra_backups',
        'description': u'Start the process of removing extra.',
    },
]
