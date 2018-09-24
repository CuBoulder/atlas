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
from atlas.config import (ATLAS_LOCATION, ENVIRONMENT, SSH_USER, CODE_ROOT, INSTANCE_ROOT,
                          WEB_ROOT, WEBSERVER_USER, WEBSERVER_USER_GROUP, NFS_MOUNT_FILES_DIR,
                          BACKUP_PATH, SERVICE_ACCOUNT_USERNAME, SERVICE_ACCOUNT_PASSWORD,
                          SITE_DOWN_PATH, VARNISH_CONTROL_KEY, STATIC_WEB_PATH, SSL_VERIFICATION,
                          CORE_WEB_ROOT_SYMLINKS, BACKUP_IMPORT_PATH, SAML_AUTH, SMTP_PASSWORD)
from atlas.config_servers import (SERVERDEFS, NFS_MOUNT_LOCATION, API_URLS,
                                  VARNISH_CONTROL_TERMINALS, BASE_URLS, ATLAS_LOGGING_URLS)

# Setup a sub-logger. See tasks.py for longer comment.
log = logging.getLogger('atlas.fabric_tasks')

# Fabric environmental settings.
env.user = SSH_USER

# Allow ~/.ssh/config to be utilized.
env.use_ssh_config = True
env.roledefs = SERVERDEFS[ENVIRONMENT]


class FabricException(Exception):
    pass


# TODO Refactor
@roles('webservers', 'operations_server')
def site_remove(site):
    """
    Responds to DELETEs to remove site from the server.

    :param site: Item to remove
    :return:
    """
    log.info('Site | Remove | Site - %s', site['_id'])

    code_directory = '{0}/{1}'.format(INSTANCE_ROOT, site['sid'])
    web_directory = '{0}/{1}'.format(WEB_ROOT, site['sid'])
    web_directory_path = '{0}/{1}'.format(WEB_ROOT, site['path'])

    # Fix perms to allow settings file to be removed.
    sites_dir = "{0}/{1}/{1}/sites".format(INSTANCE_ROOT, site['sid'])
    if exists(sites_dir):
        run("chmod -R u+w {0}".format(sites_dir))

    remove_symlink(web_directory)
    remove_symlink(web_directory_path)

    if NFS_MOUNT_FILES_DIR:
        nfs_dir = NFS_MOUNT_LOCATION[ENVIRONMENT]
        nfs_files_dir = '{0}/{1}/files'.format(nfs_dir, site['sid'])
        remove_directory(nfs_files_dir)

    remove_directory(code_directory)


# TODO Refactor
@roles('webservers', 'operations_server')
def instance_heal(item):
    log.info('Instance | Heal | Item ID - %s | Item - %s', item['sid'], item)
    path_list = []
    # Check for code root
    path_list.append('{0}/{1}'.format(INSTANCE_ROOT, item['sid']))
    path_list.append('{0}/{1}/{2}'.format(INSTANCE_ROOT, item['sid'], item['sid']))
    path_list.append('{0}/{1}/current'.format(INSTANCE_ROOT, item['sid']))
    # Check for NFS
    path_list.append('{0}/{1}/files'.format(NFS_MOUNT_LOCATION[ENVIRONMENT], item['sid']))
    # Check for web root symlinks
    path_list.append('{0}/{1}'.format(WEB_ROOT, item['sid']))
    # Build list of paths to check
    reprovison = False
    if item['status'] == 'launched':
        path_symlink = '{0}/{1}'.format(WEB_ROOT, item['path'])
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


# TODO Refactor
@roles('operations_server')
def instance_rebuild_code(item):
    log.info('Instance | Rebuild code | Item ID - %s | Item - %s', item['sid'], item)
    # Build list of paths to check
    path_list = []
    # Check for code root
    path_list.append('{0}/{1}'.format(INSTANCE_ROOT, item['sid']))
    path_list.append('{0}/{1}/{2}'.format(INSTANCE_ROOT, item['sid'], item['sid']))
    path_list.append('{0}/{1}/current'.format(INSTANCE_ROOT, item['sid']))
    # Check for NFS
    path_list.append('{0}/{1}/files'.format(NFS_MOUNT_LOCATION[ENVIRONMENT], item['sid']))
    # Check for web root symlinks
    path_list.append('{0}/{1}'.format(WEB_ROOT, item['sid']))
    # If homepage, add symlinks in webroot
    if item['path'] == 'homepage':
        # TODO Make sure that we are using the correct variable for Web root symlinks vs Instance symlinks
        for link in CORE_WEB_ROOT_SYMLINKS:
            path_list.append('{0}/{1}'.format(WEB_ROOT, link))
    reprovison = False
    if item['status'] == 'launched':
        path_symlink = '{0}/{1}'.format(WEB_ROOT, item['path'])
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
        instance_remove_code(item)
        instance_add_code(item)
        # Add packages
        if item['code'].get('package'):
            site_package_update(item)
        if item['status'] == 'launched':
            site_launch(item)
        log.info('Instance | Heal | Item ID - %s | Reprovision finished', item['sid'])
    else:
        log.info('Instance | Heal | Item ID - %s | Instance okay', item['sid'])


