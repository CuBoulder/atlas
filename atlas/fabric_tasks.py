"""
    atlas.fabric_tasks
    ~~~~
    Commands that run on servers to do the actual work.
"""
import logging
import os
import re
import json

import requests
from datetime import datetime
from time import time, sleep, strftime

from fabric.contrib.files import exists, upload_template
from fabric.operations import put
from fabric.api import *
from fabric.network import disconnect_all

from atlas import utilities
from atlas.config import (ATLAS_LOCATION, ENVIRONMENT, SSH_USER, CODE_ROOT, SITES_CODE_ROOT,
                          SITES_WEB_ROOT, WEBSERVER_USER, WEBSERVER_USER_GROUP, NFS_MOUNT_FILES_DIR,
                          BACKUP_PATH, SERVICE_ACCOUNT_USERNAME, SERVICE_ACCOUNT_PASSWORD,
                          SITE_DOWN_PATH, LOAD_BALANCER, VARNISH_CONTROL_KEY, STATIC_WEB_PATH,
                          SSL_VERIFICATION, DRUPAL_CORE_PATHS, BACKUP_IMPORT_PATH, SAML_AUTH,
                          SMTP_PASSWORD)
from atlas.config_servers import (SERVERDEFS, NFS_MOUNT_LOCATION, API_URLS,
                                  VARNISH_CONTROL_TERMINALS, LOAD_BALANCER_CONFIG_FILES,
                                  LOAD_BALANCER_CONFIG_GROUP, BASE_URLS, ATLAS_LOGGING_URLS)

# Setup a sub-logger. See tasks.py for longer comment.
log = logging.getLogger('atlas.fabric_tasks')

# Fabric environmental settings.
env.user = SSH_USER

# Allow ~/.ssh/config to be utilized.
env.use_ssh_config = True
env.roledefs = SERVERDEFS[ENVIRONMENT]


class FabricException(Exception):
    pass


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
        log.info('Code | Deploy | Item - %s', item)
        if item['meta']['code_type'] == 'library':
            code_type_dir = 'libraries'
        else:
            code_type_dir = item['meta']['code_type'] + 's'
        code_folder = '{0}/{1}/{2}/{2}-{3}'.format(
            CODE_ROOT,
            code_type_dir,
            item['meta']['name'],
            item['meta']['version'])
        create_directory_structure(code_folder)
        clone_task = clone_repo(item["git_url"], item["commit_hash"], code_folder)
        log.debug('Code | Deploy | Clone result - %s', clone_task)
        if clone_task is True:
            if item['meta']['is_current']:
                code_folder_current = '{0}/{1}/{2}/{2}-current'.format(
                    CODE_ROOT,
                    code_type_dir,
                    item['meta']['name'])
                update_symlink(code_folder, code_folder_current)
            if item['meta']['code_type'] == 'static':
                static_target = '{0}/{1}-{2}'.format(STATIC_WEB_PATH,
                                                     item['meta']['name'], item['meta']['version'])
                log.debug('Code | Deploy | Static | Target - %s', static_target)
                update_symlink(code_folder, static_target)

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
    log.info('Code | Update | Updates - %s | Original - %s', updated_item, original_item)
    if updated_item['meta']['code_type'] == 'library':
        code_type_dir = 'libraries'
    else:
        code_type_dir = updated_item['meta']['code_type'] + 's'
    code_folder = '{0}/{1}/{2}/{2}-{3}'.format(
        CODE_ROOT,
        code_type_dir,
        updated_item['meta']['name'],
        updated_item['meta']['version'])
    if (updated_item['meta']['name'] != original_item['meta']['name']) or (updated_item['meta']['version'] != original_item['meta']['version']) or (updated_item['meta']['code_type'] != original_item['meta']['code_type']):
        code_remove(original_item)
        code_deploy(updated_item)
    else:
        checkout_repo(updated_item["commit_hash"], code_folder)
        if updated_item['meta']['is_current']:
            code_folder_current = '{0}/{1}/{2}/{2}-current'.format(
                CODE_ROOT,
                code_type_dir,
                updated_item['meta']['name'])
            update_symlink(code_folder, code_folder_current)
    clear_php_cache()


