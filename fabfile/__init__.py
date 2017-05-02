"""
Fabric Commands

Commands that run on servers to do the actual work.
"""
import sys
import requests
import re
import os

from fabric.contrib.files import append, exists, sed
from fabric.api import *
from fabric.network import disconnect_all
from jinja2 import Environment, PackageLoader
from random import randint
from time import time
from datetime import datetime
from atlas.config import *
from atlas import utilities

path = '/data/code'
if path not in sys.path:
    sys.path.append(path)

# Tell Jinja where our templates live.
jinja_env = Environment(loader=PackageLoader('atlas', 'templates'))

# Fabric environmental settings.
env.user = ssh_user
# env.key_filename =

# Allow ~/.ssh/config to be utilized.
env.use_ssh_config = True
env.roledefs = serverdefs[environment]


# TODO: Figure out a better way to deal with the output. Calling functions via
# 'var = execute(func)' seems to suppress a lot of the output.


# Code Commands.
@roles('webservers')
def code_deploy(item):
    """
    Responds to POSTs to deploy code to the right places on the server.

    :param item:
    :return:
    """
    # Need warn only to allow the error to pass to celery.
    with settings(warn_only=True):
        print('Code - Deploy\n{0}'.format(item))
        if item['meta']['code_type'] == 'library':
            code_type_dir = 'libraries'
        else:
            code_type_dir = item['meta']['code_type'] + 's'
        code_folder = '{0}/{1}/{2}/{2}-{3}'.format(
            code_root,
            code_type_dir,
            item['meta']['name'],
            item['meta']['version'])
        _create_directory_structure(code_folder)
        clone_task = _clone_repo(item["git_url"], item["commit_hash"], code_folder)
        print('Got clone response')
        print(clone_task)
        if clone_task == True:
            if item['meta']['is_current']:
                code_folder_current = '{0}/{1}/{2}/{2}-current'.format(
                    code_root,
                    code_type_dir,
                    item['meta']['name'])
                _update_symlink(code_folder, code_folder_current)
        else:
            return clone_task


@roles('webservers')
def code_update(updated_item, original_item):
    """
    Responds to PATCHes to update code in the right places on the server.

    :param updated_item:
    :param original_item:
    :return:
    """
    print('Code - Update\nUpdated Item\n{0}\n\nOriginal Item\n{1}'.format(
        updated_item,
        original_item))
    if updated_item['meta']['code_type'] == 'library':
        code_type_dir = 'libraries'
    else:
        code_type_dir = updated_item['meta']['code_type'] + 's'
    code_folder = '{0}/{1}/{2}/{2}-{3}'.format(
        code_root,
        code_type_dir,
        updated_item['meta']['name'],
        updated_item['meta']['version'])
    if (updated_item['meta']['name'] != original_item['meta']['name']) or (updated_item['meta']['version'] != original_item['meta']['version']) or (updated_item['meta']['code_type'] != original_item['meta']['code_type']):
        code_remove(original_item)
        code_deploy(updated_item)
    else:
        _checkout_repo(updated_item["commit_hash"], code_folder)
        if updated_item['meta']['is_current']:
            code_folder_current = '{0}/{1}/{2}/{2}-current'.format(
                code_root,
                code_type_dir,
                updated_item['meta']['name'])
            _update_symlink(code_folder, code_folder_current)


@roles('webservers')
def code_remove(item):
    """
    Responds to DELETEs to remove code from the server.

    :param item: Item to remove
    :return:
    """
    print('Code - Remove\n{0}'.format(item))
    if item['meta']['code_type'] == 'library':
        code_type_dir = 'libraries'
    else:
        code_type_dir = item['meta']['code_type'] + 's'
    code_folder = '{0}/{1}/{2}/{2}-{3}'.format(
        code_root,
        code_type_dir,
        item['meta']['name'],
        item['meta']['version'])
    _remove_directory(code_folder)
    if item['meta']['is_current']:
        code_folder_current = '{0}/{1}/{2}/{2}-current'.format(
            code_root,
            code_type_dir,
            item['meta']['name'])
        _remove_symlink(code_folder_current)


