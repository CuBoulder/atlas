"""
Fabric Commands

Commands that run on servers to do the actual work.
"""
import sys
import requests
import re
import os

from fabric.contrib.files import append, exists, sed, upload_template
from fabric.api import *
from fabric.network import disconnect_all
from random import randint
from time import time
from datetime import datetime
from atlas.config import *
from atlas import utilities

atlas_path = '/data/code'
if atlas_path not in sys.path:
    sys.path.append(atlas_path)

# Fabric environmental settings.
env.user = ssh_user
# env.key_filename =

# Allow ~/.ssh/config to be utilized.
env.use_ssh_config = True
env.roledefs = serverdefs[environment]


# TODO: Figure out a better way to deal with the output. Calling functions via
# 'var = execute(func)' seems to suppress a lot of the output.

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
        create_directory_structure(code_folder)
        clone_task = clone_repo(item["git_url"], item["commit_hash"], code_folder)
        print('Got clone response')
        print(clone_task)
        if clone_task is True:
            if item['meta']['is_current']:
                code_folder_current = '{0}/{1}/{2}/{2}-current'.format(
                    code_root,
                    code_type_dir,
                    item['meta']['name'])
                update_symlink(code_folder, code_folder_current)
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
        checkout_repo(updated_item["commit_hash"], code_folder)
        if updated_item['meta']['is_current']:
            code_folder_current = '{0}/{1}/{2}/{2}-current'.format(
                code_root,
                code_type_dir,
                updated_item['meta']['name'])
            update_symlink(code_folder, code_folder_current)


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
    remove_directory(code_folder)
    if item['meta']['is_current']:
        code_folder_current = '{0}/{1}/{2}/{2}-current'.format(
            code_root,
            code_type_dir,
            item['meta']['name'])
        remove_symlink(code_folder_current)


@roles('webservers')
def instance_provision(instance):
    """
    Responds to POSTs to provision an instance to the right places on the server.

    :param instance: The flask.request object, JSON encoded
    :return:
    """
    print 'Instance Provision - {0} - {1}'.format(instance['_id'], instance)

    code_directory = '{0}/{1}'.format(instances_code_root, instance['sid'])
    code_directory_sid = '{0}/{1}'.format(code_directory, instance['sid'])
    code_directory_current = '{0}/current'.format(code_directory)
    web_directory_type = '{0}/{1}'.format(
        instances_web_root,
        instance['type'])
    web_directory_sid = '{0}/{1}'.format(
        web_directory_type,
        instance['sid'])
    profile = utilities.get_single_eve('code', instance['code']['profile'])
    profile_name = profile['meta']['name']

    try:
        result_create_database = execute(create_database, instance=instance)
    except FabricException:
        print 'Database creation failed.'
        return result_create_database

    try:
        result_create_dir_structure = execute(
            create_directory_structure, folder=code_directory)
    except FabricException:
        print 'Create directory structure failed.'
        return result_create_dir_structure

    try:
        result_create_dir_structure_web = execute(
            create_directory_structure, folder=web_directory_type)
    except FabricException:
        print 'Create directory structure failed.'
        return result_create_dir_structure_web

    with cd(code_directory):
        core = utilities.get_code_name_version(instance['code']['core'])
        run('drush dslm-new {0} {1}'.format(instance['sid'], core))

    try:
        result_update_symlink = execute(
            update_symlink, source=code_directory_sid, destination=code_directory_current)
    except FabricException:
        print 'Update symlink failed.'
        return result_update_symlink

    with cd(code_directory_current):
        profile = utilities.get_code_name_version(instance['code']['profile'])
        run('drush dslm-add-profile {0}'.format(profile))

    if nfs_mount_files_dir:
        nfs_dir = nfs_mount_location[environment]
        nfs_files_dir = '{0}/sitefiles/{1}/files'.format(nfs_dir, instance['sid'])
        try:
            result_create_nfs_files_dir = execute(
                create_nfs_files_dir, nfs_dir=nfs_dir, instance_sid=instance['sid'])
        except FabricException:
            print 'Create nfs directory failed.'
            return result_create_nfs_files_dir
        # Replace default files dir with this one
        instance_files_dir = code_directory_current + '/sites/default/files'
        try:
            result_replace_files_directory = execute(
                replace_files_directory, source=nfs_files_dir, destination=instance_files_dir)
        except FabricException:
            print 'Replace file directory failed.'
            return result_replace_files_directory

    try:
        result_create_settings_files = execute(
            create_settings_files, instance=instance, profile_name=profile_name)
    except FabricException:
        print 'Settings file creation failed.'
        return result_create_settings_files

    try:
        result_update_symlink_web = execute(
            update_symlink, source=code_directory_current, destination=web_directory_sid)
    except FabricException:
        print 'Update symlink failed.'
        return result_update_symlink_web

    try:
        result_correct_file_dir_perms = execute(
            correct_file_directory_permissions, instance=instance)
    except FabricException:
        print 'Correct file permissions failed.'
        return result_correct_file_dir_perms


