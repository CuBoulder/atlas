"""
Fabric Commands

Commands that run on servers to do the actual work.
"""
import sys
from fabric.contrib.files import append, exists, sed
from fabric.api import *
from atlas.config import *


path = '/data/code'
if path not in sys.path:
    sys.path.append(path)

# Fabric environmental settings.
env.user = ssh_user
#env.key_filename =
# Allow ~/.ssh/config to be utilized.
env.use_ssh_config = True
env.colorize_error = True
env.roledefs = roledefs[environment]

# Code Commands.

@roles('webservers')
def code_deploy(request):
    """
    Responds to POSTs to deploy code to the right places on the server.

    The 'parallel' decorator allows several instances of this task to run at
    the same time.

    :param request: The flask.request object
    :return:
    """

    code_folder = '{0}/{1}s/{2}/{2}-{3}'.format(code_root,request['meta']['code_type'],request['meta']['name'],request['meta']['version'])
    _create_directory_structure(code_folder)
    _clone_repo(request["git_url"],request["commit_hash"],code_folder)
    if request['meta']['is_current']:
        code_folder_current = '/data/code/{0}/{1}/{1}-current'.format(request['meta']['code_type'],request['meta']['name'])
        _update_symlink(code_folder,code_folder_current)


def _create_directory_structure(folder):
    run('mkdir -p {0}'.format(folder))


def _clone_repo(git_url, checkout_item, destination):
    run('git clone {0} {1}'.format(git_url, destination))
    with cd(destination):
        run('git checkout {0}'.format(checkout_item))


def _update_symlink(source,destination):
    if exists(destination):
        run('rm {0}'.format(destination))
    run('ln -s {0} {1}'.format(source, destination))


# Site Commands.
# Look at '@run_once' decorator to run things like DB cache clears once per Fabric run, instead of on each host.