@roles('webservers')
def site_provision(site):
    """
    Responds to POSTs to provision a site to the right places on the server.

    :param site: The flask.request object, JSON encoded
    :return:
    """
    print('Site Provision\n{0}'.format(site))

    code_directory = '{0}/{1}'.format(sites_code_root, site['sid'])
    code_directory_sid = '{0}/{1}'.format(code_directory, site['sid'])
    code_directory_current = '{0}/current'.format(code_directory)
    web_directory_type = '{0}/{1}'.format(
        sites_web_root,
        site['type'])
    web_directory_sid = '{0}/{1}'.format(
        web_directory_type,
        site['sid'])
    profile = utilities.get_single_eve('code', site['code']['profile'])
    profile_name = profile['meta']['name']

    _create_database(site)

    _create_settings_files(site, profile_name)

    _create_directory_structure(code_directory)
    _create_directory_structure(web_directory_type)

    with cd(code_directory):
        core = utilities.get_code_name_version(site['code']['core'])
        run('drush dslm-new {0} {1}'.format(site['sid'], core))

    _update_symlink(code_directory_sid, code_directory_current)

    with cd(code_directory_current):
        profile = utilities.get_code_name_version(site['code']['profile'])
        run('drush dslm-add-profile {0}'.format(profile))

    if nfs_mount_files_dir:
        nfs_dir = nfs_mount_location[environment]
        nfs_files_dir = '{0}/sitefiles/{1}/files'.format(nfs_dir, site['sid'])
        _create_nfs_files_dir(nfs_dir, site['sid'])
        # Replace default files dir with this one
        site_files_dir = code_directory_current + '/sites/default/files'
        _replace_files_directory(nfs_files_dir, site_files_dir)

    _push_settings_files(site, code_directory_current)

    _update_symlink(code_directory_current, web_directory_sid)
    correct_file_directory_permissions(site)



@roles('webserver_single')
def site_install(site):
    code_directory = '{0}/{1}'.format(sites_code_root, site['sid'])
    code_directory_current = '{0}/current'.format(code_directory)
    profile = utilities.get_single_eve('code', site['code']['profile'])
    profile_name = profile['meta']['name']

    _install_site(profile_name, code_directory_current)
    correct_file_directory_permissions(site)


@roles('webservers')
def site_package_update(site):
    print('Site Package Update\n{0}'.format(site))
    code_directory_sid = '{0}/{1}/{1}'.format(sites_code_root, site['sid'])
    packages_directory = '{0}/sites/all'.format(code_directory_sid)

    package_name_string = ""
    for package in site['code']['package']:
        # Append the package name and a space.
        package_name_string += utilities.get_code_name_version(package) + " "
    # Strip the trailing space off the end.
    package_name_string = package_name_string.rstrip()
    print("Ready to add packages - {0}\n{1}".format(
        site['sid'],
        package_name_string))

    with cd(packages_directory):
        run("drush dslm-remove-all-packages")
        if len(package_name_string) > 0:
            run("drush dslm-add-package {0}".format(package_name_string))


@roles('webservers')
def site_core_update(site):
    print('Site Core Update\n{0}'.format(site))
    code_directory_sid = '{0}/{1}/{1}'.format(sites_code_root, site['sid'])
    core_string = utilities.get_code_name_version(site['code']['core'])

    with cd(code_directory_sid):
        run("drush dslm-switch-core {0}".format(core_string))


@roles('webservers')
def site_profile_update(site, original, updates):
    print('Site Profile Update\n{0}'.format(site))
    code_directory_sid = '{0}/{1}/{1}'.format(sites_code_root, site['sid'])
    old_profile = utilities.get_single_eve('code', original['code']['profile'])
    new_profile = utilities.get_single_eve('code', site['code']['profile'])
    new_profile_full_string = utilities.get_code_name_version(site['code']['profile'])

    with cd(code_directory_sid + '/profiles'):
        run("rm {0}; ln -s {1}/profiles/{2}/{3} {2}".format(
            old_profile['meta']['name'],
            code_root,
            new_profile['meta']['name'],
            new_profile_full_string))