@roles('webserver_single')
def instance_install(instance):
    code_dir = '{0}/{1}'.format(instances_code_root, instance['sid'])
    code_dir_current = '{0}/current'.format(code_dir)
    profile = utilities.get_single_eve('code', instance['code']['profile'])
    profile_name = profile['meta']['name']

    try:
        result_install_instance = execute(
            install_instance, profile_name=profile_name, code_directory_current=code_dir_current)
    except FabricException:
        print 'Instance install failed.'
        return result_install_instance

    try:
        result_correct_file_dir_permissions = execute(
            correct_file_directory_permissions, instance=instance)
    except FabricException:
        print 'Correct file permissions failed.'
        return result_correct_file_dir_permissions


@roles('webservers')
def instance_package_update(instance):
    print('Instance Package Update\n{0}'.format(instance))
    code_directory_sid = '{0}/{1}/{1}'.format(instances_code_root, instance['sid'])
    packages_directory = '{0}/sites/all'.format(code_directory_sid)

    package_name_string = ""
    for package in instance['code']['package']:
        # Append the package name and a space.
        package_name_string += utilities.get_code_name_version(package) + " "
    # Strip the trailing space off the end.
    package_name_string = package_name_string.rstrip()
    print("Ready to add packages - {0}\n{1}".format(
        instance['sid'],
        package_name_string))

    with cd(packages_directory):
        run("drush dslm-remove-all-packages")
        if len(package_name_string) > 0:
            run("drush dslm-add-package {0}".format(package_name_string))


@roles('webservers')
def instance_core_update(instance):
    print('Instance Core Update\n{0}'.format(instance))
    code_directory_sid = '{0}/{1}/{1}'.format(instances_code_root, instance['sid'])
    core_string = utilities.get_code_name_version(instance['code']['core'])

    with cd(code_directory_sid):
        run("drush dslm-switch-core {0}".format(core_string))


@roles('webservers')
def instance_profile_update(instance, original, updates):
    print('Instance Profile Update\n{0}'.format(instance))
    code_directory_sid = '{0}/{1}/{1}'.format(instances_code_root, instance['sid'])
    old_profile = utilities.get_single_eve('code', original['code']['profile'])
    new_profile = utilities.get_single_eve('code', instance['code']['profile'])
    new_profile_full_string = utilities.get_code_name_version(instance['code']['profile'])

    with cd(code_directory_sid + '/profiles'):
        run("rm {0}; ln -s {1}/profiles/{2}/{3} {2}".format(
            old_profile['meta']['name'],
            code_root,
            new_profile['meta']['name'],
            new_profile_full_string))


