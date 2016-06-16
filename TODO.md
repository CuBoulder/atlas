# TODO: Deal with this stuff from the config.py file server definitions

base_urls = {
    'prod': 'http://www.colorado.edu',
    'test': 'http://www-test.colorado.edu',
    'stage': 'http://www-stage.colorado.edu',
    'dev': 'http://www-dev.colorado.edu',
    'local': 'http://express.local',
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