@roles('webservers')
def code_remove(item):
    """
    Responds to DELETEs to remove code from the server.

    :param item: Item to remove
    :return:
    """
    log.info('Code | Remove | Item - %s', item)
    if item['meta']['code_type'] == 'library':
        code_type_dir = 'libraries'
    else:
        code_type_dir = item['meta']['code_type'] + 's'
    code_folder = '{0}/{1}/{2}/{2}-{3}'.format(
        CODE_ROOT,
        code_type_dir,
        item['meta']['name'],
        item['meta']['version'])
    remove_directory(code_folder)
    if item['meta']['is_current']:
        code_folder_current = '{0}/{1}/{2}/{2}-current'.format(
            CODE_ROOT,
            code_type_dir,
            item['meta']['name'])
        remove_symlink(code_folder_current)
    if item['meta']['code_type'] == 'static':
        static_target = '{0}/{1}-{2}'.format(STATIC_WEB_PATH,
                                             item['meta']['name'], item['meta']['version'])
        remove_symlink(static_target)


@roles('webservers')
def code_heal(item):
    log.info('Code | Heal | Item - %s', item)
    if item['meta']['code_type'] == 'library':
        code_type_dir = 'libraries'
    else:
        code_type_dir = item['meta']['code_type'] + 's'
    code_folder = '{0}/{1}/{2}/{2}-{3}'.format(
        CODE_ROOT,
        code_type_dir,
        item['meta']['name'],
        item['meta']['version'])
    if not exists(code_folder):
        code_deploy(item)
    else:
        checkout_repo(item["commit_hash"], code_folder)


@roles('webservers')
def site_provision(site):
    """
    Responds to POSTs to provision a site to the right places on the server.

    :param site: The flask.request object, JSON encoded
    :return:
    """
    log.info('Site | Provision | site - %s', site)
    code_directory = '{0}/{1}'.format(SITES_CODE_ROOT, site['sid'])
    code_directory_sid = '{0}/{1}'.format(code_directory, site['sid'])
    code_directory_current = '{0}/current'.format(code_directory)
    web_directory_sid = '{0}/{1}'.format(SITES_WEB_ROOT, site['sid'])
    profile = utilities.get_single_eve('code', site['code']['profile'])

    try:
        execute(create_directory_structure, folder=code_directory)
    except FabricException as error:
        log.error('Site | Provision | Create directory structure failed | Error - %s', error)
        return error

    with cd(code_directory):
        core = utilities.get_code_name_version(site['code']['core'])
        run('drush dslm-new {0} {1}'.format(site['sid'], core))
        # Find all directories and set perms to 0755.
        run('find {0} -type d -exec chmod 0755 {{}} \\;'.format(code_directory_sid))
        # Find all directories and set group to `webserver_user_group`.
        run('find {0} -type d -exec chgrp {1} {{}} \\;'.format(code_directory_sid, WEBSERVER_USER_GROUP))
        # Find all files and set perms to 0644.
        run('find {0} -type f -exec chmod 0644 {{}} \\;'.format(code_directory_sid))

    with cd(code_directory_sid):
        profile = utilities.get_code_name_version(site['code']['profile'])
        run('drush dslm-add-profile {0}'.format(profile))

    try:
        execute(update_symlink, source=code_directory_sid, destination=code_directory_current)
    except FabricException as error:
        log.error('Site | Provision | Update symlink failed | Error - %s', error)
        return error

    if NFS_MOUNT_FILES_DIR:
        nfs_files_dir = '{0}/{1}'.format(NFS_MOUNT_LOCATION[ENVIRONMENT], site['sid'])
        try:
            execute(create_nfs_files_dir, nfs_dir=nfs_files_dir)
        except FabricException as error:
            log.error('Site | Provision | Create nfs directory failed | Error - %s', error)
            return error
        # Replace default files dir with this one
        site_files_dir = code_directory_current + '/sites/default/files'
        nfs_src = '{0}/files'.format(nfs_files_dir)
        try:
            execute(replace_files_directory, source=nfs_src, destination=site_files_dir)
        except FabricException as error:
            log.error('Site | Provision | Replace file directory failed | Error - %s', error)
            return error

    try:
        execute(create_settings_files, site=site)
    except FabricException as error:
        log.error('Site | Provision | Settings file creation failed | Error - %s', error)
        return error

    try:
        execute(update_symlink, source=code_directory_current, destination=web_directory_sid)
    except FabricException as error:
        log.error('Site | Provision | Update symlink failed | Error - %s', error)
        return error