# TODO Refactor
def instance_remove_code(site):
    """
    Remove code for instance

    :param site: Instance to remove code from
    :return:
    """
    log.info('Instance | Remove Code | Instance - %s', site['_id'])

    code_directory = '{0}/{1}'.format(INSTANCE_ROOT, site['sid'])
    web_directory = '{0}/{1}'.format(WEB_ROOT, site['sid'])
    web_directory_path = '{0}/{1}'.format(WEB_ROOT, site['path'])

    # Fix perms to allow settings file to be removed.
    sites_dir = "{0}/{1}/{1}/sites".format(INSTANCE_ROOT, site['sid'])
    if exists(sites_dir):
        run("chmod -R u+w {0}".format(sites_dir))

    remove_symlink(web_directory)
    remove_symlink(web_directory_path)
    remove_directory(code_directory)


# TODO Refactor
def instance_add_code(site):
    """
    Add code to instance

    :param site: The site object
    :return:
    """
    log.info('Site | Add Code | site - %s', site)
    code_directory = '{0}/{1}'.format(INSTANCE_ROOT, site['sid'])
    code_directory_sid = '{0}/{1}'.format(code_directory, site['sid'])
    code_directory_current = '{0}/current'.format(code_directory)
    web_directory_sid = '{0}/{1}'.format(WEB_ROOT, site['sid'])
    profile = utilities.get_single_eve('code', site['code']['profile'])

    try:
        execute(create_directory_structure, folder=code_directory)
    except FabricException as error:
        log.error('Site | Add Code | Create directory structure failed | Error - %s', error)
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
        log.error('Site | Add Code | Update symlink failed | Error - %s', error)
        return error

    if NFS_MOUNT_FILES_DIR:
        # Replace default files dir with this one
        site_files_dir = code_directory_current + '/sites/default/files'
        nfs_files_dir = '{0}/{1}/files'.format(NFS_MOUNT_LOCATION[ENVIRONMENT], site['sid'])
        nfs_src = '{0}/files'.format(nfs_files_dir)
        try:
            execute(replace_files_directory, source=nfs_src, destination=site_files_dir)
        except FabricException as error:
            log.error('Site | Add Code | Replace file directory failed | Error - %s', error)
            return error

    try:
        execute(create_settings_files, site=site)
    except FabricException as error:
        log.error('Site | Add Code | Settings file creation failed | Error - %s', error)
        return error

    try:
        execute(update_symlink, source=code_directory_current, destination=web_directory_sid)
    except FabricException as error:
        log.error('Site | Add Code | Update symlink failed | Error - %s', error)
        return error


@roles('webservers', 'operations_server')
def clear_php_cache():
    try:
        run('curl -ks https://127.0.0.1/opcache/reset.php;')
    except FabricException as error:
        log.error('Clear PHP Cache | Error - %s', error)
        return error


@roles('webservers')
def command_run(site, command):
    """
    Run a command on a all webservers.

    :param site: Site to run command on
    :param command: Command to run
    :return:
    """
    log.info('Command | Multiple Servers | Site - %s | Command - %s', site['sid'], command)
    web_directory = '{0}/{1}'.format(WEB_ROOT, site['sid'])
    with cd(web_directory):
        run('{0}'.format(command))


@roles('operations_server')
def command_run_single(site, command, warn_only=False):
    """
    Run a command on a single server

    :param site: Site to run command on
    :param command: Command to run
    :return:
    """
    log.info('Command | Single Server | Site - %s | Command - %s', site['sid'], command)
    web_directory = '{0}/{1}'.format(WEB_ROOT, site['sid'])
    with settings(warn_only=warn_only):
        with cd(web_directory):
            command_result = run("{0}".format(command), pty=False)
            # Return the failure if there is one.
            if command_result.failed:
                return command_result

# TODO Refactor
@roles('operations_server')
def correct_nfs_file_permissions(instance=None):
    """
    Correct the nfs mount file permissions for an instance
    """
    if instance:
        log.info('Correct NFS File permissions | Instance - %s | Start', instance['sid'])
        nfs_files_dir = '{0}/{1}/files'.format(NFS_MOUNT_LOCATION[ENVIRONMENT], instance['sid'])
    else:
        log.info('Correct NFS File permissions | All instances | Start')
        nfs_files_dir = NFS_MOUNT_LOCATION[ENVIRONMENT]

    with settings(warn_only=True):
        run('find {0} -type f -or -type d -not -group {1} -exec chgrp {1} {{}} \\;'.format(nfs_files_dir, WEBSERVER_USER_GROUP))
        run('find {0} -type f -user {1} -exec chmod g+rw {{}} \\;'.format(nfs_files_dir, SSH_USER))
        run('find {0} -type d -user {1} -exec chmod g+rws {{}} \\;'.format(nfs_files_dir, SSH_USER))

    if instance:
        log.info('Correct NFS File permissions | Instance - %s | Complete', instance['sid'])
    else:
        log.info('Correct NFS File permissions | All instances | Complete')


