"""
Configuration file for Atlas

All variable settings should go here so values can be propagated to the various
 functions from a central location.
"""
import re
import os

# Set Atlas location
atlas_location = os.path.dirname(os.path.realpath(__file__))

# Import config_servers.py.
try:
    from config_servers import *
except ImportError:
    raise Exception("You need a config_servers.py file!")

# Import config_local.py.
try:
    from config_local import *
except ImportError:
    raise Exception("You need a config_local.py file!")

# Verify code_root is correctly formed.
begin_with_slash = re.compile("^/")
trailing_slash = re.compile("/$")
# Uses re.match primitive to look from the beginning.
if not begin_with_slash.match(code_root):
    raise Exception("'code_root' should begin with a slash.")
if not begin_with_slash.match(sites_web_root):
    raise Exception("'sites_web_root' should begin with a slash.")
if not begin_with_slash.match(sites_code_root):
    raise Exception("'sites_code_root' should begin with a slash.")
# Uses re.search primitive to look anywhere in the string.
if trailing_slash.search(code_root):
    raise Exception("'code_root' should not have a trailing slash.")
if trailing_slash.search(sites_web_root):
    raise Exception("'sites_web_root' should not have a trailing slash.")
if trailing_slash.search(sites_web_root):
    raise Exception("'sites_web_root' should not have a trailing slash.")


# This allows us to use a self signed cert for local dev.
ssl_verification = True
if environment == 'local':
    ssl_verification = False

version_number = '1.0.13'