@roles('webservers')
def instance_profile_swap(instance):
    print('Instance Profile Update\n{0}'.format(instance))
    code_directory_sid = '{0}/{1}/{1}'.format(instances_code_root, instance['sid'])
    profile = utilities.get_single_eve('code', instance['code']['profile'])
    new_profile_full_string = utilities.get_code_name_version(instance['code']['profile'])

    with cd(code_directory_sid + '/profiles'):
        run("rm {0}; ln -s {1}/profiles/{2}/{3} {2}".format(
            profile['meta']['name'],
            code_root,
            profile['meta']['name'],
            new_profile_full_string))


@roles('webservers')
def instance_launch(instance):
    profile = utilities.get_single_eve('code', instance['code']['profile'])
    profile_name = profile['meta']['name']
    try:
        result_create_settings_files = execute(
            create_settings_files, instance=instance, profile_name=profile_name)
    except FabricException:
        print 'Settings files creation failed.'
        return result_create_settings_files

    if environment is 'prod' and instance['pool'] is 'poolb-express':
        # Create GSA collection if needed.
        gsa_task = create_gsa(instance)
        if gsa_task is True:
            print 'GSA Collection - Success'
            machine_name = machine_readable(instance['path'])
            launch_instance(instance=instance, gsa_collection=machine_name)
            return
        else:
            print 'GSA Collection - Failed'
            launch_instance(instance=instance)
    else:
        print 'Instance launch - No GSA'
        launch_instance(instance=instance)


@roles('webserver_single')
def instance_backup(instance):
    """
    Backup the database and files for an instance.
    """
    print('Instance - Backup\m{0}'.format(instance))
    # Setup all the variables we will need.
    web_directory = '{0}/{1}/{2}'.format(
        instances_web_root,
        instance['type'],
        instance['sid'])
    date_string = datetime.now().strftime("%Y-%m-%d")
    date_time_string = datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
    backup_path = '{0}/{1}/{2}'.format(
        backup_directory,
        instance['sid'],
        date_string)
    database_result_file_path = '{0}/{1}_{2}.sql'.format(
        backup_path,
        instance['sid'],
        date_time_string)
    files_result_file_path = '{0}/{1}_{2}.tar.gz'.format(
        backup_path,
        instance['sid'],
        date_time_string)
    nfs_dir = nfs_mount_location[environment]
    nfs_files_dir = '{0}/sitefiles/{1}/files'.format(nfs_dir, instance['sid'])
    # Start the actual process.
    create_directory_structure(backup_path)
    with cd(web_directory):
        run('drush sql-dump --result-file={0}'.format(database_result_file_path))
        run('tar -czf {0} {1}'.format(files_result_file_path, nfs_files_dir))


@roles('webservers')
def instance_take_down(instance):
    """
    Point the instance to the 'Down' page.
    """
    print('Instance Take down\n{0}'.format(instance))
    code_directory_current = '{0}/{1}/current'.format(
        instances_code_root,
        instance['sid'])
    update_symlink(instances_down_path, code_directory_current)


@roles('webservers')
def instance_restore(instance):
    """
    Point the instance to the current release.
    """
    code_directory_current = '{0}/{1}/current'.format(
        instances_code_root,
        instance['sid'])
    code_directory_sid = '{0}/{1}/{1}'.format(
        instances_code_root,
        instance['sid'])
    update_symlink(code_directory_sid, code_directory_current)
    # TODO: Figure out what we need to do with Bondo during a restore.


@roles('webservers')
def instance_remove(instance):
    """
    Responds to DELETEs to remove instance from the server.

    :param instance: Item to remove
    :return:
    """
    print 'Instance - Remove\n{0}'.format(instance)
    code_directory = '{0}/{1}'.format(instances_code_root, instance['sid'])
    web_directory = '{0}/{1}/{2}'.format(
        instances_web_root,
        instance['type'],
        instance['sid'])
    web_directory_path = '{0}/{1}/{2}'.format(
        instances_web_root,
        instance['type'],
        instance['path'])

    delete_database(instance)

    remove_symlink(web_directory)
    remove_symlink(web_directory_path)

    if nfs_mount_files_dir:
        nfs_dir = nfs_mount_location[environment]
        nfs_files_dir = '{0}/sitefiles/{1}'.format(nfs_dir, instance['sid'])
        remove_directory(nfs_files_dir)

    remove_directory(code_directory)


