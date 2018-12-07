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
                          CORE_WEB_ROOT_SYMLINKS, SAML_AUTH, SMTP_PASSWORD)
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
    if NFS_MOUNT_FILES_DIR:
        files_dir = '{0}/{1}/files'.format(NFS_MOUNT_LOCATION[ENVIRONMENT], site['sid'])
    else:
        files_dir = '{0}/{1}/sites/default/files'.format(WEB_ROOT, site['sid'])
    files_result_file = '{0}_{1}.tar.gz'.format(site['sid'], date_time_string)
    files_result_file_path = '{0}/backups/{1}'.format(BACKUP_PATH, files_result_file)

    # Start the actual process.
    with cd(web_directory):
        run('drush sql-dump --structure-tables-list=cache,cache_*,sessions,watchdog,history --result-file={0}'.format(
            database_result_file_path))
    with cd(files_dir):
        log.debug('File dir | %s', files_dir)
        run('tar --exclude "imagecache" --exclude "css" --exclude "js" --exclude "backup_migrate" --exclude "styles" --exclude "xmlsitemap" --exclude "honeypot" -czf {0} *'.format(
            files_result_file_path))

    backup_time = time() - start_time

    # File size with thousand seperator, converted to MB.
    db_size = '{:,.0f}'.format(os.path.getsize(database_result_file_path)/float(1 << 20))+" MB"
    file_size = '{:,.0f}'.format(os.path.getsize(files_result_file_path)/float(1 << 20))+" MB"

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

    log.info('Operational statistic | Backup Create | SID - %s | Time - %s | DB size - %s | File size - %s',
             site['sid'], backup_time, db_size, file_size)


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
    Connect to a single applicaiton server, copy over the database and file backups to a temp
    directory, restore them into the Drupal instance, and remove the backup files.
    """
    log.info('Import Backup | Backup - %s | Target Instance - %s',
             backup, target_instance)

    start_time = time()

    # Copy db and files
    backup_db = backup['database']
    backup_files = backup['files']
    backup_source_path = '/nfs/{0}_backups/backups'.format(source_env)
    backup_db_path = '{0}/{1}'.format(backup_source_path, backup['database'])
    backup_files_path = '{0}/{1}'.format(backup_source_path, backup['files'])

    backup_tmp_dir = '{0}/tmp'.format(BACKUP_PATH)
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
