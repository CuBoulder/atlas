"""
Fabric Commands

Commands that run on servers to do the actual work.
"""
import sys

from fabric.contrib.files import append, exists, sed
from fabric.api import *
from jinja2 import Environment, PackageLoader
from atlas.config import *
from atlas import utilities


path = '/data/code'
if path not in sys.path:
    sys.path.append(path)

# Tell Jinja where our templates live.
jinja_env = Environment(loader=PackageLoader('atlas', 'templates'))

# Fabric environmental settings.
env.user = ssh_user
#env.key_filename =
# Allow ~/.ssh/config to be utilized.
env.use_ssh_config = True
env.colorize_error = True
env.roledefs = serverdefs[environment]


# TODO: Figure out a better way to deal with the output. Calling functions via 'var = execute(func)' seems to suppress a lot of the output.


# Code Commands.
@roles('webservers')
def code_deploy(item):
    """
    Responds to POSTs to deploy code to the right places on the server.

    :param item:
    :return:
    """
    code_folder = '{0}/{1}s/{2}/{2}-{3}'.format(code_root, item['meta']['code_type'], item['meta']['name'], item['meta']['version'])
    _create_directory_structure(code_folder)
    _clone_repo(item["git_url"],item["commit_hash"], code_folder)
    if item['meta']['is_current']:
        code_folder_current = '{0}/{1}s/{2}/{2}-current'.format(code_root, item['meta']['code_type'], item['meta']['name'])
        _update_symlink(code_folder,code_folder_current)


@roles('webservers')
def code_update(item):
    """
    Responds to PATCHes to update code in the right places on the server.

    :param item:
    :return:
    """
    code_folder = '{0}/{1}s/{2}/{2}-{3}'.format(code_root, item['meta']['code_type'], item['meta']['name'], item['meta']['version'])
    _checkout_repo(item["commit_hash"], code_folder)
    if item['meta']['is_current']:
        code_folder_current = '{0}/{1}s/{2}/{2}-current'.format(code_root, item['meta']['code_type'], item['meta']['name'])
        _update_symlink(code_folder,code_folder_current)


@roles('webservers')
def code_remove(item):
    """
    Responds to DELETEs to remove code from the server.

    :param item: Item to remove
    :return:
    """
    code_folder = '{0}/{1}s/{2}/{2}-{3}'.format(code_root, item['meta']['code_type'], item['meta']['name'], item['meta']['version'])
    _remove_directory(code_folder)


@roles('webservers')
def site_provision(site, install=True):
    """
    Responds to POSTs to provision a site to the right places on the server.

    :param site: The flask.request object, JSON encoded
    :param install: Boolean. Indicates if the install command will run.
    :return:
    """
    print('Site Provision - Install: {0}\n{1}'.format(install, site))

    code_directory = '{0}/{1}'.format(sites_code_root, site['sid'])
    code_directory_sid = '{0}/{1}'.format(code_directory, site['sid'])
    code_directory_current = '{0}/current'.format(code_directory)
    web_directory = '{0}/{1}/{2}'.format(sites_web_root, site['type'], site['sid'])
    profile = utilities.get_eve('code', 'where={{"_id":"{0}"}}'.format(site['code']['profile']))
    profile_name = profile['_items'][0]['meta']['name']

    _create_database(site)

    _create_settings_files(site, profile_name)

    _create_directory_structure(code_directory)

    with cd(code_directory):
        # TODO: Get core from site object.
        # core = site['code']['core']
        core = 'current'
        run('drush dslm-new {0} --{1}'.format(site['sid'], core))

    _update_symlink(code_directory_sid, code_directory_current)

    with cd(code_directory_current):
        # TODO: Get profile from site object.
        # version = site['code']['profile']
        version = 'current'
        run('drush dslm-add-profile {0} --{1}'.format(default_profile, version))

    if nfs_mount_files_dir:
        nfs_dir = nfs_mount_location[environment]
        nfs_files_dir = '{0}/sitefiles/{1}/files'.format(nfs_dir, site['sid'])
        nfs_tmp_dir = '{0}/sitefiles/{1}/tmp'.format(nfs_dir, site['sid'])
        _create_directory_structure(nfs_files_dir)
        _create_directory_structure(nfs_tmp_dir)
        # Replace default files dir with this one
        site_files_dir = code_directory_current + '/sites/default/files'
        _replace_files_directory(nfs_files_dir, site_files_dir)


    _push_settings_files(site, code_directory_current)

    _update_symlink(code_directory_current, web_directory)
    correct_file_directory_permissions(site)

    if install:
        _install_site(profile_name, code_directory_current)

    # TODO: Patch site with all its new information.


def correct_file_directory_permissions(site):
    code_directory_sid = '{0}/{1}/{1}'.format(sites_code_root, site['sid'])
    with cd(code_directory_sid):
        run('chgrp -R lapurd sites/default'.format(ssh_user_group))
        run('chgrp -R apache sites/default/files'.format(webserver_user_group))
        run('chmod -R 775 sites/default')