def correct_file_directory_permissions(instance):
    code_directory_sid = '{0}/{1}/{1}'.format(instances_code_root, instance['sid'])
    web_directory_sid = '{0}/{1}/{2}'.format(instances_web_root, instance['type'], instance['sid'])
    nfs_dir = nfs_mount_location[environment]
    nfs_files_dir = '{0}/sitefiles/{1}/files'.format(nfs_dir, instance['sid'])
    nfs_files_tmp_dir = '{0}/sitefiles/{1}/tmp'.format(nfs_dir, instance['sid'])
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
def command_run_single(instance, command, warn_only=False):
    """
    Run a command on a single server

    :param instance: Instance to run command on
    :param command: Command to run
    :return:
    """
    print 'Command - Single Server | {0} | {1}'.format(instance['sid'], command)
    web_directory = '{0}/{1}/{2}'.format(
        instances_web_root,
        instance['type'],
        instance['sid'])
    with settings(warn_only=warn_only):
        with cd(web_directory):
            command_result = run("{0}".format(command), pty=False)
            # Return the failure if there is one.
            if command_result.failed:
                return command_result


@roles('webservers')
def command_run(instance, command):
    """
    Run a command on a all webservers.

    :param instance: Instance to run command on
    :param command: Command to run
    :return:
    """
    print('Command - {0}\n{1}'.format(instance['sid'], command))
    web_directory = '{0}/{1}/{2}'.format(
        instances_web_root,
        instance['type'],
        instance['sid'])
    with cd(web_directory):
        run('{0}'.format(command))


@roles('webserver_single')
def update_database(instance):
    """
    Run a updb

    :param instance: Instance to run command on
    :return:
    """
    print('Database Update | {0}'.format(instance))
    code_directory_sid = '{0}/{1}/{1}'.format(instances_code_root, instance['sid'])
    with cd(code_directory_sid):
        print('Running database updates.')
        run("drush updb -y")


@roles('webserver_single')
def registry_rebuild(instance):
    """
    Run a drush rr

    :param instance: Instance to run command on
    :return:
    """
    print 'Drush registry rebuild | {0}'.format(instance)
    code_directory_sid = '{0}/{1}/{1}'.format(instances_code_root, instance['sid'])
    with cd(code_directory_sid):
        run("drush rr")


@roles('webservers')
def clear_apc():
    run("wget -q -O - http://localhost/sysadmintools/apc/clearapc.php")


def drush_cache_clear(sid):
    code_directory_current = '{0}/{1}/current'.format(instances_code_root, sid)
    with cd(code_directory_current):
        run("drush cc all")


@roles('webservers')
def rewrite_symlinks(instance):
    print 'Rewrite symlinks | {0}'.format(instance)
    code_directory_current = '{0}/{1}/current'.format(instances_code_root, instance['sid'])
    web_directory = '{0}/{1}/{2}'.format(instances_web_root, instance['type'], instance['sid'])
    if instance['pool'] != 'poolb-homepage':
        update_symlink(code_directory_current, web_directory)
    if instance['status'] == 'launched' and instance['pool'] != 'poolb-homepage':
        path_symlink = '{0}/{1}/{2}'.format(instances_web_root, instance['type'], instance['path'])
        update_symlink(web_directory, path_symlink)
    if instance['status'] == 'launched' and instance['pool'] == 'poolb-homepage':
        web_directory = '{0}/{1}'.format(instances_web_root, 'homepage')
        update_symlink(code_directory_current, web_directory)


