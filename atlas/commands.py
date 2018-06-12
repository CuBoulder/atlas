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
        'description': u'Check that all intances are present and the directory structure is correct. Fix any instances that are irregular.',
    },
    {
        'machine_name': u'correct_nfs_file_permissions',
        'description': u'Correct the group file and directory permissions for an instance.',
    }
]
