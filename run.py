import sys
path = '/data/code'
if path not in sys.path:
    sys.path.append(path)
import ldap
import logging
import json
import datetime

# To run Ansible commands
from collections import namedtuple
from ansible.parsing.dataloader import DataLoader
from ansible.vars import VariableManager
from ansible.inventory import Inventory
from ansible.executor.task_queue_manager import TaskQueueManager

from eve import Eve
from eve.auth import BasicAuth

from atlas.config import allowed_users, ldap_server, ldap_org_unit, ldap_dns_domain_name
from atlas.tasks import *

"""
Callbacks
"""

"""
Callback for POST to `code` endpoint.

:param request: original flask.request object
"""
def post_code_callback(request):
    # Request object brings the POST information as a MultiDict.
    request.form
    ansible_playbook(playbook=code, environment=environment, vars=dict(request.form['git_url']))
    app.logger.debug(request.values)


"""
Utilities
"""
# Run Ansible Playbook

def ansible_playbook(playbook, environment, vars):
    # Initialize needed objects
    variable_manager = VariableManager()
    loader = DataLoader()
    passwords = {}
    playbook_path = sys.path + 'atlas/ansible/{0}.yml'.format(playbook)
    host_path = sys.path + 'atlas/ansible/{0}'.format(environment)

    # Validate paths
    if not os.path.exists(playbook_path):
        app.logger.error(
            'Playbook does not exist at \'{0}\''.format(playbook_path))
        return False
    if not os.path.exists(host_path):
        app.logger.error(
            'Inventory file does not exist at \'{0}\''.format(host_path))
        return False

    # Create inventory and pass to variable manager.
    inventory = Inventory(loader=loader, variable_manager=variable_manager, host_list=host_path)
    variable_manager.set_inventory(inventory)

    Options = namedtuple('Options', ['connection', 'module_path', 'forks', 'become', 'become_method', 'become_user', 'check'])
    options = Options(connection='ssh', forks=3, check=False)

    # Assemble the play.
    play = Play().load(playbook_path, variable_manager=variable_manager, loader=loader)

    # Actually run it
    try:
        tqm = TaskQueueManager(
                  inventory=inventory,
                  variable_manager=variable_manager,
                  loader=loader,
                  options=options,
                  passwords=passwords,
                  stdout_callback='default',
              )
        result = tqm.run(play)
    finally:
        if tqm is not None:
            tqm.cleanup()

# Basic Authentication
class AtlasBasicAuth(BasicAuth):
    def check_auth(self, username, password, allowed_roles=['default'], resource='default', method='default'):
        if username not in allowed_users:
            return False

        # Test credentials against LDAP.
        # Initialize LDAP. The initialize() method returns an LDAPObject
        # object, which contains methods for performing LDAP operations and
        # retrieving information about the LDAP connection and transactions.
        l = ldap.initialize(ldap_server)

        # Start the connection in a secure manner. Catch any errors and print
        # the description if present.
        try:
            l.start_tls_s()
        except ldap.LDAPError, e:
            print e.message['info']
            if type(e.message) == dict and e.message.has_key('desc'):
                print e.message['desc']
            else:
                print e

        ldap_distinguished_name = "uid={0},ou={1},{2}".format(username, ldap_org_unit, ldap_dns_domain_name)

        try:
            # Try a synchronous bind (we want synchronous so that the
            # command is blocked until the bind gets a result. If you can
            # bind, the credentials are valid.
            result = l.simple_bind_s(ldap_distinguished_name, password)
            app.logger.info('LDAP - {0} - Bind successful'.format(username))
            return True
        except ldap.INVALID_CREDENTIALS:
            app.logger.info('LDAP - {0} - Invalid credentials'.format(username))
            print "Username or Password is incorrect."

        # Apparently this was a bad login attempt
        app.logger.info('LDAP - {0} - Bind failed'.format(username))
        return False

# TODO: Add in a message and/or result broker, I don't want to use the DB. It is currently 41 GB for inventory.

"""
Setup the application and logging.
"""
# Tell Eve to use Basic Auth where our data structure is defined.
app = Eve(auth=AtlasBasicAuth, settings="/data/code/atlas/config_data_structure.py")

# TODO: Remove debug mode.
app.debug = True

# Add specific callbacks
# Pattern is: `atlas.on_{Hook}_{Method}_{Resource}`
app.on_pre_POST_code += post_code_callback

if __name__ == '__main__':
    # Enable logging to file
    # TODO: Figure out why the stuff shows in the apache error log, not this location.
    handler = logging.FileHandler('/var/log/celery/atlas.log')

    # The default log level is set to WARNING, so we have to explicitly set the
    # logging level to DEBUG.
    # TODO: Turn this back down.
    app.logger.setLevel(logging.DEBUG)
    # Append the handler to the default application logger
    app.logger.addHandler(handler)

    # This goes last
    app.run(host='0.0.0.0', ssl_context='adhoc')