@roles('webservers')
def update_settings_file(instance):
    print 'Update Settings Files - {0}'.format(instance)
    profile = utilities.get_single_eve('code', instance['code']['profile'])
    profile_name = profile['meta']['name']
    try:
        result_create_settings_files = execute(
            create_settings_files, instance=instance, profile_name=profile_name)
    except FabricException:
        print 'Settings files creation failed.'
        return result_create_settings_files


@roles('webservers')
def update_homepage_extra_files():
    """
    SCP the homepage files to web heads.
    :return:
    """
    send_from_robots = '{0}/files/homepage_robots'.format(atlas_location)
    send_from_htaccess = '{0}/files/homepage_htaccess'.format(atlas_location)
    send_to = '{0}/homepage'.format(instances_web_root)
    run("chmod -R u+w {}".format(send_to))
    run("rm -f {0}/robots.txt".format(send_to))
    put(send_from_robots, "{0}/robots.txt".format(send_to))
    run("rm -f {0}/.htaccess".format(send_to))
    put(send_from_htaccess, "{0}/.htaccess".format(send_to))
    run("chmod -R u+w {}".format(send_to))


# Removed because this sometimes causes provision to fail. Since the function is immutable, we don't
# need to run it a single time. The extra work is worth the stability in provisions.
# @runs_once
def create_nfs_files_dir(nfs_dir, instance_sid):
    nfs_files_dir = '{0}/sitefiles/{1}/files'.format(nfs_dir, instance_sid)
    nfs_tmp_dir = '{0}/sitefiles/{1}/tmp'.format(nfs_dir, instance_sid)
    create_directory_structure(nfs_files_dir)
    create_directory_structure(nfs_tmp_dir)


# Fabric utility functions.
# TODO: Add decorator to run on a single host if called via 'execute'.
# Need to make sure it runs on all when called without execute.
def create_directory_structure(folder):
    print 'Create directory\n{0}'.format(folder)
    run('mkdir -p {0}'.format(folder))


def remove_directory(folder):
    print 'Remove directory\n{0}'.format(folder)
    run('rm -rf {0}'.format(folder))


def remove_symlink(symlink):
    print 'Remove symlink\n{0}'.format(symlink)
    run('rm -f {0}'.format(symlink))


@runs_once
def create_database(instance):
    print 'Instance Provision - {0} - Create DB'.format(instance['_id'])
    if environment != 'local':
        os.environ['MYSQL_TEST_LOGIN_FILE'] = '/home/{0}/.mylogin.cnf'.format(
            ssh_user)
        mysql_login_path = "{0}_{1}".format(database_user, environment)
        mysql_info = '{0} --login-path={1} -e'.format(mysql_path, mysql_login_path)
        database_password = utilities.decrypt_string(instance['db_key'])
        local('{0} \'CREATE DATABASE `{1}`;\''.format(mysql_info, instance['sid']))
        # TODO: Make IP addresses config.
        local("{0} \"CREATE USER '{1}'@'172.20.62.0/255.255.255.0' IDENTIFIED BY '{2}';\"".format(
            mysql_info,
            instance['sid'],
            database_password))
        sql = "GRANT ALL PRIVILEGES ON {0}.* TO '{0}'@'172.20.62.0/255.255.255.0';".format(
            instance['sid'])
        local("{0} \"{1}\"".format(mysql_info, sql))
    else:
        with settings(host_string='express.local'):
            run("mysql -e 'create database `{}`;'".format(instance['sid']))


@runs_once
def delete_database(instance):
    if environment != 'local':
        # TODO: Make file location config.
        os.environ['MYSQL_TEST_LOGIN_FILE'] = '/home/{0}/.mylogin.cnf'.format(
            ssh_user)
        mysql_login_path = "{0}_{1}".format(database_user, environment)
        mysql_info = '{0} --login-path={1} -e'.format(mysql_path, mysql_login_path)
        database_password = utilities.decrypt_string(instance['db_key'])
        local('{0} \'DROP DATABASE IF EXISTS `{1}`;\''.format(mysql_info, instance['sid']))
        # TODO: Make IP addresses config.
        local("{0} \"DROP USER '{1}'@'172.20.62.0/255.255.255.0';\"".format(
            mysql_info,
            instance['sid']))
    else:
        with settings(host_string='express.local'):
            run("mysql -e 'DROP DATABASE IF EXISTS `{}`;'".format(instance['sid']))


