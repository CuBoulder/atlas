import os

MONGO_HOST = os.environ.get('MONGO_HOST', 'localhost')
MONGO_PORT = os.environ.get('MONGO_PORT', 27017)
MONGO_DBNAME = os.environ.get('MONGO_DBNAME', 'atlas')

DATE_FORMAT = '%Y-%m-%d %H:%M:%S GMT'

# Enable reads (GET), inserts (POST), and DELETE for resources/collections.
RESOURCE_METHODS = ['GET', 'POST']

# Enable reads (GET), edits (PATCH), replacements (PUT), and deletes of
# individual items.
ITEM_METHODS = ['GET', 'PATCH', 'PUT', 'DELETE']

# Add support for CORS
X_DOMAINS = '*'
X_HEADERS = ['Access-Control-Allow-Origin']
#
# Definitions of schemas for Items. Schema is based on Cerberus grammar
# https://github.com/nicolaiarocci/cerberus.
#

# Mongo creates the following: '_created', '_updated', '_etag', and '_id'.
# We don't use those fields in our logic because want to be able to move or
# recreate a record without losing any information.

# Code schema. Defines a code asset that can be applied to a site.
# We nest in 'meta' to allow us to check for a unique combo
code_schema = {
    'meta': {
        'type': 'dict',
        'required': True,
        'unique': True,
        'schema': {
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
            'code_type': {
                'type': 'string',
                'allowed': ['library', 'theme', 'module', 'core', 'profile'],
                'required': True,
            },
            'is_current': {
                'type': 'boolean',
                'default': False,
            },
            'tag': {
                'type': 'list',
            },
        },
    },
    'git_url': {
        'type': 'string',
        'regex': '((git|ssh|http(s)?)|(git@[\w\.]+))(:(//)?)([\w\.@\:/\-~]+)(\.git)(/)?',
        'required': True,
    },
    'commit_hash': {
        'type': 'string',
        'required': True,
        'unique': True
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
    },
    'sid': {
      'type': 'string',
      'minlength': 9,
      'maxlength': 14,
      'unique': True,
      'readonly': True,
    },
    'type': {
      'type': 'string',
      'allowed':  ['custom', 'express', 'legacy', 'homepage'],
      'default': 'express',
    },
    'status': {
        'type': 'string',
        'allowed': [
            'pending',
            'available',
            'installing',
            'installed',
            'launching',
            'launched',
            'take_down',
            'down',
            'restore',
            'delete'
        ],
        'default': 'pending',
    },
    'pool': {
        'type': 'string',
        'allowed': [
            'poolb-express',
            'poola-custom',
            'poolb-homepage',
            'WWWLegacy'],
        'default': 'poolb-express',
    },
    'update_group': {
        'type': 'integer',
    },
    'f5only': {
        'type': 'boolean',
        'default': False
    },
    'tag': {
        'type': 'list',
    },
    'code': {
        'type': 'dict',
        'schema': {
            'core': {
                'type': 'objectid',
                'data_relation': {
                    'resource': 'code',
                    'field': '_id',
                    'embeddable': True,
                },
            },
            'profile': {
                'type': 'objectid',
                'data_relation': {
                    'resource': 'code',
                    'field': '_id',
                    'embeddable': True,
                },
            },
            'package': {
                'type': 'list',
                'schema': {
                    'type': 'objectid',
                    'data_relation': {
                        'resource': 'code',
                        'field': '_id',
                        'embeddable': True,
                    },
                }
            },
        },
    },
    'dates': {
        'type': 'dict',
        'schema': {
            # See https://docs.python.org/2/library/datetime.html#datetime.datetime for datetime format.
            'created': {
                'type': 'datetime',
            },
            'assigned': {
                'type': 'datetime',
            },
            'launched': {
                'type': 'datetime',
            },
            'taken_down': {
                'type': 'datetime',
            },
        },
    },
}

commands_schema = {
    'name': {
        'type': 'string',
        'minlength': 3,
        'required': True,
    },
    'command': {
        'type': 'string',
        'minlength': 3,
        'required': True,
    },
    # String that is stored needs to be posted with Unicode character encodings
    'query': {
        'type': 'string',
        'minlength': 9,
    },
    'single_server': {
        'type': 'boolean',
        'required': True,
        'default': True,
    },
}

"""
Definitions of Resources.
Tells Eve what methods and schemas apply to a given resource.
"""
# Code resource
code = {
    'item_title': 'code',
    'public_methods': ['GET'],
    'public_item_methods': ['GET'],
    'versioning': True,
    'soft_delete': True,
    'schema': code_schema,
}

# Sites resource
sites = {
    'item_title': 'site',
    # Allow lookup by 'sid' in addition to '_id'
    'additional_lookup': {
        'url': 'regex("[\w]+")',
        'field': 'sid'
    },
    'embedded_fields': ['code.core', 'code.profile', 'code.package'],
    'public_methods': ['GET'],
    'public_item_methods': ['GET'],
    'versioning': True,
    'soft_delete': True,
    'schema': sites_schema,
}

# Command resource
# Empty public_item_methods means that you can't call actual commands without
# authentication. Anonymous users can list the commands, but not call them.
commands = {
    'item_title': 'commands',
    'public_methods': ['GET'],
    'public_item_methods': [],
    'versioning': True,
    'schema': commands_schema,
}

#
# Domain definition. Tells Eve what resources are available on this domain.
#

DOMAIN = {
    'sites': sites,
    'code': code,
    'commands': commands,
}
