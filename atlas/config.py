"""
Configuration file for Atlas

All variable settings should go here so values can be propagated to the various
 functions from a central location.
"""
import re
import os

from atlas.config_servers import (SERVERDEFS, VARNISH_CONTROL_TERMINALS, NFS_MOUNT_LOCATION,
                                  BASE_URLS, API_URLS, LOAD_BALANCER_CONFIG_FILES,
                                  LOAD_BALANCER_CONFIG_GROUP)
from atlas.config_local import (ENVIRONMENT, SSL_KEY_FILE, SSL_CRT_FILE, ALLOWED_USERS,
                                NFS_MOUNT_FILES_DIR, LOAD_BALANCER, DESIRED_SITE_COUNT, CODE_ROOT,
                                SITES_WEB_ROOT, SITES_CODE_ROOT, SITE_DOWN_PATH, BACKUPS_PATH,
                                DEFAULT_CORE, DEFAULT_PROFILE, ENCRYPTION_KEY, LDAP_SERVER,
                                LDAP_ORG_UNIT, LDAP_DNS_DOMAIN_NAME, SSH_USER, WEBSERVER_USER,
                                WEBSERVER_USER_GROUP, DATABASE_USER, DATABASE_PASSWORD,
                                SERVICE_ACCOUNT_USERNAME, SERVICE_ACCOUNT_PASSWORD,
                                SLACK_NOTIFICATIONS, SLACK_URL, SLACK_USERNAME,
                                SEND_NOTIFICATION_EMAILS, SEND_NOTIFICATION_FROM_EMAIL, EMAIL_HOST,
                                EMAIL_PORT, EMAIL_USERNAME, EMAIL_PASSWORD, LOG_LOCATION,
                                EMAIL_USERS_EXCLUDE)

# Set Atlas location
ATLAS_LOCATION = os.path.dirname(os.path.realpath(__file__))

# Verify code_root is correctly formed.
LEADING_SLASH = re.compile("^/")
TRAILING_SLASH = re.compile("/$")
# Uses re.match primitive to look from the beginning.
if not LEADING_SLASH.match(CODE_ROOT):
    raise Exception("'code_root' should begin with a slash.")
if not LEADING_SLASH.match(SITES_WEB_ROOT):
    raise Exception("'sites_web_root' should begin with a slash.")
if not LEADING_SLASH.match(SITES_CODE_ROOT):
    raise Exception("'sites_code_root' should begin with a slash.")
# Uses re.search primitive to look anywhere in the string.
if TRAILING_SLASH.search(CODE_ROOT):
    raise Exception("'code_root' should not have a trailing slash.")
if TRAILING_SLASH.search(SITES_WEB_ROOT):
    raise Exception("'sites_web_root' should not have a trailing slash.")
if TRAILING_SLASH.search(SITES_WEB_ROOT):
    raise Exception("'sites_web_root' should not have a trailing slash.")


# This allows us to use a self signed cert for local dev.
SSL_VERIFICATION = True
if ENVIRONMENT == 'local':
    SSL_VERIFICATION = False

    import urllib3
    # Disable warnings about not being able to verify local certs.
    # https://urllib3.readthedocs.io/en/latest/advanced-usage.html#ssl-warnings
    urllib3.disable_warnings()

VERSION_NUMBER = '2.1.2'