# Fabric utility functions.
# TODO: Add decorator to run on a single host if called via 'execute'.
# Need to make sure it runs on all when called without execute.
def _create_directory_structure(folder):
    print('Create directory\n{0}'.format(folder))
    run('mkdir -p {0}'.format(folder))


def _remove_directory(folder):
    print('Remove directory\n{0}'.format(folder))
    run('rm -rf {0}'.format(folder))


# TODO: Add decorator to run on a single host.
def _create_database(site):
    if environment != 'local':
        # TODO: Make file location config.
        os.environ['MYSQL_TEST_LOGIN_FILE'] = '/home/dplagnt/.mylogin.cnf'
        mysql_login_path = "invsqlagnt_{0}_poolb".format(environment)
        mysql_info = '/usr/local/mysql/bin/mysql --login-path={0} -e'.format(mysql_login_path)
        database_password = utilities.decrypt_string(site['db_key'])
        local('{0} \'create database `{1}`;\''.format(mysql_info, site['sid']))
        # TODO: Make IP addresses config.
        local("{0} \"create user '{1}'@'172.20.62.0/255.255.255.0' identified by '{2}';\"".format(mysql_info, site['sid'], database_password))
        sql = "GRANT ALL PRIVILEGES ON {0}.* TO '{0}'@'172.20.62.0/255.255.255.0';".format(site['sid'])
        local("{0} \"{1}\"".format(mysql_info, sql))
    else:
        with settings(host_string='express.local'):
            run("mysql -e 'create database `{}`;'".format(site['sid']))


def _create_settings_files(site, profile_name):
    sid = site['sid']
    if 'path' in site:
        path = site['path']
    else:
        path = site['sid']
    # If the site is launching or launched, we add 'cu_path' and redirect the
    # p1 URL.
    status = site['status']

    database_password = utilities.decrypt_string(site['db_key'])

    # Call the template file and render the variables into it.
    template = jinja_env.get_template('settings.local_pre.php')
    local_pre_settings = template.render(
        profile=profile_name,
        sid=sid,
        path=path,
        status=status,
        pool_full=site['pool']
    )
    # Write the file to a temporary location.
    with open("/tmp/{0}.settings.local_pre.php".format(sid), "w") as ofile:
        ofile.write(local_pre_settings)

    template = jinja_env.get_template('settings.local_post.php')
    local_post_settings = template.render(
        sid=sid,
        pw=database_password,
        database_servers=env.roledefs['database_servers'],
        memcache_servers=env.roledefs['memcache_servers'],
        environment=environment if environment != 'prod' else '',
    )
    with open("/tmp/{0}.settings.local_post.php".format(sid), "w") as ofile:
        ofile.write(local_post_settings)

    template = jinja_env.get_template('settings.php')
    settings_php = template.render(
        profile=profile_name,
        sid=sid,
        reverse_proxies=env.roledefs['varnish_servers'],
        varnish_control=varnish_control_terminals[environment],
        memcache_servers=env.roledefs['memcache_servers'],
        environment=environment if environment != 'prod' else '',
    )
    with open("/tmp/{0}.settings.php".format(sid), "w") as ofile:
        ofile.write(settings_php)


def _push_settings_files(site, directory):
    send_from = '/tmp/{0}'.format(site['sid'])
    send_to = "{0}/sites/default/".format(directory)
    run("chmod -R u+w {0}".format(send_to))
    put("{0}.settings.local_pre.php".format(send_from), "{0}settings.local_pre.php".format(send_to))
    put("{0}.settings.local_post.php".format(send_from), "{0}settings.local_post.php".format(send_to))
    put("{0}.settings.php".format(send_from), "{0}settings.php".format(send_to))
    run("chmod -R u+w {0}".format(send_to))


# TODO: Add decorator to run on a single host.
def _install_site(profile_name, code_directory_current):
    with cd(code_directory_current):
        run('drush site-install -y {0}'.format(profile_name))
        run('drush rr')


def _clone_repo(git_url, checkout_item, destination):
    print('Clone Repo: {0}\n Checkout: {1}'.format(git_url, checkout_item))
    run('git clone {0} {1}'.format(git_url, destination))
    with cd(destination):
        run('git checkout {0}'.format(checkout_item))
        run('git submodule update --init --recursive')
        run('git clean -f -f -d')


def _checkout_repo(checkout_item, destination):
    print('Checkout Repo: {0}\n Checkout: {1}'.format(destination, checkout_item))
    with cd(destination):
        run('git reset --hard')
        run('git checkout {0}'.format(checkout_item))
        run('git submodule update --init --recursive')
        run('git clean -f -f -d')


def _replace_files_directory(source, destination):
    if exists(destination):
        run('rm -rf {0}'.format(destination))
    _update_symlink(source, destination)


def _update_symlink(source, destination):
    if exists(destination):
        run('rm {0}'.format(destination))
    run('ln -s {0} {1}'.format(source, destination))


# Site Commands.
# Look at '@run_once' decorator to run things like DB cache clears once per Fabric run, instead of on each host.