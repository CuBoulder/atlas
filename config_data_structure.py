import os

MONGO_HOST = os.environ.get('MONGO_HOST', 'localhost')
MONGO_PORT = os.environ.get('MONGO_PORT', 27017)
MONGO_DBNAME = os.environ.get('MONGO_DBNAME', 'atlas')

# Enable reads (GET), inserts (POST), and DELETE for resources/collections.
RESOURCE_METHODS = ['GET', 'POST']

# Enable reads (GET), edits (PATCH), replacements (PUT), and deletes of
# individual items.
ITEM_METHODS = ['GET', 'PATCH', 'PUT', 'DELETE']

#
# Definitions of schemas for Items. Schema is based on Cerberus grammar
# https://github.com/nicolaiarocci/cerberus.
#

# TODO: Add support for DNS entries that are owned as part of a site.
# TODO: Consider adding additional field to 'code' for 'has_submodules'. This would allow us to improve performance of code checkouts.

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
                'allowed': ['custom_package', 'contrib_package', 'core', 'profile'],
                'required': True,
            },
            'is_current': {
                'type': 'boolean',
                'default': False,
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
    'type': {
      'type': 'string',
      'allowed':  ['custom', 'express', 'legacy', 'homepage'],
      'default': 'express',
    },
    'status': {
        'type': 'string',
        'allowed': ['pending', 'available', 'assigned', 'assigned_training', 'launching', 'launched',  'take_down', 'down', 'restore', 'delete'],
        'default': 'pending',
    },
    'pool': {
        'type': 'string',
        'allowed': ['poolb-express', 'poola-custom', 'poola-homepage', 'poolb-homepage', 'WWWLegacy'],
        'default': 'poolb-express',
    },
    'update_group': {
        'type': 'integer',
    },
    'f5only': {
        'type': 'boolean',
        'default': False
    },
    'code': {
        'type': 'dict',
        'schema': {
            'custom_package': {
                'type': 'objectid',
                'data_relation': {
                    'resource': 'code',
                    'field': '_id',
                    'embeddable': True,
                },
            },
            'contrib_package': {
                'type': 'objectid',
                'data_relation': {
                    'resource': 'code',
                    'field': '_id',
                    'embeddable': True,
                },
            },
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
        },
    },
    'dates': {
        'type': 'dict',
        'schema': {
            # See https://docs.python.org/2/library/datetime.html#datetime.datetime for datetime format.
            'created': {
                'type': 'datetime',
            },
            'updated': {
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

command_schema = {
    'name': {
        'type': 'string',
        'minlength': 3,
        'required': True,
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
    'public_methods': ['GET'],
    'public_item_methods': ['GET'],
    'versioning': True,
    'soft_delete': True,
    'schema': sites_schema,
}

# Command resource
# Empty public_item_methods means that you can't call actual commands without
# authentication. Anonymous users can list the commands, but not call them.
command = {
    'item_title': 'command',
    'public_methods': ['GET'],
    'public_item_methods': [],
    'schema': command_schema,
}

#
# Domain definition. Tells Eve what resources are available on this domain.
#

DOMAIN = {
    'sites': sites,
    'code': code,
    'command': command,
}