def create_settings_files(instance, profile_name):
    sid = instance['sid']
    if 'route' in instance:
        route = utilities.get_single_eve('route', instance['route'])
        path = route['source']
    else:
        path = instance['sid']
    # If the instance is launching or launched, we add 'cu_path' and redirect the
    # p1 URL.
    status = instance['status']
    instance_id = instance['_id']
    statistics = instance['statistics']
    # TODO: Fix this for new site record.
    if instance['settings'].get('siteimprove_site'):
        siteimprove_site = instance['settings']['siteimprove_site']
    else:
        siteimprove_site = None
    if instance['settings'].get('siteimprove_group'):
        siteimprove_group = instance['settings']['siteimprove_group']
    else:
        siteimprove_group = None
    page_cache_maximum_age = instance['settings']['page_cache_maximum_age']
    atlas_url = '{0}/'.format(api_urls[environment])
    database_password = utilities.decrypt_string(instance['db_key'])

    profile = utilities.get_single_eve('code', instance['code']['profile'])
    profile_name = profile['meta']['name']

    template_dir = '{0}/templates'.format(atlas_location)

    print template_dir

    destination = "{0}/{1}/{1}/sites/default".format(instances_code_root, instance['sid'])

    local_pre_settings_variables = {
        'profile': profile_name,
        'sid': sid,
        'atlas_id': instance_id,
        'atlas_url': atlas_url,
        'atlas_username': service_account_username,
        'atlas_password': service_account_password,
        'path': path,
        'status': status,
        'pool': instance['pool'],
        'atlas_statistics_id': statistics,
        'siteimprove_site': siteimprove_site,
        'siteimprove_group': siteimprove_group
    }

    print 'Settings Pre Variables - {0}'.format(local_pre_settings_variables)

    upload_template('settings.local_pre.php',
                    destination=destination,
                    context=local_pre_settings_variables,
                    use_jinja=True,
                    template_dir=template_dir,
                    backup=False,
                    mode='0664')

    settings_variables = {
        'profile': profile_name,
        'sid': sid,
        'reverse_proxies': env.roledefs['varnish_servers'],
        'varnish_control': varnish_control_terminals[environment],
        'memcache_servers': env.roledefs['memcache_servers'],
        'environment': environment if environment != 'prod' else ''
    }

    print 'Settings  Variables - {0}'.format(settings_variables)

    upload_template('settings.php',
                    destination=destination,
                    context=settings_variables,
                    use_jinja=True,
                    template_dir=template_dir,
                    backup=False,
                    mode='0664')

    local_post_settings_variables = {
        'sid': sid,
        'pw': database_password,
        'page_cache_maximum_age': page_cache_maximum_age,
        'database_servers': env.roledefs['database_servers'],
        'memcache_servers': env.roledefs['memcache_servers'],
        'environment': environment if environment != 'prod' else ''
    }

    print 'Settings Post Variables - {0}'.format(local_post_settings_variables)

    upload_template('settings.local_post.php',
                    destination=destination,
                    context=local_post_settings_variables,
                    use_jinja=True,
                    template_dir=template_dir,
                    backup=False,
                    mode='0664')


@runs_once
def install_instance(profile_name, code_directory_current):
    with cd(code_directory_current):
        run('drush site-install -y {0}'.format(profile_name))
        run('drush rr')