@roles('webservers')
def site_profile_swap(site):
    print('Site Profile Update\n{0}'.format(site))
    code_directory_sid = '{0}/{1}/{1}'.format(sites_code_root, site['sid'])
    profile = utilities.get_single_eve('code', site['code']['profile'])
    new_profile_full_string = utilities.get_code_name_version(site['code']['profile'])

    with cd(code_directory_sid + '/profiles'):
        run("rm {0}; ln -s {1}/profiles/{2}/{3} {2}".format(
            profile['meta']['name'],
            code_root,
            profile['meta']['name'],
            new_profile_full_string))


@roles('webservers')
def site_launch(site):
    update_settings_file(site)

    if environment is 'prod' and site['pool'] is 'poolb-express':
        # Create GSA collection if needed.
        gsa_task = _create_gsa(site)
        if gsa_task is True:
            print ('GSA Collection - Success')
            machine_name = _machine_readable(site['path'])
            _launch_site(site=site, gsa_collection=machine_name)
            return
        else:
            print ('GSA Collection - Failed')
            _launch_site(site=site)
    else:
        print ('Site launch - No GSA')
        _launch_site(site=site)


@roles('webserver_single')
def site_backup(site):
    """
    Backup the database and files for an instance.
    """
    print('Site - Backup\m{0}'.format(site))
    # Setup all the variables we will need.
    web_directory = '{0}/{1}/{2}'.format(
        sites_web_root,
        site['type'],
        site['sid'])
    date_string = datetime.now().strftime("%Y-%m-%d")
    date_time_string = datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
    backup_path = '{0}/{1}/{2}'.format(
        backup_directory,
        site['sid'],
        date_string)
    database_result_file_path = '{0}/{1}_{2}.sql'.format(
        backup_path,
        site['sid'],
        date_time_string)
    files_result_file_path = '{0}/{1}_{2}.tar.gz'.format(
        backup_path,
        site['sid'],
        date_time_string)
    nfs_dir = nfs_mount_location[environment]
    nfs_files_dir = '{0}/sitefiles/{1}/files'.format(nfs_dir, site['sid'])
    # Start the actual process.
    _create_directory_structure(backup_path)
    with cd(web_directory):
        run('drush sql-dump --result-file={0}'.format(database_result_file_path))
        run('tar -czf {0} {1}'.format(files_result_file_path, nfs_files_dir))

    result = {
        'database': database_result_file_path,
        'files': files_result_file_path
    }
    return result


@roles('webservers')
def site_take_down(site):
    """
    Point the site to the 'Down' page.
    """
    print('Site Take down\n{0}'.format(site))
    code_directory_current = '{0}/{1}/current'.format(
        sites_code_root,
        site['sid'])
    _update_symlink(site_down_path, code_directory_current)


@roles('webservers')
def site_restore(site):
    """
    Point the site to the current release.
    """
    code_directory_current = '{0}/{1}/current'.format(
        sites_code_root,
        site['sid'])
    code_directory_sid = '{0}/{1}/{1}'.format(
        sites_code_root,
        site['sid'])
    _update_symlink(code_directory_sid, code_directory_current)
    with cd(code_directory_current):
        # Run updates
        action_0 = run("drush vset inactive_30_email FALSE; drush vset inactive_55_email FALSE; drush vset inactive_60_email FALSE;")
        # TODO: See if this works as intended.
        if action_0.failed:
            return task


@roles('webservers')
def site_remove(site):
    """
    Responds to DELETEs to remove site from the server.

    :param site: Item to remove
    :return:
    """
    print('Site - Remove\n{0}'.format(site))

    code_directory = '{0}/{1}'.format(sites_code_root, site['sid'])
    web_directory = '{0}/{1}/{2}'.format(
        sites_web_root,
        site['type'],
        site['sid'])
    web_directory_path = '{0}/{1}/{2}'.format(
        sites_web_root,
        site['type'],
        site['path'])

    _delete_database(site)

    _remove_symlink(web_directory)
    _remove_symlink(web_directory_path)

    if nfs_mount_files_dir:
        nfs_dir = nfs_mount_location[environment]
        nfs_files_dir = '{0}/sitefiles/{1}'.format(nfs_dir, site['sid'])
        _remove_directory(nfs_files_dir)

    _remove_directory(code_directory)


