"""
Configuration file for Atlas

All variable settings should go here so values can be propagated to the various
 functions from a central location.
"""
import re
import os

# Set Atlas location
ATLAS_LOCATION = os.path.dirname(os.path.realpath(__file__))

try:
    from config_servers import *
except ImportError:
    raise Exception("You need an config_servers.py file!")

try:
    from config_local import *
except ImportError:
    raise Exception("You need an config_local.py file!")

# Verify code_root is correctly formed.
begin_with_slash = re.compile("^/")
trailing_slash = re.compile("/$")
# Uses re.match primitive to look from the beginning.
if not begin_with_slash.match(CODE_ROOT):
    raise Exception("'code_root' should begin with a slash.")
if not begin_with_slash.match(SITES_WEB_ROOT):
    raise Exception("'sites_web_root' should begin with a slash.")
if not begin_with_slash.match(SITES_CODE_ROOT):
    raise Exception("'sites_code_root' should begin with a slash.")
# Uses re.search primitive to look anywhere in the string.
if trailing_slash.search(CODE_ROOT):
    raise Exception("'code_root' should not have a trailing slash.")
if trailing_slash.search(SITES_WEB_ROOT):
    raise Exception("'sites_web_root' should not have a trailing slash.")
if trailing_slash.search(SITES_WEB_ROOT):
    raise Exception("'sites_web_root' should not have a trailing slash.")


# This allows us to use a self signed cert for local dev.
SSL_VERIFICATION = True
if ENVIRONMENT == 'local':
    SSL_VERIFICATION = False

VERSION_NUMBER = '2.0.0-dev'
