"""
Configuration file for Atlas

All variable settings should go here so values can be propagated to the various
 functions from a central location.
"""

# Import config_local.py.
try:
    from config_local import *
except ImportError:
    raise Exception("You need a config_local.py file!")

# URL to eve instance, no trailing slash
if environment == 'local':
    api_server = 'http://inventory.local/atlas'
elif environment == 'dev':
    api_server = 'https://wwhdev1.int.colorado.edu/atlas'
elif environment == 'test':
    api_server = 'https://wwhtest1.int.colorado.edu/atlas'
elif environment == 'prod':
    api_server = 'https://wwh1.int.colorado.edu/atlas'
