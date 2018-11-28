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
X_HEADERS = ['Access-Control-Allow-Origin', 'If-Match',
             'Authorization', 'User-Agent', 'Content-Type']

# Allow $regex filtering. Default config blocks where and regex.
MONGO_QUERY_BLACKLIST = ['$where']

# Require etags
ENFORCE_IF_MATCH = True

# Definitions of schemas for Items. Schema is based on Cerberus grammar
# https://github.com/nicolaiarocci/cerberus.

# Mongo creates the following: '_created', '_updated', '_etag', and '_id'.
# We don't use those fields in our logic because want to be able to move or
# recreate a record without losing any information.

# Code schema. Defines a code asset that can be applied to an instance.
# We nest in 'meta' to allow us to check for a unique combo
CODE_SCHEMA = {
    'meta': {
        'type': 'dict',
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
                'allowed': ['library', 'theme', 'module', 'core', 'profile', 'static'],
                'required': True,
            },
            'label': {
                'type': 'string',
                'minlength': 3,
            },
            'is_current': {
                'type': 'boolean',
                'default': False,
                'required': True,
            },
            'tag': {
                'type': 'list',
            },
        },
    },
    'deploy': {
        'type': 'dict',
        'schema': {
            'registry_rebuild': {
                'type': 'boolean',
                'default': False,
                'required': True,
            },
            'cache_clear': {
                'type': 'boolean',
                'default': True,
                'required': True,
            },
            'update_database': {
                'type': 'boolean',
                'default': True,
                'required': True,
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

QUERY_SCHEMA = {
    'title': {
        'type': 'string',
        'required': True,
    },
    'description': {
        'type': 'string',
    },
    'endpoint': {
        'type': 'list',
        'allowed': ["code", "site", "statistic"],
        'required': True,
    },
    'query': {
        'type': 'string',
        'unique': True,
    },
    'tags': {
        'type': 'list',
        'schema': {
            'type': 'string',
        }
    },
    'rank': {
        'type': 'integer',
    },
    'created_by': {
        'type': 'string',
    },
    'modified_by': {
        'type': 'string',
    },
}

# Site schema.
SITES_SCHEMA = {
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
        'allowed':  ['express'],
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
            'locked',
            'take_down',
            'down',
            'restore',
        ],
        'default': 'pending',
    },
    'environment': {
        'type': 'string',
        'allowed': [
            'local',
            'dev',
            'test',
            'prod'
        ],
    },
    'update_group': {
        'type': 'integer',
    },
    'settings': {
        'type': 'dict',
        'schema': {
            'page_cache_maximum_age': {
                'type': 'integer',
                'default': 10800,
            },
            'siteimprove_site': {
                'type': 'integer',
            },
            'siteimprove_group': {
                'type': 'integer',
            },
            'cse_creator': {
                'type': 'string',
            },
            'cse_id': {
                'type': 'string',
            },
            'google_tag_client_container_id': {
                'type': 'string',
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
            # See https://docs.python.org/2/library/datetime.html#datetime.datetime for format.
            'created': {
                'type': 'datetime',
            },
            'assigned': {
                'type': 'datetime',
            },
            'launched': {
                'type': 'datetime',
            },
            'locked': {
                'type': 'datetime',
            },
            'taken_down': {
                'type': 'datetime',
                'nullable': True,
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
    'install': {
        'type': 'boolean',
        'default': True,
        'nullable': True,
    },
}

STATISTICS_SCHEMA = {
    'site': {
        'type': 'objectid',
        'data_relation': {
            'resource': 'sites',
            'field': '_id',
        },
        'required': True,
        'unique': True,
    },
    'name': {
        'type': 'string',
        'minlength': 1,
        'nullable': True,
    },
    'status': {
        'type': 'string',
        'minlength': 1,
        'nullable': True,
    },
    'nodes_total': {
        'type': 'integer',
        'nullable': True,
    },
    'node_revision_total': {
        'type': 'integer',
        'nullable': True,
    },
    'nodes_by_type': {
        'type': 'dict',
        'nullable': True,
        'schema': {
            'page': {'type': 'integer', 'nullable': True},
            'file': {'type': 'integer', 'nullable': True},
            'faqs': {'type': 'integer', 'nullable': True},
            'content_list_page': {'type': 'integer', 'nullable': True},
            'webform': {'type': 'integer', 'nullable': True},
            'article': {'type': 'integer', 'nullable': True},
            'article_list_page': {'type': 'integer', 'nullable': True},
            'person': {'type': 'integer', 'nullable': True},
            'person_list_page': {'type': 'integer', 'nullable': True},
            'photo_gallery': {'type': 'integer', 'nullable': True},
            'full_html': {'type': 'integer', 'nullable': True},
        },
    },
    'nodes_other': {
        'type': 'string',
        'nullable': True,
    },
    'days_since_last_edit': {
        'type': 'integer',
        'nullable': True,
    },
    'days_since_last_login': {
        'type': 'integer',
        'nullable': True,
    },
    'beans_total': {
        'type': 'integer',
        'nullable': True,
    },
    'beans_by_type': {
        'type': 'dict',
        'nullable': True,
        'schema': {
            'hero_unit': {'type': 'integer', 'nullable': True},
            'slider': {'type': 'integer', 'nullable': True},
            'block': {'type': 'integer', 'nullable': True},
            'content_list': {'type': 'integer', 'nullable': True},
            'feature_callout': {'type': 'integer', 'nullable': True},
            'quicktab': {'type': 'integer', 'nullable': True},
            'video_reveal': {'type': 'integer', 'nullable': True},
            'block_row': {'type': 'integer', 'nullable': True},
            'block_section': {'type': 'integer', 'nullable': True},
            'cu_events_calendar_block': {'type': 'integer', 'nullable': True},
            'events_calendar_grid': {'type': 'integer', 'nullable': True},
            'rss': {'type': 'integer', 'nullable': True},
            'articles': {'type': 'integer', 'nullable': True},
            'article_feature': {'type': 'integer', 'nullable': True},
            'article_grid': {'type': 'integer', 'nullable': True},
            'article_slider': {'type': 'integer', 'nullable': True},
            'people_list_block': {'type': 'integer', 'nullable': True},
            'social_links': {'type': 'integer', 'nullable': True},
            'facebook_activity': {'type': 'integer', 'nullable': True},
            'facebook_like_button': {'type': 'integer', 'nullable': True},
            'twitter_block': {'type': 'integer', 'nullable': True},
            'full_html': {'type': 'integer', 'nullable': True},
        },
    },
    'beans_other': {
        'type': 'string',
        'nullable': True,
    },
    'context': {
        'type': 'dict',
        'nullable': True,
        'schema': {
            'condition': {
                'type': 'dict',
                'nullable': True,
                'schema': {
                    'context': {'type': 'integer', 'nullable': True},
                    'context_all': {'type': 'integer', 'nullable': True},
                    'default': {'type': 'integer', 'nullable': True},
                    'layout': {'type': 'integer', 'nullable': True},
                    'menu': {'type': 'integer', 'nullable': True},
                    'node': {'type': 'integer', 'nullable': True},
                    'node_taxonomy': {'type': 'integer', 'nullable': True},
                    'path': {'type': 'integer', 'nullable': True},
                    'query_param': {'type': 'integer', 'nullable': True},
                    'query_string': {'type': 'integer', 'nullable': True},
                    'sitewide': {'type': 'integer', 'nullable': True},
                    'sitewide_public': {'type': 'integer', 'nullable': True},
                    'taxonomy_term': {'type': 'integer', 'nullable': True},
                    'user': {'type': 'integer', 'nullable': True},
                    'user_page': {'type': 'integer', 'nullable': True},
                    'views': {'type': 'integer', 'nullable': True},
                },
            },
            'reaction': {
                'type': 'dict',
                'nullable': True,
                'schema': {
                    'backstretch': {'type': 'integer', 'nullable': True},
                    'block': {'type': 'integer', 'nullable': True},
                    'breadcrumb': {'type': 'integer', 'nullable': True},
                    'column_override': {'type': 'integer', 'nullable': True},
                    'cu_share': {'type': 'integer', 'nullable': True},
                    'menu': {'type': 'integer', 'nullable': True},
                    'region': {'type': 'integer', 'nullable': True},
                    'template_suggestions': {'type': 'integer', 'nullable': True},
                    'theme': {'type': 'integer', 'nullable': True},
                    'theme_html': {'type': 'integer', 'nullable': True},
                    'title_image': {'type': 'integer', 'nullable': True},
                },
            },
        },
    },
    'context_other_conditions': {
        'type': 'string',
        'nullable': True,
    },
    'context_other_reactions': {
        'type': 'string',
        'nullable': True,
    },
    'variable_cron_last': {
        'type': 'integer',
        'nullable': True,
    },
    'variable_site_403': {
        'type': 'string',
        'nullable': True,
    },
    'variable_site_404': {
        'type': 'string',
        'nullable': True,
    },
    'variable_theme_default': {
        'type': 'string',
        'nullable': True,
    },
    'variable_ga_account': {
        'type': 'string',
        'nullable': True,
    },
    'variable_livechat_license_number': {
        'type': 'string',
        'nullable': True,
    },
    'profile_module_manager': {
        'type': 'string',
        'nullable': True,
    },
    'express_code_version': {
        'type': 'string',
        'nullable': True,
    },
    'express_core_schema_version': {
        'type': 'integer',
        'nullable': True,
    },
    'theme_is_responsive': {
        'type': 'boolean',
        'nullable': True,
    },
    'overridden_features': {
        'type': 'dict',
        'nullable': True,
    },
    'drupal_system_status': {
        'type': 'boolean',
        'nullable': True,
    },
    'custom_logo_settings': {
        'type': 'boolean',
        'nullable': True,
    },
    'users': {
        'type': 'dict',
        'nullable': True,
        'schema': {
            'email_address': {
                'type': 'dict',
                'nullable': True,
                'schema': {
                    'site_owner': {
                        'type': 'list',
                        'nullable': True,
                    },
                    'content_editor': {
                        'type': 'list',
                        'nullable': True,
                    },
                    'edit_my_content': {
                        'type': 'list',
                        'nullable': True,
                    },
                    'site_editor': {
                        'type': 'list',
                        'nullable': True,
                    },
                    'access_manager': {
                        'type': 'list',
                        'nullable': True,
                    },
                    'campaign_manager': {
                        'type': 'list',
                        'nullable': True,
                    },
                    'configuration_manager': {
                        'type': 'list',
                        'nullable': True,
                    },
                    'form_manager': {
                        'type': 'list',
                        'nullable': True,
                    },
                },
            },
            'username': {
                'type': 'dict',
                'nullable': True,
                'schema': {
                    'site_owner': {
                        'type': 'list',
                        'nullable': True,
                    },
                    'content_editor': {
                        'type': 'list',
                        'nullable': True,
                    },
                    'edit_my_content': {
                        'type': 'list',
                        'nullable': True,
                    },
                    'site_editor': {
                        'type': 'list',
                        'nullable': True,
                    },
                    'access_manager': {
                        'type': 'list',
                        'nullable': True,
                    },
                    'campaign_manager': {
                        'type': 'list',
                        'nullable': True,
                    },
                    'configuration_manager': {
                        'type': 'list',
                        'nullable': True,
                    },
                    'form_manager': {
                        'type': 'list',
                        'nullable': True,
                    },
                },
            },
            'no_valid_owner': {
                'type': 'boolean',
                'nullable': True,
            },
            'counts': {
                'type': 'dict',
                'nullable': True,
                'schema': {
                    'site_owner': {
                        'type': 'integer',
                        'nullable': True,
                    },
                    'content_editor': {
                        'type': 'integer',
                        'nullable': True,
                    },
                    'edit_my_content': {
                        'type': 'integer',
                        'nullable': True,
                    },
                    'site_editor': {
                        'type': 'integer',
                        'nullable': True,
                    },
                    'access_manager': {
                        'type': 'integer',
                        'nullable': True,
                    },
                    'campaign_manager': {
                        'type': 'integer',
                        'nullable': True,
                    },
                    'configuration_manager': {
                        'type': 'integer',
                        'nullable': True,
                    },
                    'form_manager': {
                        'type': 'integer',
                        'nullable': True,
                    },
                },
            },
        },
    },
    'bundles': {
        'type': 'dict',
        'nullable': True,
        'schema': {
            'cu_advanced_content_bundle': {
                'type': 'dict',
                'nullable': True,
                'schema': {
                    'schema_version': {
                        'type': 'integer',
                        'nullable': True,
                    },
                },
            },
            'cu_advanced_design_bundle': {
                'type': 'dict',
                'nullable': True,
                'schema': {
                    'schema_version': {
                        'type': 'integer',
                        'nullable': True,
                    },
                },
            },
            'cu_advanced_layout_bundle': {
                'type': 'dict',
                'nullable': True,
                'schema': {
                    'schema_version': {
                        'type': 'integer',
                        'nullable': True,
                    },
                },
            },
            'cu_events_bundle': {
                'type': 'dict',
                'nullable': True,
                'schema': {
                    'schema_version': {
                        'type': 'integer',
                        'nullable': True,
                    },
                },
            },
            'cu_feeds_bundle': {
                'type': 'dict',
                'nullable': True,
                'schema': {
                    'schema_version': {
                        'type': 'integer',
                        'nullable': True,
                    },
                },
            },
            'cu_forms_bundle': {
                'type': 'dict',
                'nullable': True,
                'schema': {
                    'schema_version': {
                        'type': 'integer',
                        'nullable': True,
                    },
                },
            },
            'cu_news_bundle': {
                'type': 'dict',
                'nullable': True,
                'schema': {
                    'schema_version': {
                        'type': 'integer',
                        'nullable': True,
                    },
                },
            },
            'cu_people_bundle': {
                'type': 'dict',
                'nullable': True,
                'schema': {
                    'schema_version': {
                        'type': 'integer',
                        'nullable': True,
                    },
                },
            },
            'cu_photo_gallery_bundle': {
                'type': 'dict',
                'nullable': True,
                'schema': {
                    'schema_version': {
                        'type': 'integer',
                        'nullable': True,
                    },
                },
            },
            'cu_seo_bundle': {
                'type': 'dict',
                'nullable': True,
                'schema': {
                    'schema_version': {
                        'type': 'integer',
                        'nullable': True,
                    },
                },
            },
            'cu_social_media_bundle': {
                'type': 'dict',
                'nullable': True,
                'schema': {
                    'schema_version': {
                        'type': 'integer',
                        'nullable': True,
                    },
                },
            },
            'cu_seo_admin_bundle': {
                'type': 'dict',
                'nullable': True,
                'schema': {
                    'schema_version': {
                        'type': 'integer',
                        'nullable': True,
                    },
                },
            },
            'cu_test_content_admin_bundle': {
                'type': 'dict',
                'nullable': True,
                'schema': {
                    'schema_version': {
                        'type': 'integer',
                        'nullable': True,
                    },
                },
            },
            'cu_debug_admin_bundle': {
                'type': 'dict',
                'nullable': True,
                'schema': {
                    'schema_version': {
                        'type': 'integer',
                        'nullable': True,
                    },
                },
            },
            'other': {
                'type': 'string',
                'nullable': True,
            },
        },
    },
    'webforms': {
        'type': 'dict',
        'nullable': True,
        'schema': {
            'total_submissions': {'type': 'integer', 'nullable': True},
            'active_forms': {'type': 'integer', 'nullable': True},
            'inactive_forms': {'type': 'integer', 'nullable': True},
        },
    },
    'created_by': {
        'type': 'string',
        'nullable': True,
    },
    'modified_by': {
        'type': 'string',
        'nullable': True,
    },
}

BACKUP_SCHEMA = {
    'state': {
        'type': 'string',
        'allowed': ['pending', 'complete'],
        'default': 'pending',
        'required': True,
    },
    'site': {
        'type': 'objectid',
        'data_relation': {
            'resource': 'sites',
            'field': '_id',
        },
        'required': True,
    },
    'site_version': {
        'type': 'integer',
        'required': True,
    },
    'backup_date': {
        'type': 'datetime',
    },
    'backup_type': {
        'type': 'string',
        'allowed': ['on_demand', 'update', 'routine'],
        'default': 'routine',
        'required': True,
    },
    'files': {
        'type': 'string',
    },
    'database': {
        'type': 'string',
    },
    'created_by': {
        'type': 'string',
    },
    'modified_by': {
        'type': 'string',
    },
}

DRUSH_SCHEMA = {
    'label': {
        'type': 'string',
        'required': True,
    },
    'commands': {
        'type': 'list',
        'schema': {
            'type': 'string',
            'minlength': 5,
        },
        'required': True,
        'unique': True,
    },
    # String that is stored needs to be posted with Unicode character encodings
    'query': {
        'type': 'string',
        'minlength': 9,
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
CODE = {
    'item_title': 'code',
    'public_methods': ['GET'],
    'public_item_methods': ['GET'],
    'versioning': True,
    'soft_delete': True,
    'schema': CODE_SCHEMA,
}

# Query resource
QUERY = {
    'item_title': 'query',
    'public_methods': ['GET'],
    'public_item_methods': ['GET'],
    'versioning': True,
    'schema': QUERY_SCHEMA,
}

# Sites resource
SITES = {
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
    'schema': SITES_SCHEMA,
}

# Statistics resource
STATISTICS = {
    'item_title': 'statistics',
    'public_methods': ['GET'],
    'public_item_methods': ['GET'],
    'versioning': True,
    'soft_delete': True,
    'schema': STATISTICS_SCHEMA,
}

# Backup resource
BACKUP = {
    'item_title': 'backup',
    'public_methods': ['GET'],
    'public_item_methods': ['GET'],
    'schema': BACKUP_SCHEMA,
}

# Drush resource
DRUSH = {
    'item_title': 'drush',
    'public_methods': ['GET'],
    'public_item_methods': ['GET'],
    'versioning': True,
    'schema': DRUSH_SCHEMA,
}

# Domain definition. Tells Eve what resources are available on this domain.
DOMAIN = {
    'sites': SITES,
    'code': CODE,
    'drush': DRUSH,
    'query': QUERY,
    'statistics': STATISTICS,
    'backup': BACKUP,
}
