"""
Server configuration file for Atlas

All server definitions go here.
"""
# Servers manipulate using Fabric.
serverdefs = {
    'production': {
        'webservers': [
            'wweb3.int.colorado.edu',
            'wweb4.int.colorado.edu',
            'wweb5.int.colorado.edu',
        ],
        'webserver_single': [
            'wweb4.int.colorado.edu',
        ],
        'database_servers': {
            'master': 'wdb-poolb-master.int.colorado.edu',
            'slaves': ['wdb-poolb-read1.int.colorado.edu', ],
        },
        'varnish_servers': [
            '172.20.62.71',
            '172.20.62.72',
        ],
        'memcache_servers': [
            'wmem1.int.colorado.edu:11212',
            'wmem2.int.colorado.edu:11212',
        ],
        'f5_servers': [
            'its4-f5.colorado.edu',
            'its5-f5.colorado.edu',
        ],
    },
    'test': {
        'webservers': [
            'wwebtest3.int.colorado.edu',
            'wwebtest4.int.colorado.edu',
            'wwebtest5.int.colorado.edu',
        ],
        'webserver_single': [
            'wwebtest4.int.colorado.edu',
        ],
        'database_servers': {
            'master': 'wdbtest-poolb-master.int.colorado.edu',
            'slaves': ['wdbtest-poolb-read1.int.colorado.edu', ],
        },
        'varnish_servers': [
            '172.20.62.41',
            '172.20.62.42',
        ],
        'memcache_servers': [
            'wmemtest1.int.colorado.edu:11212',
            'wmemtest2.int.colorado.edu:11212',
        ],
        'f5_servers': [
            'its6-f5.colorado.edu',
            'its7-f5.colorado.edu',
        ],
    },
    'development': {
        'webservers': [
            'wwebdev2.int.colorado.edu'
        ],
        'webserver_single': [
            'wwebdev2.int.colorado.edu',
        ],
        'database_servers': {
            'master': 'wdbdev-poolb-master.int.colorado.edu',
            'slaves': ['wdbdev-poolb-read1.int.colorado.edu', ],
        },
        'varnish_servers': [
            '172.20.62.11'
        ],
        'memcache_servers': [
            'wmemdev1.int.colorado.edu:11212'
        ],
        'f5_servers': [
            'its6-f5.colorado.edu',
            'its7-f5.colorado.edu'
        ],
    },
    'local': {
        'webservers': ['express.local'],
        'webserver_single': ['express.local'],
        'database_servers': {
            'master': 'localhost',
        },
        'varnish_servers': ['localhost'],
        'memcache_servers': ['localhost:11211'],
        'f5_servers': [],
    },
}

varnish_control_terminals = {
    'production': 'wvarn3.int.colorado.edu:6082 wvarn4.int.colorado.edu:6082',
    'test': 'wvarntest3.int.colorado.edu:6082 wvarntest4.int.colorado.edu:6082',
    'development': 'wvarndevelopment2.int.colorado.edu:6082',
    'local': 'localhost:6082',
}

# See config_local.py for switch.
nfs_mount_location = {
    'production': '/Net/hanfs/wwwng-poolb',
    'test': '/Net/hanfs-test/wwwng-poolb',
    'development': '/Net/hanfs-test/wwwng-poolb',
    'local': '/wwwng',
}

base_urls = {
    'production': 'http://www.colorado.edu',
    'test': 'http://www-test.colorado.edu',
    'development': 'http://www-development.colorado.edu',
    'local': 'http://express.local',
}

f5_config_files = {
    'production': 'WWWNGProdDataGroup.dat',
    'test': 'WWWNGTestDataGroup.dat',
    'development': 'WWWNGDevDataGroup.dat',
}
# Entries in the f5 that are not sites.
f5_exceptions = [
    '/engineering/videos',
    '/law/media',
    '/catalog',
    '/p1',
]