@roles('webservers')
def site_package_update(site):
    log.info('Site | Package Update | Site - %s', site['_id'])
    code_directory_sid = '{0}/{1}/{1}'.format(SITES_CODE_ROOT, site['sid'])
    packages_directory = '{0}/sites/all'.format(code_directory_sid)

    package_name_string = ""
    for package in site['code']['package']:
        # Append the package name and a space.
        package_name_string += utilities.get_code_name_version(package) + " "
    # Strip the trailing space off the end.
    package_name_string = package_name_string.rstrip()

    log.debug('Site | Package Update | Site - %s | Packages - %s', site['_id'], package_name_string)

    with cd(packages_directory):
        run("drush dslm-remove-all-packages")
        if len(package_name_string) > 0:
            run("drush dslm-add-package {0}".format(package_name_string))


@roles('webservers')
def site_core_update(site):
    log.info('Site | Core Update | Site - %s', site['_id'])
    code_directory_sid = '{0}/{1}/{1}'.format(SITES_CODE_ROOT, site['sid'])
    core_string = utilities.get_code_name_version(site['code']['core'])

    with cd(code_directory_sid):
        run("drush dslm-switch-core {0}".format(core_string))


@roles('webservers')
def site_profile_update(site, original, updates):
    log.info('Site | Profile Update | Site - %s', site['_id'])
    code_directory_sid = '{0}/{1}/{1}'.format(SITES_CODE_ROOT, site['sid'])
    old_profile = utilities.get_single_eve('code', original['code']['profile'])
    new_profile = utilities.get_single_eve('code', site['code']['profile'])
    new_profile_full_string = utilities.get_code_name_version(site['code']['profile'])

    with cd(code_directory_sid + '/profiles'):
        run("rm {0}; ln -s {1}/profiles/{2}/{3} {2}".format(
            old_profile['meta']['name'],
            CODE_ROOT,
            new_profile['meta']['name'],
            new_profile_full_string))


@roles('webservers')
def site_profile_swap(site):
    log.info('Site | Profile Swap | Site - %s', site['_id'])
    code_directory_sid = '{0}/{1}/{1}'.format(SITES_CODE_ROOT, site['sid'])
    profile = utilities.get_single_eve('code', site['code']['profile'])
    new_profile_full_string = utilities.get_code_name_version(site['code']['profile'])

    with cd(code_directory_sid + '/profiles'):
        run("rm {0}; ln -s {1}/profiles/{2}/{3} {2}".format(
            profile['meta']['name'],
            CODE_ROOT,
            profile['meta']['name'],
            new_profile_full_string))


@roles('webservers')
def site_launch(site):
    """
    Create symlinks with new site name.
    """
    log.info('fabric_tasks | Launch subtask | Site - %s', site['_id'])
    code_directory = '{0}/{1}'.format(SITES_CODE_ROOT, site['sid'])
    code_directory_current = '{0}/current'.format(code_directory)

    if site['type'] == 'express':
        if site['path'] != 'homepage':
            web_directory_path = '{0}/{1}'.format(SITES_WEB_ROOT, site['path'])
            with cd(SITES_WEB_ROOT):
                # If the path is nested like 'lab/atlas', make the 'lab' directory
                if "/" in site['path']:
                    lead_path = "/".join(site['path'].split("/")[:-1])
                    create_directory_structure(lead_path)
                # Create a new symlink using site's updated path
                if not exists(web_directory_path):
                    update_symlink(code_directory_current, site['path'])
        elif site['path'] == 'homepage':
            with cd(SITES_WEB_ROOT):
                for link in DRUPAL_CORE_PATHS:
                    source_path = "{0}/{1}".format(code_directory_current, link)
                    target_path = "{0}/{1}".format(SITES_WEB_ROOT, link)
                    update_symlink(source_path, target_path)


@roles('webservers')
def site_take_down(site):
    """
    Point the site to the 'Down' page.
    """
    log.info('Site | Take down | Site - %s', site['_id'])
    code_directory_current = '{0}/{1}/current'.format(SITES_CODE_ROOT, site['sid'])
    update_symlink(SITE_DOWN_PATH, code_directory_current)


@roles('webservers')
def site_restore(site):
    """
    Point the site to the current release.
    """
    log.info('Site | Restore | Site - %s', site['_id'])
    code_directory_current = '{0}/{1}/current'.format(SITES_CODE_ROOT, site['sid'])
    code_directory_sid = '{0}/{1}/{1}'.format(SITES_CODE_ROOT, site['sid'])
    update_symlink(code_directory_sid, code_directory_current)