def correct_file_directory_permissions(site):
    code_directory_sid = '{0}/{1}/{1}'.format(sites_code_root, site['sid'])
    web_directory_sid = '{0}/{1}/{2}'.format(sites_web_root, site['type'], site['sid'])
    nfs_dir = nfs_mount_location[environment]
    nfs_files_dir = '{0}/sitefiles/{1}/files'.format(nfs_dir, site['sid'])
    nfs_files_tmp_dir = '{0}/sitefiles/{1}/tmp'.format(nfs_dir, site['sid'])
    with cd(code_directory_sid):
        run('chgrp -R {0} sites/default'.format(ssh_user_group))
        run('chmod -R 0775 sites/default')
    with cd(nfs_files_dir):
        run('chgrp -R {0} {1}'.format(webserver_user_group, nfs_files_dir))
        run('chmod -R 0775 {0}'.format(nfs_files_dir))
    with cd(nfs_files_tmp_dir):
        run('chgrp -R {0} {1}'.format(webserver_user_group, nfs_files_tmp_dir))
        run('chmod -R 0775 {0}'.format(nfs_files_tmp_dir))
    with cd(web_directory_sid):
        run('chmod -R 0775 sites/default')
        run('chmod -R 0644 sites/default/*.php')


@roles('webserver_single')
def command_run_single(site, command, warn_only=False):
    """
    Run a command on a single server

    :param site: Site to run command on
    :param command: Command to run
    :return:
    """
    print('Command - Single Server - {0}\n{1}'.format(site['sid'], command))
    web_directory = '{0}/{1}/{2}'.format(
        sites_web_root,
        site['type'],
        site['sid'])
    with settings(warn_only=warn_only):
        with cd(web_directory):
            command_result = run("{0}".format(command), pty=False)
            # Return the failure if there is one.
            if command_result.failed:
                return command_result


@roles('webservers')
def command_run(site, command):
    """
    Run a command on a all webservers.

    :param site: Site to run command on
    :param command: Command to run
    :return:
    """
    print('Command - {0}\n{1}'.format(site['sid'], command))
    web_directory = '{0}/{1}/{2}'.format(
        sites_web_root,
        site['type'],
        site['sid'])
    with cd(web_directory):
        run('{0}'.format(command))


@roles('webserver_single')
def update_database(site):
    """
    Run a updb

    :param site: Site to run command on
    :return:
    """
    print('Database Update\n{0}'.format(site))
    code_directory_sid = '{0}/{1}/{1}'.format(sites_code_root, site['sid'])
    with cd(code_directory_sid):
        print('Running database updates.')
        run("drush updb -y")


@roles('webserver_single')
def registry_rebuild(site):
    """
    Run a drush rr

    :param site: Site to run command on
    :return:
    """
    print('Drush registry rebuild\n{0}'.format(site))
    code_directory_sid = '{0}/{1}/{1}'.format(sites_code_root, site['sid'])
    with cd(code_directory_sid):
        run("drush rr")


@roles('webservers')
def clear_apc():
    run("wget -q -O - http://localhost/sysadmintools/apc/clearapc.php")


def drush_cache_clear(sid):
    code_directory_current = '{0}/{1}/current'.format(sites_code_root, sid)
    with cd(code_directory_current):
        run("drush cc all")


@roles('webservers')
def rewrite_symlinks(site):
    print('Rewrite symlinks\n{0}'.format(site))
    code_directory_current = '{0}/{1}/current'.format(sites_code_root, site['sid'])
    web_directory = '{0}/{1}/{2}'.format(sites_web_root, site['type'], site['sid'])
    if site['pool'] != 'poolb-homepage':
        _update_symlink(code_directory_current, web_directory)
    if site['status'] == 'launched' and site['pool'] != 'poolb-homepage':
        path_symlink = '{0}/{1}/{2}'.format(sites_web_root, site['type'], site['path'])
        _update_symlink(web_directory, path_symlink)
    if site['status'] == 'launched' and site['pool'] == 'poolb-homepage':
        web_directory = '{0}/{1}'.format(sites_web_root, 'homepage')
        _update_symlink(code_directory_current, web_directory)


@roles('webservers')
def update_settings_file(site):
    print('Update Settings Files\n{0}'.format(site))
    code_directory = '{0}/{1}/{1}'.format(sites_code_root, site['sid'])
    profile = utilities.get_single_eve('code', site['code']['profile'])
    profile_name = profile['meta']['name']

    _create_settings_files(site, profile_name)
    # Use execute to pass role.
    execute(_push_settings_files, site=site, directory=code_directory)


