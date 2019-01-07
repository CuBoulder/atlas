"""
Configuration file for Atlas

All variable settings should go here so values can be propagated to the various
 functions from a central location.
"""
import re
import os

from atlas.config_servers import (SERVERDEFS, VARNISH_CONTROL_TERMINALS, NFS_MOUNT_LOCATION,
                                  BASE_URLS, API_URLS)
from atlas.config_local import (ENVIRONMENT, SSL_KEY_FILE, SSL_CRT_FILE, ALLOWED_USERS,
                                NFS_MOUNT_FILES_DIR, DESIRED_SITE_COUNT, CODE_ROOT, WEB_ROOT,
                                INSTANCE_ROOT, SITE_DOWN_PATH, DEFAULT_CORE, DEFAULT_PROFILE,
                                ENCRYPTION_KEY, LDAP_SERVER, LDAP_ORG_UNIT, LDAP_DNS_DOMAIN_NAME,
                                SSH_USER, WEBSERVER_USER, WEBSERVER_USER_GROUP, DATABASE_USER,
                                DATABASE_PASSWORD, SERVICE_ACCOUNT_USERNAME,
                                SERVICE_ACCOUNT_PASSWORD, SLACK_NOTIFICATIONS, SLACK_URL,
                                SLACK_USERNAME, VARNISH_CONTROL_KEY, SEND_NOTIFICATION_EMAILS,
                                SEND_NOTIFICATION_FROM_EMAIL, EMAIL_HOST, EMAIL_PORT,
                                EMAIL_USERNAME, EMAIL_PASSWORD, LOG_LOCATION, EMAIL_USERS_EXCLUDE,
                                STATIC_WEB_PATH, BACKUP_PATH, SMTP_PASSWORD, SAML_AUTH,
                                SERVICENOW_KEY, BACKUPS_LARGE_INSTANCES)

# Set Atlas location
ATLAS_LOCATION = os.path.dirname(os.path.realpath(__file__))

# Verify code_root is correctly formed.
LEADING_SLASH = re.compile("^/")
TRAILING_SLASH = re.compile("/$")
# Uses re.match primitive to look from the beginning.
if not LEADING_SLASH.match(CODE_ROOT):
    raise Exception("'code_root' should begin with a slash.")
if not LEADING_SLASH.match(WEB_ROOT):
    raise Exception("'WEB_ROOT' should begin with a slash.")
if not LEADING_SLASH.match(INSTANCE_ROOT):
    raise Exception("'INSTANCE_ROOT' should begin with a slash.")
# Uses re.search primitive to look anywhere in the string.
if TRAILING_SLASH.search(CODE_ROOT):
    raise Exception("'code_root' should not have a trailing slash.")
if TRAILING_SLASH.search(WEB_ROOT):
    raise Exception("'WEB_ROOT' should not have a trailing slash.")
if TRAILING_SLASH.search(WEB_ROOT):
    raise Exception("'WEB_ROOT' should not have a trailing slash.")

# These are paths that we cannot route to instances.
PROTECTED_PATHS = ['opcache', 'static', 'includes', 'misc',
                   'modules', 'profiles', 'scripts', 'sites', 'themes']

# Files that we do not want to link into Instances.
# Even though the risk is low, including .DS_Store as it may contain sensitive metadata
# Intend to match: .DS_Store, .git/, .gitignore, all text files expect robots.txt, all patch files,
# all markdown files.
INSTANCE_CODE_IGNORE_REGEX = ['^.DS_Store', '^.git',
                              '(?<!^robots)\.txt$', '(.+).patch$', '(.+).md$']

# Drupal core paths to symlink into the WEB_ROOT for the homepage instances. We are not including
# .htaccess or robots.txt since they are managed seperately for this instance.
CORE_WEB_ROOT_SYMLINKS = ['authorize.php', 'cron.php', 'includes', 'index.php', 'install.php',
                          'misc', 'modules', 'profiles', 'scripts', 'sites', 'themes', 'update.php',
                          'web.config', 'xmlrpc.php']

# This allows us to use a self signed cert for local dev.
SSL_VERIFICATION = True
if ENVIRONMENT == 'local':
    SSL_VERIFICATION = False

    import urllib3
    # Disable warnings about not being able to verify local certs.
    # https://urllib3.readthedocs.io/en/latest/advanced-usage.html#ssl-warnings
    urllib3.disable_warnings()

VERSION_NUMBER = '2.3.0-alpha6'