@roles('webservers')
def site_remove(site):
    """
    Responds to DELETEs to remove site from the server.

    :param site: Item to remove
    :return:
    """
    log.info('Site | Remove | Site - %s', site['_id'])

    code_directory = '{0}/{1}'.format(SITES_CODE_ROOT, site['sid'])
    web_directory = '{0}/{1}'.format(SITES_WEB_ROOT, site['sid'])
    web_directory_path = '{0}/{1}'.format(SITES_WEB_ROOT, site['path'])

    # Fix perms to allow settings file to be removed.
    run("chmod u+w {0}/{1}/{1}/sites/default/settings.php".format(SITES_CODE_ROOT, site['sid']))

    remove_symlink(web_directory)
    remove_symlink(web_directory_path)

    if NFS_MOUNT_FILES_DIR:
        nfs_dir = NFS_MOUNT_LOCATION[ENVIRONMENT]
        nfs_files_dir = '{0}/{1}/files'.format(nfs_dir, site['sid'])
        remove_directory(nfs_files_dir)

    remove_directory(code_directory)


@roles('webservers')
def instance_heal(item):
    log.info('Instance | Heal | Item ID - %s | Item - %s', item['sid'], item)
    path_list = []
    # Check for code root
    path_list.append('{0}/{1}'.format(SITES_CODE_ROOT, item['sid']))
    path_list.append('{0}/{1}/{2}'.format(SITES_CODE_ROOT, item['sid'], item['sid']))
    path_list.append('{0}/{1}/current'.format(SITES_CODE_ROOT, item['sid']))
    # Check for NFS
    path_list.append('{0}/{1}/files'.format(NFS_MOUNT_LOCATION[ENVIRONMENT], item['sid']))
    # Check for web root symlinks
    path_list.append('{0}/{1}'.format(SITES_WEB_ROOT, item['sid']))
    # Build list of paths to check
    reprovison = False
    if item['status'] == 'launched':
        path_symlink = '{0}/{1}'.format(SITES_WEB_ROOT, item['path'])
        path_list.append(path_symlink)
    log.info('Instance | Heal | Item ID - %s | Path list - %s', item['sid'], path_list)
    for path_to_check in path_list:
        if not exists(path_to_check):
            log.info('Instance | Heal | Item ID - %s | Path check failed - %s',
                     item['sid'], path_to_check)
            reprovison = True
            break
    # If we are missing any of the paths, wipe the instance and rebuild it.
    if reprovison:
        log.info('Instance | Heal | Item ID - %s | Begin reprovision', item['sid'])
        site_remove(item)
        site_provision(item)
        # Add packages
        if item['code'].get('package'):
            site_package_update(item)
        if item['status'] == 'launched':
            site_launch(item)
        log.info('Instance | Heal | Item ID - %s | Reprovision finished', item['sid'])
    else:
        log.info('Instance | Heal | Item ID - %s | Instance okay', item['sid'])


@roles('webservers')
def clear_php_cache():
    try:
        run('curl -ks https://127.0.0.1/opcache/reset.php;')
    except FabricException as error:
        log.error('Clear PHP Cache | Error - %s', error)
        return error


@roles('webservers')
def update_settings_file(site):
    log.info('fabric_tasks | Update Settings File | Site - %s', site['sid'])
    try:
        # Change permissions to allow us to update the template
        run("chmod u+w {0}/{1}/{1}/sites/default/settings.php".format(SITES_CODE_ROOT, site['sid']))
        execute(create_settings_files, site=site)
    except FabricException as error:
        log.error('fabric_tasks | Update Settings File | Site - %s | Error - %s',
                  site['sid'], error)
        return error


@roles('webservers')
def update_homepage_files():
    """
    SCP the homepage files to web heads.
    :return:
    """
    send_from_robots = '{0}/files/homepage_robots'.format(ATLAS_LOCATION)
    send_from_htaccess = '{0}/files/homepage_htaccess'.format(ATLAS_LOCATION)
    run("rm -f {0}/robots.txt".format(SITES_WEB_ROOT))
    put(send_from_robots, "{0}/robots.txt".format(SITES_WEB_ROOT))
    run("chmod -R u+w {0}/robots.txt".format(SITES_WEB_ROOT))
    run("rm -f {0}/.htaccess".format(SITES_WEB_ROOT))
    put(send_from_htaccess, "{0}/.htaccess".format(SITES_WEB_ROOT))
    run("chmod -R u+w {0}/.htaccess".format(SITES_WEB_ROOT))


