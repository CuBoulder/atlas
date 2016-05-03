# We are going to use a local mongod instance. MONGO_HOST and MONGO_PORT default
# to these values, but we are being explicit.
MONGO_HOST = 'localhost'
MONGO_PORT = 27017
MONGO_DBNAME = 'atlas'

# Enable reads (GET), inserts (POST) and DELETE for resources/collections.
RESOURCE_METHODS = ['GET', 'POST', 'DELETE']

# Enable reads (GET), edits (PATCH), and deletes of individual items.
ITEM_METHODS = ['GET', 'PATCH', 'DELETE']

##
## Schemas
##

# Mongo creates the following: '_created', '_updated', '_etag', and '_id'.
# We don't use those fields in logic because want to be able to move or recreate
# a record without losing information.
# Schema is based on Cerberus grammer https://github.com/nicolaiarocci/cerberus.

# Code schema. Defines a code asset that can be applied to a site.
code_schema = {
    'versioning': True,
    'name': {
        'type': 'string',
        'minlength': 3,
        'required': True,
    },
    'version': {
        'type': 'string',
        'minlength': 1,
        'required': True,
    },
    'type': {
        'type': 'string',
        'allowed':  ['custom_package', 'contrib_package', 'drupal_core', 'profile'],
        'required': True,
    },
    'git_url': {
        'type': 'string',
        'regex': 'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
        'required': True,
    },
    'commit_hash': {
        'type': 'string',
        'required': True,
    },
    # See https://docs.python.org/2/library/datetime.html#datetime.datetime for datetime format.
    'date_created': {
        'type': 'datetime',
        'required': True,
        'readonly': True,
    },
    'date_updated': {
        'type': 'datetime',
        'required': True,
        'readonly': True,
    },
}

# Site schema.
sites_schema = {
    'name': {
      'type': 'string',
      'minlength': 1,
    },
    'path': {
      'type': 'string',
      'unique': True,
    },
    'db_key': {
      'type': 'string',
      'minlength': 1,
      'maxlength': 128,
    },
    'sid': {
      'type': 'string',
      'minlength': 9,
      'maxlength': 14,
      'unique': True,
      'readonly': True,
    },
    'type' : {
      'type': 'string',
      'allowed':  ['custom', 'express', 'legacy', 'homepage'],
      'default': 'express',
    },
    'status': {
        'type': 'string',
        'allowed': ['pending', 'available', 'installed', 'launching', 'launched',  'take_down', 'down', 'restore', 'delete'],
        'default': 'pending',
    },
    'pool': {
        'type': 'string',
        'allowed': ['poolb-express', 'poola-custom', 'poola-homepage', 'WWWLegacy'],
        'default': 'poolb-express',
    },
    'update_group': {
        'type': 'integer',
    },
    'f5only': {
        'type': 'boolean',
        'default': False,
    },
    'code': {
        'type': 'dict',
        'nullable': True,
        'schema': {
            'custom_package': {
                'type': 'list',
                'nullable': True,
            },
            'contrib_package': {
                'type': 'list',
                'nullable': True,
            },
            'drupal_core': {
                'type': 'string',
                'nullable': True,
            },
        },
    },
    # We are wrapping the first 'dict' in a list so that we can 'null' the whole thing.
    'statistics': {
        'type': 'list',
        'nullable': True,
        'schema': {
            'type': 'dict',
            'allow_unknown': True,
            'schema': {
                'var_grid_size': {'type': 'string'},
                'var_site_403': {'type': 'string'},
                'var_site_404': {'type': 'string'},
                'var_theme_default': {'type': 'string'},
                'var_ga_account': {'type': 'string'},
                'var_livechat_license_number': {'type': 'string'},
                'var_inactive_30_email': {'type': 'boolean'},
                'var_inactive_55_email': {'type': 'boolean'},
                'var_inactive_60_email': {'type': 'boolean'},
                'var_cron_last': {'type': 'integer'},
                'num_days_since_last_edit': {'type': 'integer'},
                'num_nodes': {'type': 'integer'},
                'num_beans': {'type': 'integer'},
            },
        },
    },
}