@roles('webservers')
def update_homepage_extra_files():
    """
    SCP the homepage files to web heads.
    :return:
    """
    send_from_robots = '{0}/files/homepage_robots'.format(atlas_location)
    send_from_htaccess = '{0}/files/homepage_htaccess'.format(atlas_location)
    send_to = '{0}/homepage'.format(sites_web_root)
    run("chmod -R u+w {}".format(send_to))
    run("rm -f {0}/robots.txt".format(send_to))
    put(send_from_robots, "{0}/robots.txt".format(send_to))
    run("rm -f {0}/.htaccess".format(send_to))
    put(send_from_htaccess, "{0}/.htaccess".format(send_to))
    run("chmod -R u+w {}".format(send_to))


@runs_once
def _create_nfs_files_dir(nfs_dir, site_sid):
    nfs_files_dir = '{0}/sitefiles/{1}/files'.format(nfs_dir, site_sid)
    nfs_tmp_dir = '{0}/sitefiles/{1}/tmp'.format(nfs_dir, site_sid)
    _create_directory_structure(nfs_files_dir)
    _create_directory_structure(nfs_tmp_dir)


# Fabric utility functions.
# TODO: Add decorator to run on a single host if called via 'execute'.
# Need to make sure it runs on all when called without execute.
def _create_directory_structure(folder):
    print('Create directory\n{0}'.format(folder))
    run('mkdir -p {0}'.format(folder))


def _remove_directory(folder):
    print('Remove directory\n{0}'.format(folder))
    run('rm -rf {0}'.format(folder))


def _remove_symlink(symlink):
    print('Remove symlink\n{0}'.format(symlink))
    run('rm -f {0}'.format(symlink))


@runs_once
def _create_database(site):
    if environment != 'local':
        os.environ['MYSQL_TEST_LOGIN_FILE'] = '/home/{0}/.mylogin.cnf'.format(
            ssh_user)
        mysql_login_path = "{0}_{1}".format(database_user, environment)
        mysql_info = '{0} --login-path={1} -e'.format(mysql_path, mysql_login_path)
        database_password = utilities.decrypt_string(site['db_key'])
        local('{0} \'CREATE DATABASE `{1}`;\''.format(mysql_info, site['sid']))
        # TODO: Make IP addresses config.
        local("{0} \"CREATE USER '{1}'@'172.20.62.0/255.255.255.0' IDENTIFIED BY '{2}';\"".format(
            mysql_info,
            site['sid'],
            database_password))
        sql = "GRANT ALL PRIVILEGES ON {0}.* TO '{0}'@'172.20.62.0/255.255.255.0';".format(
            site['sid'])
        local("{0} \"{1}\"".format(mysql_info, sql))
    else:
        with settings(host_string='express.local'):
            run("mysql -e 'create database `{}`;'".format(site['sid']))


@runs_once
def _delete_database(site):
    if environment != 'local':
        # TODO: Make file location config.
        os.environ['MYSQL_TEST_LOGIN_FILE'] = '/home/{0}/.mylogin.cnf'.format(
            ssh_user)
        mysql_login_path = "{0}_{1}".format(database_user, environment)
        mysql_info = '{0} --login-path={1} -e'.format(mysql_path, mysql_login_path)
        database_password = utilities.decrypt_string(site['db_key'])
        local('{0} \'DROP DATABASE IF EXISTS `{1}`;\''.format(mysql_info, site['sid']))
        # TODO: Make IP addresses config.
        local("{0} \"DROP USER '{1}'@'172.20.62.0/255.255.255.0';\"".format(
            mysql_info,
            site['sid']))
    else:
        with settings(host_string='express.local'):
            run("mysql -e 'DROP DATABASE IF EXISTS `{}`;'".format(site['sid']))