@roles('webservers')
def command_run(site, command):
    """
    Run a command on a all webservers.

    :param site: Site to run command on
    :param command: Command to run
    :return:
    """
    log.info('Command | Multiple Servers | Site - %s | Command - %s', site['sid'], command)
    web_directory = '{0}/{1}'.format(SITES_WEB_ROOT, site['sid'])
    with cd(web_directory):
        run('{0}'.format(command))


# We use a dynamic host list to round-robin, so you need to pass a host list when calling it.
def command_run_single(site, command, warn_only=False):
    """
    Run a command on a single server

    :param site: Site to run command on
    :param command: Command to run
    :return:
    """
    log.info('Command | Single Server | Site - %s | Command - %s', site['sid'], command)
    web_directory = '{0}/{1}'.format(SITES_WEB_ROOT, site['sid'])
    with settings(warn_only=warn_only):
        with cd(web_directory):
            command_result = run("{0}".format(command), pty=False)
            # Return the failure if there is one.
            if command_result.failed:
                return command_result


# We use a dynamic host list to round-robin, so you need to pass a host list when calling it.
def update_database(site):
    """
    Run a updb

    :param site: Site to run command on
    :return:
    """
    log.info('fabric_tasks | updb | Site - %s', site['sid'])
    code_directory_sid = '{0}/{1}/{1}'.format(SITES_CODE_ROOT, site['sid'])
    with cd(code_directory_sid):
        run('drush updb -y')


# We use a dynamic host list to round-robin, so you need to pass a host list when calling it.
def registry_rebuild(site):
    """
    Run a drush rr and drush cc drush.
    Drush command cache clear is a workaround, see #306.

    :param site: Site to run command on
    :return:
    """
    log.info('fabric_tasks | Drush registry rebuild and cache clear | Site - %s', site['sid'])
    code_directory_sid = '{0}/{1}/{1}'.format(SITES_CODE_ROOT, site['sid'])
    with cd(code_directory_sid):
        run('drush rr; drush cc drush;')


def drush_cache_clear(sid):
    """
    Clear the Drupal cache

    We use a dynamic host list to round-robin, so you need to pass a host list when calling it or
    call it from a parent fabric task that has a role.
    """
    code_directory_current = '{0}/{1}/current'.format(SITES_CODE_ROOT, sid)
    with cd(code_directory_current):
        run('drush cc all')


def site_install(site):
    """
    Run Drupal install

    We use a dynamic host list to round-robin, so you need to pass a host list when calling it.
    """
    code_directory = '{0}/{1}'.format(SITES_CODE_ROOT, site['sid'])
    code_directory_current = '{0}/current'.format(code_directory)
    profile = utilities.get_single_eve('code', site['code']['profile'])
    profile_name = profile['meta']['name']

    try:
        with cd(code_directory_current):
            run('drush site-install -y {0}'.format(profile_name))
            run('chgrp -R {0} sites/default/files/*'.format(WEBSERVER_USER_GROUP))
            run('drush rr; drush cc drush')
    except FabricException as error:
        log.error('Site | Install | Instance install failed | Error - %s', error)
        return error


def create_nfs_files_dir(nfs_dir):
    nfs_files_dir = '{0}/files'.format(nfs_dir)
    nfs_tmp_dir = '{0}/tmp'.format(nfs_dir)
    create_directory_structure(nfs_files_dir)
    create_directory_structure(nfs_tmp_dir)
    run('chown {0}:{1} {2}'.format(SSH_USER, WEBSERVER_USER_GROUP, nfs_files_dir))
    run('chown {0}:{1} {2}'.format(SSH_USER, WEBSERVER_USER_GROUP, nfs_tmp_dir))
    run('chmod 775 {0}'.format(nfs_files_dir))
    run('chmod 775 {0}'.format(nfs_tmp_dir))


def create_directory_structure(folder):
    log.info('fabric_tasks | Create directory | Directory - %s', folder)
    run('mkdir -p {0}'.format(folder))


def remove_directory(folder):
    log.info('fabric_tasks | Remove directory | Directory - %s', folder)
    run('rm -rf {0}'.format(folder))


def remove_symlink(symlink):
    log.info('fabric_tasks | Remove symlink | Symlink - %s', symlink)
    run('rm -f {0}'.format(symlink))


