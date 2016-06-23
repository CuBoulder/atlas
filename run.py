import sys
import logging

from eve import Eve
from atlas import tasks
from atlas import utilities
from atlas.config import *


path = '/data/code'
if path not in sys.path:
    sys.path.append(path)

# Callbacks
def pre_post_code_callback(request):
    """
    Hook into 'code' create events *before* the Mongo object is created.

    Set 'code.meta.is_current' for items with the same meta data to False.

    :param request: original flask.request object
                    request.json["meta"]["name"],
                    request.json["git_url"],
                    request.json["commit_hash"],
                    request.json["meta"]["version"],
                    request.json["meta"]["code_type"],
                    request.json["meta"]["is_current"]
    :return:
    """
    # Need a lowercase string when querying boolean values. Python
    # stores it as 'True'.
    query = 'where={{"meta.name":"{0}","meta.code_type":"{1}","meta.is_current": {2}}}'.format(request.json['meta']['name'], request.json['meta']['code_type'], str(request.json['meta']['is_current']).lower())
    app.logger.debug(query)
    code_get = utilities.get_eve('code', query)
    app.logger.debug(code_get)
    for code in code_get['_items']:
        request_payload = {'meta.is_current': False}
        utilities.patch_eve('code', code['_id'], code['_etag'], request_payload)


def post_post_callback(resource, request, payload):
    """
    Callback for POST to all endpoints.

    Hook into any create event *after* the Mongo object is created.

    :param resource: resource accessed
    :param request: original flask.request object
    :param payload: the response payload from Eve
    """
    app.logger.debug(request.json)


def post_post_code_callback(request, payload):
    """
    Callback for POST to `code` endpoint.

    Hook into 'code' create events *after* the Mongo object is created.

    :param request: original flask.request object
                    request.json["meta"]["name"],
                    request.json["git_url"],
                    request.json["commit_hash"],
                    request.json["meta"]["version"],
                    request.json["meta"]["code_type"],
                    request.json["meta"]["is_current"]

    :param payload: response payload
    :return:
    """
    app.logger.debug(payload.__dict__)
    # Verify that the POST was successful before we do anything else.
    # Status code '201 Created'.
    if payload._status_code == 201:
        deploy_result = tasks.code_deploy.delay(request.json)



def post_post_site_callback(request, payload):
    """
    Callback for POST to `code` endpoint.

    Allows us to hook into 'site' create events *after* the Mongo object has been created.

    :param request: original flask.request object
    :param payload: response payload
    :return:
    """
    tasks.site_provison.delay(request.json)


def post_get_command_callback(request, payload):
    """
    Callback for GET to `command` endpoint.

    Allows us to run commands when API endpoints are called.

    :param resource: resource accessed
    :param request: original flask.request object
    :param payload: response payload
    :return:
    """
    tasks.command_run.delay(request.json)

# TODO: Set it up to mark what user updated the record.
# auto fill _created_by and _modified_by user fields
# created_by_field = '_created_by'
# modified_by_field = '_modified_by'
# for resource in settings['DOMAIN']:
#     settings['DOMAIN'][resource]['schema'][created_by_field] = {'type': 'string'}
#     settings['DOMAIN'][resource]['schema'][modified_by_field] = {'type': 'string'}
# def pre_insert(resource, documents):
#     user = g.get('user', None)
#     if user is not None:
#         for document in documents:
#             document[created_by_field] = user
#             document[modified_by_field] = user
# def pre_replace(resource, document):
#     user = g.get('user', None)
#     if user is not None:
#         document[modified_by_field] = user


# TODO: Add in a message (DONE) and better result broker, I don't want to use the DB. It is currently 41 GB for inventory.


"""
Setup the application and logging.
"""
# Tell Eve to use Basic Auth and where our data structure is defined.
app = Eve(auth=utilities.AtlasBasicAuth, settings="/data/code/atlas/config_data_structure.py")
# TODO: Remove debug mode.
app.debug = True

# Add specific callbacks
# Pattern is: `atlas.on_{Hook}_{Method}_{Resource}`
#app.on_pre_POST += pre_post_callback
#app.on_insert += pre_insert
#app.on_replace += pre_replace
app.on_pre_POST_code += pre_post_code_callback
app.on_post_POST += post_post_callback
app.on_post_POST_code += post_post_code_callback
app.on_post_POST_site += post_post_site_callback
app.on_post_GET_command += post_get_command_callback


if __name__ == '__main__':
    # Enable logging to 'atlas.log' file
    # TODO: Figure out why the stuff shows in the apache error log, not this location.
    handler = logging.FileHandler('atlas.log')
    # The default log level is set to WARNING, so we have to explicitly set the
    # logging level to Debug.
    app.logger.setLevel(logging.DEBUG)
    # Append the handler to the default application logger
    app.logger.addHandler(handler)

    # This goes last.
    app.run(host='0.0.0.0', ssl_context='adhoc')