@roles('operations_server')
def update_database(site):
    """
    Run a updb

    :param site: Site to run command on
    :return:
    """
    log.info('fabric_tasks | updb | Site - %s', site['sid'])
    code_directory_sid = '{0}/{1}/{1}'.format(INSTANCE_ROOT, site['sid'])
    with cd(code_directory_sid):
        run('drush updb -y')


@roles('operations_server')
def registry_rebuild(site):
    """
    Run a drush rr and drush cc drush.
    Drush command cache clear is a workaround, see #306.

    :param site: Site to run command on
    :return:
    """
    log.info('fabric_tasks | Drush registry rebuild and cache clear | Site - %s', site['sid'])
    code_directory_sid = '{0}/{1}/{1}'.format(INSTANCE_ROOT, site['sid'])
    with cd(code_directory_sid):
        run('drush rr; drush cc drush;')


@roles('operations_server')
def drush_cache_clear(sid):
    """
    Clear the Drupal cache

    We use a dynamic host list to round-robin, so you need to pass a host list when calling it or
    call it from a parent fabric task that has a role.
    """
    code_directory_current = '{0}/{1}/{1}'.format(INSTANCE_ROOT, sid)
    with cd(code_directory_current):
        run('drush cc all')


@roles('operations_server')
def site_install(site):
    """Run Drupal install
    """
    code_directory = '{0}/{1}'.format(INSTANCE_ROOT, site['sid'])
    code_directory_current = '{0}/current'.format(code_directory)
    profile = utilities.get_single_eve('code', site['code']['profile'])
    profile_name = profile['meta']['name']

    try:
        with cd(code_directory_current):
            run('drush site-install -y {0}'.format(profile_name))
    except FabricException as error:
        log.error('Site | Install | Instance install failed | Error - %s', error)
        return error


# TODO Refactor
def create_directory_structure(folder):
    log.info('fabric_tasks | Create directory | Directory - %s', folder)
    run('mkdir -p {0}'.format(folder))


# TODO Refactor
def remove_directory(folder):
    log.info('fabric_tasks | Remove directory | Directory - %s', folder)
    run('rm -rf {0}'.format(folder))


# TODO Refactor
def remove_symlink(symlink):
    log.info('fabric_tasks | Remove symlink | Symlink - %s', symlink)
    run('rm -f {0}'.format(symlink))


# TODO Refactor
def replace_files_directory(source, destination):
    if exists(destination):
        run('rm -rf {0}'.format(destination))
    update_symlink(source, destination)


# TODO Refactor
def update_symlink(source, destination):
    log.info('fabric_tasks | Update Symlink | Source - %s | Destination - %s',
             source, destination)
    if exists(destination):
        run('rm {0}'.format(destination))
    run('ln -s {0} {1}'.format(source, destination))


@roles('operations_server')
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
    web_directory = '{0}/{1}'.format(WEB_ROOT, site['sid'])
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


@roles('operations_server')
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
                log.info('Instance | Restore Backup | New instance is not ready | %s', new_instance['_id'])
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

    log.info('Instance | Restore Backup | New instance is ready for DB and files | %s',
             new_instance['_id'])
    web_directory = '{0}/{1}'.format(WEB_ROOT, new_instance['sid'])
    nfs_files_dir = '{0}/{1}/files'.format(NFS_MOUNT_LOCATION[ENVIRONMENT], new_instance['sid'])

    with cd(nfs_files_dir):
        run('tar -xzf {0}'.format(files_path))
        log.info('Instance | Restore Backup | Files replaced')

    with cd(web_directory):
        run('drush sql-cli < {0}'.format(database_path))
        log.info('Instance | Restore Backup | DB imported')
        run('drush cc all')

    restore_time = time() - start_time
    log.info('Instance | Restore Backup | Complete | Backup - %s | New Instance - %s (%s) | %s sec',
             backup_record['_id'], new_instance['_id'], new_instance['sid'], restore_time)


@roles('operations_server')
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
    web_directory = '{0}/{1}'.format(WEB_ROOT, target_instance['sid'])
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
        run('drush elysia-cron run --ignore-time')
        run('drush xmlsitemap-regenerate')

    run('rm {0}'.format(files_path))
    run('rm {0}'.format(database_path))

    restore_time = time() - start_time
    log.info('Import Backup | Complete | Target Instance - %s (%s) | %s sec',
             target_instance['_id'], target_instance['sid'], restore_time)