def create_settings_files(site):
    """
    Create settings.local_pre.php, settings.php, and settings.local_post.php from templates and and
    upload the resulting file to the webservers.
    """
    sid = site['sid']
    site_path = site['path']
    # If the site is launching or launched, we add 'cu_path' and redirect the p1 URL.
    status = site['status']
    atlas_id = site['_id']
    statistics = site['statistics']

    if site.get('verification'):
        migration_verification = site['verification']['verification_status']
    else:
        migration_verification = None
    if site['settings'].get('siteimprove_site'):
        siteimprove_site = site['settings']['siteimprove_site']
    else:
        siteimprove_site = None
    if site['settings'].get('siteimprove_group'):
        siteimprove_group = site['settings']['siteimprove_group']
    else:
        siteimprove_group = None

    page_cache_maximum_age = site['settings']['page_cache_maximum_age']
    atlas_url = '{0}/'.format(API_URLS[ENVIRONMENT])
    atlas_logging_url = ATLAS_LOGGING_URLS[ENVIRONMENT]
    database_password = utilities.decrypt_string(site['db_key'])

    profile = utilities.get_single_eve('code', site['code']['profile'])
    profile_name = profile['meta']['name']

    if ('cse_creator' in site['settings']) and ('cse_id' in site['settings']):
        google_cse_csx = site['settings']['cse_creator'] + ':' + site['settings']['cse_id']
    else:
        google_cse_csx = None

    template_dir = '{0}/templates'.format(ATLAS_LOCATION)
    destination = "{0}/{1}/{1}/sites/default".format(SITES_CODE_ROOT, site['sid'])
    tmp_path = '{0}/{1}/tmp'.format(NFS_MOUNT_LOCATION[ENVIRONMENT], site['sid'])
    saml_auth = SAML_AUTH

    settings_variables = {
        'profile': profile_name,
        'sid': sid,
        'atlas_id': atlas_id,
        'atlas_url': atlas_url,
        'atlas_logging_url': atlas_logging_url,
        'atlas_username': SERVICE_ACCOUNT_USERNAME,
        'atlas_password': SERVICE_ACCOUNT_PASSWORD,
        'path': site_path,
        'status': status,
        'atlas_statistics_id': statistics,
        'siteimprove_site': siteimprove_site,
        'siteimprove_group': siteimprove_group,
        'google_cse_csx': google_cse_csx,
        'reverse_proxies': env.roledefs['varnish_servers'],
        'varnish_control': VARNISH_CONTROL_TERMINALS[ENVIRONMENT],
        'varnish_control_key': VARNISH_CONTROL_KEY,
        'pw': database_password,
        'page_cache_maximum_age': page_cache_maximum_age,
        'database_servers': env.roledefs['database_servers'],
        'environment': ENVIRONMENT,
        'tmp_path': tmp_path,
        'saml_pw': saml_auth,
        'smtp_client_hostname': BASE_URLS[ENVIRONMENT],
        'smtp_password': SMTP_PASSWORD,
        'migration_verification': migration_verification
    }

    log.info('fabric_tasks | Create Settings file')
    upload_template('settings.php',
                    destination=destination,
                    context=settings_variables,
                    use_jinja=True,
                    template_dir=template_dir,
                    backup=False,
                    mode='0444')


def clone_repo(git_url, checkout_item, destination):
    with settings(warn_only=True):
        log.info('fabric_tasks | Clone Repo | Repo - %s | Checkout - %s', git_url, checkout_item)
        clone_result = run('git clone {0} {1}'.format(git_url, destination), pty=False)

        if clone_result.failed:
            log.error('fabric_tasks | Clone Failed | Repo - %s | Checkout - %s | Error - %s',
                      git_url, checkout_item, clone_result)
            return clone_result

        with cd(destination):
            checkout_result = run('git checkout {0}'.format(checkout_item), pty=False)
            if checkout_result.failed:
                log.error('fabric_tasks | Checkout Failed | Repo - %s | Checkout - %s | Error - %s',
                          git_url, checkout_item, checkout_result)
                return checkout_result
            clean_result = run('git clean -f -f -d', pty=False)
            if clean_result.failed:
                log.error('fabric_tasks | Clean Failed | Repo - %s | Checkout - %s | Error - %s',
                          git_url, checkout_item, clean_result)
                return clean_result
            return True


def checkout_repo(checkout_item, destination):
    log.info('fabric_tasks | Checkout Repo | Destination - %s | Checkout - %s',
             destination, checkout_item)
    with cd(destination):
        run('git reset --hard')
        run('git fetch --all')
        run('git checkout {0}'.format(checkout_item))
        run('git clean -f -f -d')