def clone_repo(git_url, checkout_item, destination):
    with settings(warn_only=True):
        print 'Clone Repo: {0}\n Checkout: {1}'.format(git_url, checkout_item)
        clone_result = run('git clone {0} {1}'.format(git_url, destination), pty=False)

        if clone_result.failed:
            print 'Git clone failed\n{0}'.format(clone_result)
            return clone_result

        with cd(destination):
            checkout_result = run('git checkout {0}'.format(checkout_item), pty=False)
            if checkout_result.failed:
                print 'Git checkout failed\n{0}'.format(checkout_result)
                return checkout_result
            clean_result = run('git clean -f -f -d', pty=False)
            if clean_result.failed:
                print 'Git clean failed\n{0}'.format(clean_result)
                return clean_result
            return True


def checkout_repo(checkout_item, destination):
    print 'Checkout Repo: {0}\n Checkout: {1}'.format(destination, checkout_item)
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
    if exists(destination):
        run('rm {0}'.format(destination))
    run('ln -s {0} {1}'.format(source, destination))


def machine_readable(string):
    """
    Replace all spaces with underscores and remove any non-alphanumeric
    characters.

    :param string:
    """
    new_string = string.lower().replace(" ", "_")
    return re.sub(r'\W+', '', new_string)


# GSA utilities
def create_gsa(instance):
    machine_name = machine_readable(instance['path'])
    if not gsa_collection_exists(machine_name):
        index_path = "http://www.colorado.edu/{0}/".format(instance['path'])
        gsa_create_collection(machine_name, index_path)


def gsa_collection_exists(name):
    """
    Return if a collection of the given name already exists.
    """
    raw = gsa_collection_data()
    entries = gsa_all_collections(raw)
    collections = gsa_parse_entries(entries)
    return name in collections


def gsa_create_collection(name, follow):
    """
    Creates a collection in the Google Search Appliance.
    """
    auth_token = gsa_auth()
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
        print r.text


def gsa_auth():
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


def gsa_collection_data():
    """
    Gets the list of collections
    """
    auth_token = gsa_auth()
    url = "http://{0}:8000/feeds/collection".format(gsa_host)
    headers = {"Content-Type": "application/atom+xml",
               "Authorization": "GoogleLogin auth={0}".format(auth_token)}
    r = requests.get(url, headers=headers, verify=False)
    if r.ok:
        return r.text


def gsa_next_target(page):
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


def gsa_all_collections(page):
    """
    Helper for collection_exists. Iterates through the <entry> elements in the text.
    """
    entries = []
    while True:
        entry, endpos = gsa_next_target(page)
        if entry:
            entries.append(entry)
            page = page[endpos:]
        else:
            break
    return entries


def gsa_parse_entries(entries):
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


def launch_instance(instance, gsa_collection=False):
    """
    Create symlinks with new instance name.
    """
    print 'Launch subtask'
    code_directory = '{0}/{1}'.format(instances_code_root, instance['sid'])
    code_directory_current = '{0}/current'.format(code_directory)

    if instance['pool'] in ['poolb-express', 'poolb-homepage'] and instance['type'] == 'express':
        # Get the route entry
        route = utilities.get_single_eve('route', instance['route'])
        if instance['pool'] == 'poolb-express':
            web_directory = '{0}/{1}'.format(instances_web_root, instance['type'])
            web_directory_path = '{0}/{1}'.format(web_directory, route['source'])
            with cd(web_directory):
                # If the route is nested like 'lab/atlas', make the 'lab' directory
                if "/" in route['source']:
                    lead_path = "/".join(route['source'].split("/")[:-1])
                    create_directory_structure(lead_path)

                # Create a new symlink using instance's updated path
                if not exists(web_directory_path):
                    update_symlink(code_directory_current, route['source'])
                # enter new instance directory
                with cd(web_directory_path):
                    clear_apc()
                    if gsa_collection:
                        # Set the collection name
                        run("drush vset --yes google_appliance_collection {0}".format(
                            gsa_collection))
                    # Clear caches at the end of the launch process to show
                    # correct pathologic rendered URLS.
                    drush_cache_clear(instance['sid'])
            # Assign it to an update group.
            update_group = randint(0, 10)
        if instance['pool'] == 'poolb-homepage':
            web_directory = '{0}/{1}'.format(instances_web_root, 'homepage')
            with cd(instances_web_root):
                update_symlink(code_directory_current, web_directory)
                # enter new instance directory
            with cd(web_directory):
                clear_apc()
                drush_cache_clear(instance['sid'])
            # Assign instance to update group 12.
            update_group = 12
        payload = {'status': 'launched', 'update_group': update_group}
        utilities.patch_eve('instance', instance['_id'], payload)


