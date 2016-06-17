"""
Server configuration file for Atlas

All server definitions go here.
"""
platforms = {
    'poola-custom': {
        'prod': ['wweb1', 'wweb2'],
        'test': ['wwebtest1', 'wwebtest2'],
        'stage': ['wstage1'],
        'dev': ['wwebdev1'],
    },
    'poolb-express': {
        'prod': ['wweb3', 'wweb4', 'wweb5'],
        'test': ['wwebtest3', 'wwebtest4', 'wwebtest5'],
        'dev': ['wwebdev2'],
        'local': ['express.local'],
    },
    'poolb-homepage': {
        'prod': ['wweb3', 'wweb4', 'wweb5'],
        'test': ['wwebtest3', 'wwebtest4', 'wwebtest5'],
        'dev': ['wwebdev2'],
        'local': ['express.local'],
    },
}

base_urls = {
    'prod': 'http://www.colorado.edu',
    'test': 'http://www-test.colorado.edu',
    'stage': 'http://www-stage.colorado.edu',
    'dev': 'http://www-dev.colorado.edu',
    'local': 'http://express.local',
}

# Fabric uses this and the environment variable to determine which F5 servers
# to update. DEV and TEST share an f5, but have separate config files on the
# servers.
f5_servers = {
    'prod': ['uctool@its4-f5.colorado.edu', 'uctool@its5-f5.colorado.edu'],
    'test': ['uctool@its6-f5.colorado.edu', 'uctool@its7-f5.colorado.edu'],
    'dev': ['uctool@its6-f5.colorado.edu', 'uctool@its7-f5.colorado.edu'],
    'local': [],
}

# f5 conf filename per environment.
f5_config_files = {
    'prod': 'WWWNGProdDataGroup.dat',
    'test': 'WWWNGTestDataGroup.dat',
    'dev': 'WWWNGDevDataGroup.dat',
}
# Entries in the f5 that are not sites.
f5_exceptions = [
    '/engineering/videos',
    '/law/media',
    '/catalog',
    '/p1',
]

# Varnish server IP addresses.
varnish_servers = {
    'prod': ['172.20.62.71', '172.20.62.72', ],
    'stage': ['128.138.128.61', ],
    'test': ['172.20.62.41', '172.20.62.42', ],
    'dev': ['172.20.62.11', ],
    'local': ['localhost'],
}

# Varnish control terminals. Separate multiple for a given environment with a
# space.
varnish_control_terminals = {
    'prod': 'wvarn3.int.colorado.edu:6082 wvarn4.int.colorado.edu:6082',
    'stage': 'wstage1.colorado.edu:6082',
    'test': 'wvarntest3.int.colorado.edu:6082 wvarntest4.int.colorado.edu:6082',
    'dev': 'wvarndev2.int.colorado.edu:6082',
    'local': 'localhost:6082',
}

# Memcache servers.
memcache_servers = {
    'prod': ['wmem1.int.colorado.edu:11212', 'wmem2.int.colorado.edu:11212', ],
    'stage': ['wstage1.colorado.edu:11211', ],
    'test': ['wmemtest1.int.colorado.edu:11212', 'wmemtest2.int.colorado.edu:11212', ],
    'dev': ['wmemdev1.int.colorado.edu:11211', ],
    'local': ['localhost:11211'],
}