def replace_files_directory(source, destination):
    if exists(destination):
        run('rm -rf {0}'.format(destination))
    update_symlink(source, destination)


def update_symlink(source, destination):
    log.info('fabric_tasks | Update Symlink | Source - %s | Destination - %s',
             source, destination)
    if exists(destination):
        run('rm {0}'.format(destination))
    run('ln -s {0} {1}'.format(source, destination))


def backup_create(site, backup_type):
    """
    Backup the database and files for an site.
    """
    log.debug('Backup | Create | site - %s', site)

    # Create the stub for the backup
    post_payload = {
        'site': site['_id'],
        'site_version': site['_version'],
        'backup_type': backup_type,
        'state': 'pending'
    }
    post_url = '{0}/backup'.format(API_URLS[ENVIRONMENT])
    post = requests.post(
        post_url,
        data=post_payload,
        auth=(SERVICE_ACCOUNT_USERNAME, SERVICE_ACCOUNT_PASSWORD),
        verify=SSL_VERIFICATION,
    )
    if post.ok:
        log.info('Backup | Create | POST - OK | %s | %s', post.content, post.headers)
    else:
        log.error('Backup | Create | POST - Error | %s', json.dumps(post.text))

    backup_item = post.json()
    log.info('Backup | Create | POST | Backup item - %s', backup_item)
    # Setup dates and times.
    start_time = time()
    date = datetime.now()
    date_time_string = date.strftime("%Y-%m-%d-%H-%M-%S")
    datetime_string = date.strftime("%Y-%m-%d %H:%M:%S GMT")

    # Instance paths
    web_directory = '{0}/{1}'.format(SITES_WEB_ROOT, site['sid'])
    database_result_file = '{0}_{1}.sql'.format(site['sid'], date_time_string)
    database_result_file_path = '{0}/backups/{1}'.format(BACKUP_PATH, database_result_file)
    nfs_files_dir = '{0}/{1}/files'.format(NFS_MOUNT_LOCATION[ENVIRONMENT], site['sid'])
    files_result_file = '{0}_{1}.tar.gz'.format(site['sid'], date_time_string)
    files_result_file_path = '{0}/backups/{1}'.format(BACKUP_PATH, files_result_file)

    # Start the actual process.
    with cd(web_directory):
        run('drush sql-dump --structure-tables-list=cache,cache_*,sessions,watchdog,history --result-file={0}'.format(
            database_result_file_path))
    with cd(nfs_files_dir):
        run('tar --exclude "imagecache" --exclude "css" --exclude "js" --exclude "backup_migrate" --exclude "styles" --exclude "xmlsitemap" --exclude "honeypot" -czf {0} *'.format(
            files_result_file_path))

    patch_payload = {
        'site': site['_id'],
        'site_version': site['_version'],
        'backup_date': datetime_string,
        'backup_type': backup_type,
        'files': files_result_file,
        'database': database_result_file,
        'state': 'complete'
    }

    log.debug('Backup | Create | Ready to update record | Payload - %s', patch_payload)
    utilities.patch_eve('backup', backup_item['_id'], patch_payload)

    backup_time = time() - start_time
    log.info('Atlas operational statistic | Backup Create | %s', backup_time)


