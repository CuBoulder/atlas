"""
Configuration file for Atlas

All variable settings should go here so values can be propagated to the various
 functions from a central location.
"""
import re
import os
import base64

from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes


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


# Encryption variables. See https://cryptography.io/en/latest/fernet/#implementation
encryption_kdf = PBKDF2HMAC(
    algorithm=hashes.SHA256(),
    length=32,
    salt=encryption_salt,
    iterations=100000,
    backend=default_backend()
)
encryption_key = base64.urlsafe_b64encode(encryption_kdf.derive(encryption_password))


# URL to eve instance, no trailing slash
if environment == 'local':
    api_server = 'http://inventory.local/atlas'
elif environment == 'development':
    api_server = 'https://wwhdev1.int.colorado.edu/atlas'
elif environment == 'test':
    api_server = 'https://wwhtest1.int.colorado.edu/atlas'
elif environment == 'prod':
    api_server = 'https://wwh1.int.colorado.edu/atlas'
