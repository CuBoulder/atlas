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

# Allow public GET by default can override for a specific resource or item.
PUBLIC_METHODS = ['GET']

# Default to return 500 results per page. Allow up to 2000.
PAGINATION_LIMIT = 2000
PAGINATION_DEFAULT = 500

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
    'created_by': {
        'type': 'string',
    },
    'modified_by': {
        'type': 'string',
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
    'environment': {
        'type': 'string',
        'allowed': [
            'local',
            'development',
            'test',
            'production'
        ],
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
    'import_from_inventory': {
        'type': 'boolean',
        'default': False
    },
    'settings': {
        'type': 'dict',
        'schema': {
            'page_cache_maximum_age': {
                'type': 'integer',
                'default': 300,
            },
        },
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
    'statistics': {
        'type': 'objectid',
        'data_relation': {
            'resource': 'statistics',
            'field': '_id',
            'embeddable': True,
            'unique': True,
        },
    },
    'created_by': {
        'type': 'string',
    },
    'modified_by': {
        'type': 'string',
    },
}

statistics_schema = {
    'site': {
        'type': 'objectid',
        'data_relation': {
            'resource': 'sites',
            'field': '_id',
        },
        'required': True,
        'unique': True,
    },
    'nodes_total': {
        'type': 'integer',
    },
    'nodes_by_type': {
        'type': 'dict',
        'schema': {
            'number_nodes_page': {'type': 'integer'},
            'number_nodes_file': {'type': 'integer'},
            'number_nodes_faq': {'type': 'integer'},
            'number_nodes_content_list_page': {'type': 'integer'},
            'number_nodes_webform': {'type': 'integer'},
            'number_nodes_article': {'type': 'integer'},
            'number_nodes_article_list_page': {'type': 'integer'},
            'number_nodes_person': {'type': 'integer'},
            'number_nodes_person_list_page': {'type': 'integer'},
            'number_nodes_photo_gallery': {'type': 'integer'},
        },
    },
    'days_since_last_edit': {
        'type': 'integer',
    },
    'beans_total': {
        'type': 'integer',
    },
    'beans_by_type': {
        'type': 'dict',
        'schema': {
            'number_beans_hero_unit': {'type': 'integer'},
            'number_beans_slider': {'type': 'integer'},
            'number_beans_block': {'type': 'integer'},
            'number_beans_content_list': {'type': 'integer'},
            'number_beans_feature_callout': {'type': 'integer'},
            'number_beans_quicktab': {'type': 'integer'},
            'number_beans_video_reveal': {'type': 'integer'},
            'number_beans_block_row': {'type': 'integer'},
            'number_beans_block_section': {'type': 'integer'},
            'number_beans_cu_events_calendar_block': {'type': 'integer'},
            'number_beans_events_calendar_grid': {'type': 'integer'},
            'number_beans_rss': {'type': 'integer'},
            'number_beans_articles': {'type': 'integer'},
            'number_beans_article_feature': {'type': 'integer'},
            'number_beans_article_grid': {'type': 'integer'},
            'number_beans_article_slider': {'type': 'integer'},
            'number_beans_people_list_block': {'type': 'integer'},
            'number_beans_social_links': {'type': 'integer'},
            'number_beans_facebook_activity': {'type': 'integer'},
            'number_beans_facebook_like_button': {'type': 'integer'},
            'number_beans_twitter_block': {'type': 'integer'},
        },
    },
    'variable_cron_last': {
        'type': 'integer',
    },
    'variable_site_403': {
        'type': 'string',
    },
    'variable_site_404': {
        'type': 'string',
    },
    'variable_theme_default': {
        'type': 'string',
    },
    'variable_ga_account': {
        'type': 'string',
    },
    'profile_module_manager': {
        'type': 'string',
    },
    'express_code_version': {
        'type': 'string',
    },
    'express_core_schema_version': {
        'type': 'integer',
    },
    'theme_is_responsive': {
        'type': 'boolean',
    },
    'overridden_features': {
        'type': 'dict',
    },
    'users': {
        'type': 'dict',
        'schema': {
            'email_address': {
                'type': 'list',
            },
            'username': {
                'type': 'list',
            },
        },
    },
    'bundles': {
        'type': 'dict',
        'schema': {
            'cu_advanced_content_bundle': {
                'type': 'dict',
                'schema': {
                    'schema_version': {
                        'type': 'integer',
                    },
                },
            },
            'cu_advanced_design_bundle': {
                'type': 'dict',
                'schema': {
                    'schema_version': {
                        'type': 'integer',
                    },
                },
            },
            'cu_advanced_layout_bundle': {
                'type': 'dict',
                'schema': {
                    'schema_version': {
                        'type': 'integer',
                    },
                },
            },
            'cu_events_bundle': {
                'type': 'dict',
                'schema': {
                    'schema_version': {
                        'type': 'integer',
                    },
                },
            },
            'cu_feeds_bundle': {
                'type': 'dict',
                'schema': {
                    'schema_version': {
                        'type': 'integer',
                    },
                },
            },
            'cu_forms_bundle': {
                'type': 'dict',
                'schema': {
                    'schema_version': {
                        'type': 'integer',
                    },
                },
            },
            'cu_news_bundle': {
                'type': 'dict',
                'schema': {
                    'schema_version': {
                        'type': 'integer',
                    },
                },
            },
            'cu_people_bundle': {
                'type': 'dict',
                'schema': {
                    'schema_version': {
                        'type': 'integer',
                    },
                },
            },
            'cu_photo_gallery_bundle': {
                'type': 'dict',
                'schema': {
                    'schema_version': {
                        'type': 'integer',
                    },
                },
            },
            'cu_seo_bundle': {
                'type': 'dict',
                'schema': {
                    'schema_version': {
                        'type': 'integer',
                    },
                },
            },
            'cu_social_media_bundle': {
                'type': 'dict',
                'schema': {
                    'schema_version': {
                        'type': 'integer',
                    },
                },
            },
            'cu_seo_admin_bundle': {
                'type': 'dict',
                'schema': {
                    'schema_version': {
                        'type': 'integer',
                    },
                },
            },
            'cu_test_content_admin_bundle': {
                'type': 'dict',
                'schema': {
                    'schema_version': {
                        'type': 'integer',
                    },
                },
            },
            'cu_debug_admin_bundle': {
                'type': 'dict',
                'schema': {
                    'schema_version': {
                        'type': 'integer',
                    },
                },
            },
        },
    },
    'created_by': {
        'type': 'string',
    },
    'modified_by': {
        'type': 'string',
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
    'created_by': {
        'type': 'string',
    },
    'modified_by': {
        'type': 'string',
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
    'public_methods': ['GET'],
    'public_item_methods': ['GET'],
    'versioning': True,
    'soft_delete': True,
    'schema': sites_schema,
}

# Statistics resource
statistics = {
    'item_title': 'statistics',
    'public_methods': ['GET'],
    'public_item_methods': ['GET'],
    'versioning': True,
    'soft_delete': True,
    'schema': statistics_schema,
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
    'statistics': statistics,
}