def backup_restore(backup_record, original_instance, package_list):
    """
    Restore database and files to a new instance.
    """
    log.info('Instance | Restore Backup | %s | %s', backup_record, original_instance)
    start_time = time()
    file_date = datetime.strptime(backup_record['backup_date'], "%Y-%m-%d %H:%M:%S %Z")
    pretty_filename = '{0}_{1}'.format(
        original_instance['sid'], file_date.strftime("%Y-%m-%d-%H-%M-%S"))
    pretty_database_filename = '{0}.sql'.format(pretty_filename)
    database_path = '{0}/backups/{1}'.format(BACKUP_PATH, pretty_database_filename)
    pretty_files_filename = '{0}.tar.gz'.format(pretty_filename)
    files_path = '{0}/backups/{1}'.format(BACKUP_PATH, pretty_files_filename)

    # Grab available instance and add packages if needed
    available_instances = utilities.get_eve('sites', 'where={"status":"available"}')
    log.debug('Instance | Restore Backup | Avaiable Instances - %s', available_instances)
    new_instance = next(iter(available_instances['_items']), None)
    # TODO: Don't switch if the code is the same
    if new_instance is not None:
        payload = {'status': 'installing'}
        if package_list:
            packages = {'code': {'package': package_list}}
            payload.update(packages)
        utilities.patch_eve('sites', new_instance['_id'], payload)
    else:
        exit('No available instances.')

    # Wait for code and status to update.
    attempts = 18  # Tries every 10 seconds to a max of 18 (or 3 minutes).
    while attempts:
        try:
            new_instance_refresh = utilities.get_single_eve('sites', new_instance['_id'])
            if new_instance_refresh['status'] != 'installed':
                raise ValueError('Status has not yet updated.')
            break
        except ValueError, e:
            # If the status is not updated and we have attempts left,
            # remove an attempt and wait 10 seconds.
            attempts -= 1
            if attempts is not 0:
                sleep(10)
            else:
                exit(str(e))

    log.debug('Instance | Restore Backup | New instance is ready for DB and files | %s',
              new_instance['_id'])
    web_directory = '{0}/{1}/{2}'.format(SITES_WEB_ROOT, new_instance['type'], new_instance['sid'])
    nfs_files_dir = '{0}/sitefiles/{1}/files'.format(
        NFS_MOUNT_LOCATION[ENVIRONMENT], new_instance['sid'])

    with cd(nfs_files_dir):
        run('tar -xzf {0}'.format(files_path))
        log.debug('Instance | Restore Backup | Files replaced')

    with cd(web_directory):
        run('drush sql-cli < {0}'.format(database_path))
        log.debug('Instance | Restore Backup | DB imported')
        run('drush cc all')

    restore_time = time() - start_time
    log.info('Instance | Restore Backup | Complete | Backup - %s | New Instance - %s (%s) | %s sec',
             backup_record['_id'], new_instance['_id'], new_instance['sid'], restore_time)


def import_backup(backup, target_instance, source_env=ENVIRONMENT):
    """
    Connect to a single webserver, copy over the database and file backups, restore them into the
    Drupal instance, and remove the backup files.
    """
    log.info('Import Backup | Backup - %s | Target Instance - %s',
             backup, target_instance)

    start_time = time()

    # Copy db and files
    backup_tmp_dir = '{0}/tmp'.format(BACKUP_PATH)
    file_date = datetime.strptime(backup['backup_date'], "%Y-%m-%d %H:%M:%S %Z")
    backup_date = file_date.strftime("%Y-%m-%d-%H-%M-%S")
    site = utilities.get_single_eve('sites', backup['site'], env=source_env)
    backup_db = '{0}_{1}.sql'.format(site['sid'], backup_date)
    backup_files = '{0}_{1}.tar.gz'.format(site['sid'], backup_date)
    backup_db_path = '{0}/{1}'.format(BACKUP_IMPORT_PATH, backup_db)
    backup_files_path = '{0}/{1}'.format(BACKUP_IMPORT_PATH, backup_files)

    put(backup_db_path, backup_tmp_dir)
    put(backup_files_path, backup_tmp_dir)

    # Get the path for the file
    files_path = '{0}/{1}'.format(backup_tmp_dir, backup_files)
    database_path = '{0}/{1}'.format(backup_tmp_dir, backup_db)
    log.debug('Import backup | File path - %s | DB path - %s', files_path, database_path)
    web_directory = '{0}/{1}'.format(SITES_WEB_ROOT, target_instance['sid'])
    nfs_files_dir = '{0}/{1}/files'.format(
        NFS_MOUNT_LOCATION[ENVIRONMENT], target_instance['sid'])

    with cd(nfs_files_dir):
        run('tar -xzf {0}'.format(files_path))
        run('find {0} -type f -or -type d -exec chgrp apache {{}} \\;'.format(nfs_files_dir), warn_only=True)
        run('find {0} -type f -exec chmod g+rw {{}} \\;'.format(nfs_files_dir), warn_only=True)
        run('find {0} -type d -exec chmod g+rws {{}} \\;'.format(nfs_files_dir), warn_only=True)
        log.debug('Instance | Restore Backup | Files replaced')

    with cd(web_directory):
        run('drush sql-cli < {0}'.format(database_path))
        log.debug('Instance | Restore Backup | DB imported')
        with settings(warn_only=True):
            run('drush rr')
        run('drush en ucb_on_prem_hosting -y')
        run('drush elysia-cron run --ignore-time')

    run('rm {0}'.format(files_path))
    run('rm {0}'.format(database_path))

    restore_time = time() - start_time
    log.info('Import Backup | Complete | Target Instance - %s (%s) | %s sec',
             target_instance['_id'], target_instance['sid'], restore_time)
