import os

MONGO_HOST = os.environ.get('MONGO_HOST', 'localhost')
MONGO_PORT = os.environ.get('MONGO_PORT', 27017)
MONGO_DBNAME = os.environ.get('MONGO_DBNAME', 'atlas')

# Enable reads (GET), inserts (POST), and DELETE for resources/collections.
RESOURCE_METHODS = ['GET', 'POST', 'DELETE']

# Enable reads (GET), edits (PATCH), replacements (PUT), and deletes of
# individual items.
ITEM_METHODS = ['GET', 'PATCH', 'PUT', 'DELETE']

#
# Definitions of schemas for Items. Schema is based on Cerberus grammar
# https://github.com/nicolaiarocci/cerberus.
#

# TODO: Add support for DNS entries that are owned as part of a site.

# Mongo creates the following: '_created', '_updated', '_etag', and '_id'.
# We don't use those fields in our logic because want to be able to move or
# recreate a record without losing any information.

# Code schema. Defines a code asset that can be applied to a site.
code_schema = {
    'date': {
        'type': 'dict',
        'schema': {
            # See https://docs.python.org/2/library/datetime.html#datetime.datetime for datetime format.
            'created': {
                'type': 'datetime',
                'required': True,
                'readonly': True,
            },
            'updated': {
                'type': 'datetime',
                'required': True,
                'readonly': True,
            },
        },
    },
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
        'regex': '((git|ssh|http(s)?)|(git@[\w\.]+))(:(//)?)([\w\.@\:/\-~]+)(\.git)(/)?',
        'required': True,
    },
    'commit_hash': {
        'type': 'string',
        'required': True,
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
                'type': 'dict',
                'schema': {
                    '_id': {'type': 'objectid'},
                    '_version': {'type': 'integer'}
                },
                'data_relation': {
                    'resource': 'code',
                    'field': '_id',
                    'embeddable': True,
                    'version': True,
                },
            },
            'contrib_package': {
                'type': 'dict',
                'schema': {
                    '_id': {'type': 'objectid'},
                    '_version': {'type': 'integer'}
                },
                'data_relation': {
                    'resource': 'code',
                    'field': '_id',
                    'embeddable': True,
                    'version': True,
                },
            },
            'drupal_core': {
                'type': 'dict',
                'schema': {
                    '_id': {'type': 'objectid'},
                    '_version': {'type': 'integer'}
                },
                'data_relation': {
                    'resource': 'code',
                    'field': '_id',
                    'embeddable': True,
                    'version': True,
                },
            },
            'profile': {
                'type': 'dict',
                'schema': {
                    '_id': {'type': 'objectid'},
                    '_version': {'type': 'integer'}
                },
                'data_relation': {
                    'resource': 'code',
                    'field': '_id',
                    'embeddable': True,
                    'version': True,
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
                'required': True,
            },
            'updated': {
                'type': 'datetime',
                'required': True,
            },
            'launched': {
                'type': 'datetime',
                'required': True,
            },
            'taken_down': {
                'type': 'datetime',
                'required': True,
            },
        },
    },
}

#
# Definitions of Resources. Tells Eve what methods and schemas apply to a given resource.
#

# Code resource
code = {
    'item_title': 'code',
    'resource_methods': ['GET', 'POST'],
    'public_methods': ['GET'],
    'public_item_methods': ['GET'],
    'versioning': True,
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
    'resource_methods': ['GET', 'POST'],
    'public_methods': ['GET'],
    'public_item_methods': ['GET'],
    'versioning': True,
    'schema': sites_schema,
}

#
# Domain definition. Tells Eve what resources are available on this domain.
#

DOMAIN = {
    'sites': sites,
    'code': code,
}