def _create_settings_files(site, profile_name):
    sid = site['sid']
    if 'path' in site:
        path = site['path']
    else:
        path = site['sid']
    # If the site is launching or launched, we add 'cu_path' and redirect the
    # p1 URL.
    status = site['status']
    id = site['_id']
    statistics = site['statistics']
    if site['settings'].get('siteimprove_site'):
        siteimprove_site = site['settings']['siteimprove_site']
    else:
        siteimprove_site = None
    if site['settings'].get('siteimprove_group'):
        siteimprove_group = site['settings']['siteimprove_group']
    else:
        siteimprove_group = None
    page_cache_maximum_age = site['settings']['page_cache_maximum_age']
    atlas_url = '{0}/'.format(api_urls[environment])
    database_password = utilities.decrypt_string(site['db_key'])

    # Call the template file and render the variables into it.
    template = jinja_env.get_template('settings.local_pre.php')
    local_pre_settings = template.render(
        profile=profile_name,
        sid=sid,
        atlas_id=id,
        atlas_url=atlas_url,
        atlas_username=service_account_username,
        atlas_password=service_account_password,
        path=path,
        status=status,
        pool=site['pool'],
        atlas_statistics_id=statistics,
        siteimprove_site=siteimprove_site,
        siteimprove_group=siteimprove_group
    )
    # Write the file to a temporary location.
    with open("/tmp/{0}.settings.local_pre.php".format(sid), "w") as ofile:
        ofile.write(local_pre_settings)

    template = jinja_env.get_template('settings.local_post.php')
    local_post_settings = template.render(
        sid=sid,
        pw=database_password,
        page_cache_maximum_age=page_cache_maximum_age,
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
    print('Push settings\n{0}\n{1}'.format(site, directory))
    send_from = '/tmp/{0}'.format(site['sid'])
    send_to = "{0}/sites/default".format(directory)
    run("chmod -R 755 {0}".format(send_to))
    put("{0}.settings.local_pre.php".format(send_from),
        "{0}/settings.local_pre.php".format(send_to))
    put("{0}.settings.local_post.php".format(send_from),
        "{0}/settings.local_post.php".format(send_to))
    put("{0}.settings.php".format(send_from),
        "{0}/settings.php".format(send_to))


@runs_once
def _install_site(profile_name, code_directory_current):
    with cd(code_directory_current):
        run('drush site-install -y {0}'.format(profile_name))
        run('drush rr')


def _clone_repo(git_url, checkout_item, destination):
    with settings(warn_only=True):
        print('Clone Repo: {0}\n Checkout: {1}'.format(git_url, checkout_item))
        clone_result = run('git clone {0} {1}'.format(git_url, destination), pty=False)

        if clone_result.failed:
            print ('Git clone failed\n{0}'.format(clone_result))
            return clone_result

        with cd(destination):
            checkout_result = run('git checkout {0}'.format(checkout_item), pty=False)
            if checkout_result.failed:
                print ('Git checkout failed\n{0}'.format(checkout_result))
                return checkout_result
            clean_result = run('git clean -f -f -d', pty=False)
            if clean_result.failed:
                print ('Git clean failed\n{0}'.format(clean_result))
                return clean_result
            return True


def _checkout_repo(checkout_item, destination):
    print('Checkout Repo: {0}\n Checkout: {1}'.format(
        destination,
        checkout_item))
    with cd(destination):
        run('git reset --hard')
        run('git fetch --all')
        run('git checkout {0}'.format(checkout_item))
        run('git clean -f -f -d')


def _replace_files_directory(source, destination):
    if exists(destination):
        run('rm -rf {0}'.format(destination))
    _update_symlink(source, destination)


def _update_symlink(source, destination):
    if exists(destination):
        run('rm {0}'.format(destination))
    run('ln -s {0} {1}'.format(source, destination))


def _machine_readable(string):
    """
    Replace all spaces with underscores and remove any non-alphanumeric
    characters.

    :param string:
    """
    new_string = string.lower().replace(" ", "_")
    return re.sub(r'\W+', '', new_string)


# GSA utilities
def _create_gsa(site):
    machine_name = _machine_readable(site['path'])
    if not _gsa_collection_exists(machine_name):
        index_path = "http://www.colorado.edu/{0}/".format(site['path'])
        _gsa_create_collection(machine_name, index_path)


def _gsa_collection_exists(name):
    """
    Return if a collection of the given name already exists.
    """
    raw = _gsa_collection_data()
    entries = _gsa_all_collections(raw)
    collections = _gsa_parse_entries(entries)
    return name in collections


def _gsa_create_collection(name, follow):
    """
    Creates a collection in the Google Search Appliance.
    """
    auth_token = _gsa_auth()
    url = "http://{0}:8000/feeds/collection".format(gsa_host)
    headers = {"Content-Type": "application/atom+xml",
               "Authorization": "GoogleLogin auth={0}".format(auth_token)}
    payload = """<?xml version='1.0' encoding='UTF-8'?>
<entry xmlns='http://www.w3.org/2005/Atom' xmlns:gsa='http://schemas.google.com/gsa/2007'>
<gsa:content name='collectionName'>{0}</gsa:content>
<gsa:content name='insertMethod'>customize</gsa:content>
<gsa:content name='followURLs'>{1}</gsa:content>
<gsa:content name='doNotCrawlURLs'></gsa:content>
</entry>"""
    payload = payload.format(name, follow)
    r = requests.post(url, data=payload, headers=headers, verify=False)
    if not r.ok:
        print(r.text)


def _gsa_auth():
    """
    Gets an auth token from the GSA.
    """
    url = "https://{0}:8443/accounts/ClientLogin".format(gsa_host)
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    r = requests.post(url, data="&Email={0}&Passwd={1}".format(gsa_username,
                                                               gsa_password),
                      headers=headers, verify=False)
    if r.ok:
        resp = r.text
        p = re.compile("Auth=(.*)")
        auth_token = p.findall(resp)[0]
        return auth_token


def _gsa_collection_data():
    """
    Gets the list of collections
    """
    auth_token = _gsa_auth()
    url = "http://{0}:8000/feeds/collection".format(gsa_host)
    headers = {"Content-Type": "application/atom+xml",
               "Authorization": "GoogleLogin auth={0}".format(auth_token)}
    r = requests.get(url, headers=headers, verify=False)
    if r.ok:
        return r.text


def _gsa_next_target(page):
    """
    Returns the next entry element
    """
    start_link = page.find('<entry')
    if start_link == -1:
        return None, 0
    start_quote = page.find('>', start_link)
    end_quote = page.find('</entry>', start_quote + 1)
    entry = page[start_quote + 1:end_quote]
    return entry, end_quote


def _gsa_all_collections(page):
    """
    Helper for collection_exists. Iterates through the <entry> elements in the text.
    """
    entries = []
    while True:
        entry, endpos = _gsa_next_target(page)
        if entry:
            entries.append(entry)
            page = page[endpos:]
        else:
            break
    return entries


def _gsa_parse_entries(entries):
    """
    Parses out the entries in the XML returned by the GSA into a dict.
    """
    collections = {}

    for entry in entries:
        # id = entry[entry.find("<id>")+4:entry.find("</id>")]
        needle = "<gsa:content name='entryID'>"
        start = entry.find(needle) + len(needle)
        name = entry[start:entry.find("</gsa:content>", start)]
        needle = "<gsa:content name='followURLs'>"
        start = entry.find(needle) + len(needle)
        follow = entry[start:entry.find("</gsa:content>", start)]
        follow = follow.split("\\n")
        collections[name] = follow

    return collections


def _launch_site(site, gsa_collection=False):
    """
    Create symlinks with new site name.
    """
    print ('Launch subtask')
    code_directory = '{0}/{1}'.format(sites_code_root, site['sid'])
    code_directory_current = '{0}/current'.format(code_directory)

    if site['pool'] in ['poolb-express', 'poolb-homepage'] and site['type'] == 'express':
        if site['pool'] == 'poolb-express':
            web_directory = '{0}/{1}'.format(sites_web_root, site['type'])
            web_directory_path = '{0}/{1}'.format(web_directory, site['path'])
            with cd(web_directory):
                # If the path is nested like 'lab/atlas', make the 'lab' directory
                if "/" in site['path']:
                    lead_path = "/".join(site['path'].split("/")[:-1])
                    _create_directory_structure(lead_path)

                # Create a new symlink using site's updated path
                if not exists(web_directory_path):
                    _update_symlink(code_directory_current, site['path'])
                # enter new site directory
                with cd(web_directory_path):
                    clear_apc()
                    if gsa_collection:
                        # Set the collection name
                        run("drush vset --yes google_appliance_collection {0}".format(gsa_collection))
                    # Clear caches at the end of the launch process to show
                    # correct pathologic rendered URLS.
                    drush_cache_clear(site['sid'])
            # Assign it to an update group.
            update_group = randint(0, 10)
        if site['pool'] == 'poolb-homepage':
            web_directory = '{0}/{1}'.format(sites_web_root, 'homepage')
            with cd(sites_web_root):
                _update_symlink(code_directory_current, web_directory)
                # enter new site directory
            with cd(web_directory):
                clear_apc()
                drush_cache_clear(site['sid'])
            # Assign site to update group 12.
            update_group = 12
        payload = {'status': 'launched', 'update_group': update_group}
        utilities.patch_eve('sites', site['_id'], payload)


def diff_f5():
    """
    Copy f5 configuration file to local sever, parse txt and create or update
    site items.

    """
    load_balancer_config_dir = '{0}/fabfile'.format(atlas_location)
    load_balancer_config_file = '{0}/{1}'.format(
        load_balancer_config_dir,
        load_balancer_config_files[environment])
    # If an older config file exists, copy it to a backup folder.
    if os.path.isfile(load_balancer_config_file):
        local('mv {0} {1}/f5_backups/{2}.{3}'.format(
            load_balancer_config_file,
            load_balancer_config_dir,
            load_balancer_config_files[environment],
            str(time()).split('.')[0]))
    # Copy config file from the f5 server to the Atlas server.
    local('scp {0}:/config/{1} {2}/'.format(
        serverdefs[environment]['load_balancers'][0],
        load_balancer_config_files[environment],
        load_balancer_config_dir))

    # Open file from f5
    with open(load_balancer_config_file, "r") as ifile:
        data = ifile.read()
    # Use regex to parse out path values
    p = re.compile('"(.+/?)" := "(\w+(-\w+)?)",')
    sites = p.findall(data)
    # Iterate through sites found in f5 data
    for site in sites:
        # Get path without leading slash
        path = site[0][1:]

        site_query = 'where={{"path":"{0}"}}'.format(path)
        api_sites = utilities.get_eve('sites', site_query)

        if not api_sites or len(api_sites['_items']) == 0:
            subject = 'Site record missing'
            message = "Path '{0}' is in the f5, but does not have a site record.".format(path)
            utilities.send_email(message=message, subject=subject, to=devops_team)
            print ("The f5 has an entry for '{0}' without a corresponding site record.".format(path))


def update_f5():
    # Like 'WWWNGProdDataGroup.dat'
    old_file_name = load_balancer_config_files[environment]
    # Like 'WWWNGDevDataGroup.dat.1402433484.bac'
    new_file_name = "{0}.{1}.bac".format(
        load_balancer_config_files[environment],
        str(time()).split('.')[0])
    load_balancer_config_dir = '{0}/fabfile'.format(atlas_location)
    sites = utilities.get_eve('sites', 'max_results=3000')

    # TODO: delete old backups

    # Write data to file
    with open("{0}/{1}".format(load_balancer_config_dir, load_balancer_config_files[environment]),
              "w") as ofile:
        for site in sites['_items']:
            if 'path' in site:
                # If a site is down or scheduled for deletion, skip to the next
                # site.
                if 'status' in site and (site['status'] == 'down' or site['status'] == 'delete'):
                    continue
                # In case a path was saved with a leading slash
                path = site["path"] if site["path"][0] == '/' else '/' + site["path"]
                # Ignore 'p1' paths but let the /p1 pattern through
                if not path.startswith("/p1") or len(path) == 3:
                    ofile.write('"{0}" := "{1}",\n'.format(path, site['pool']))

    execute(_exportf5,
            new_file_name=new_file_name,
            load_balancer_config_dir=load_balancer_config_dir)


@roles('load_balancers')
def _exportf5(new_file_name, load_balancer_config_dir):
    """
    Backup configuration file on f5 server, replace the active file, and reload
    the configuration.

    """
    # On an f5 server, backup the current configuration file.
    with cd("/config"):
        run("cp {0} {1}".format(load_balancer_config_files[environment], new_file_name))
    # Copy the new configuration file to the server.
    put("{0}/{1}".format(load_balancer_config_dir, load_balancer_config_files[environment]), "/config")
    # Load the new configuration.
    with cd("/config"):
        run("b load;")
    disconnect_all()