def diff_f5():
    """
    Copy f5 configuration file to local sever, parse txt and create or update
    instance items.

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
    local('scp {0}:/config/filestore/files_d/Common_d/data_group_d/\:Common\:{1}* {2}/{1}.tmp'.format(
        serverdefs[environment]['load_balancers'][0],
        load_balancer_config_files[environment],
        load_balancer_config_dir))

    # Open file from f5
    with open('{0}.tmp'.format(load_balancer_config_file), "r") as ifile:
        data = ifile.read()
    # Use regex to parse out path values
    p = re.compile('"(.+/?)" := "(\w+(-\w+)?)",')
    routes = p.findall(data)
    # Iterate through routes found in f5 data
    for route in routes:
        # Get path without leading slash
        print 'f5 | Route checking | {0}'.format(route)
        source = route[0][1:]

        route_query = 'where={{"source":"{0}"}}'.format(source)
        api_routes = utilities.get_eve('route', route_query)

        if not api_routes or len(api_routes['_items']) == 0:
            subject = 'Route record missing'
            message = "Source '{0}' is in the f5, but does not have a route record.".format(source)
            utilities.send_email(message=message, subject=subject, to=devops_team)
            print 'f5 | No Route for path | {0}'.format(source)


def update_f5():
    # Like 'WWWNGProdDataGroup.dat'
    old_file_name = load_balancer_config_files[environment]
    # Like 'WWWNGDevDataGroup.dat.1402433484.bac'
    new_file_name = "{0}.{1}.bac".format(
        load_balancer_config_files[environment],
        str(time()).split('.')[0])
    load_balancer_config_dir = '{0}/fabfile'.format(atlas_location)
    # Find instances that are 'launching', or 'launched' and have a route
    instances = utilities.get_eve('instance', 'where={"status":{"$in":["launching","launched"]},"route":{"$exists":1}}&max_results=3000')

    # TODO: delete old backup files

    # Write data to file
    with open("{0}/{1}".format(load_balancer_config_dir, load_balancer_config_files[environment]),
              "w") as ofile:
        for instance in instances['_items']:
            # Get route
            route = utilities.get_single_eve('route', instance['route'])
            # In case a path was saved with a leading slash
            source = route['source'] if route['source'][0] == '/' else '/' + route['source']
            # Ignore 'p1' paths but let the /p1 pattern through
            if not source.startswith("/p1") or len(source) == 3:
                ofile.write('"{0}" := "{1}",\n'.format(source, route['route_type']))

    execute(exportf5,
            new_file_name=new_file_name,
            load_balancer_config_dir=load_balancer_config_dir)


@roles('load_balancers')
def exportf5(new_file_name, load_balancer_config_dir):
    """
    Backup configuration file on f5 server, replace the active file, and reload
    the configuration.

    """
    # Copy the new configuration file to the server.
    put("{0}/{1}".format(load_balancer_config_dir, load_balancer_config_files[environment]), "/tmp")
    # Load the new configuration.
    run("tmsh modify sys file data-group {0} source-path file:/tmp/{0}".format(load_balancer_config_files[environment]))
    run("tmsh save sys config")
    run("tmsh run cm config-sync to-group {0}".format(load_balancer_config_group[environment]))
    disconnect_all()
