"""
    atlas.instance_operations
    ~~~~
    Commands that run on servers to deploy instances.

    Instance methods:
    Create - Local - All symlinks are in place, DB exists, NFS mount is attached
    Install - Remote - Drupal install command runs
    Update - Local and Remote - Update code or configuration; optionally clear caches, rebuild
        registry, and/or run database update script.
    Repair - Check that only intended code exists in instance, add any missing code. If extra code
        is found, raise an exception and open a ticket.
    Delete - Remove instance symlinks, settings file, NFS files, and database.
    Backup - Create a database and NFS files backup of the instance.
    Restore - Restore backup to a new `sid`
"""
import logging
import os
import stat
from grp import getgrnam
from shutil import copyfile

from jinja2 import Environment, PackageLoader

from atlas import utilities
from atlas.config import (ENVIRONMENT, CODE_ROOT, LOCAL_CODE_ROOT, LOCAL_INSTANCE_ROOT, LOCAL_WEB_ROOT, CORE_WEB_ROOT_SYMLINKS, NFS_MOUNT_FILES_DIR, NFS_MOUNT_LOCATION, SAML_AUTH, SERVICE_ACCOUNT_USERNAME, SERVICE_ACCOUNT_PASSWORD, VARNISH_CONTROL_KEY, SMTP_PASSWORD, WEBSERVER_USER_GROUP)
from atlas.config_servers import (SERVERDEFS, ATLAS_LOGGING_URLS, API_URLS, VARNISH_CONTROL_TERMINALS, BASE_URLS)

# Setup a sub-logger. See tasks.py for longer comment.
log = logging.getLogger('atlas.instance_operations')


def instance_create(instance):
    """Create database, symlink structure, settings file, and NFS space for an instance.

    Arguments:
        instance {dict} -- complete instance dict from POST request
    """
    log.info('Instance | Provision | Instance ID - %s', instance['_id'])
    log.debug('Instance | Provision | Instance ID - %s | Instance - %s', instance['_id'], instance)
    # Setup path variables
    instance_code_path_sid = '{0}/{1}/{1}'.format(LOCAL_INSTANCE_ROOT, instance['sid'])
    instance_code_path_current = '{0}/{1}/current'.format(LOCAL_INSTANCE_ROOT, instance['sid'])
    instance_web_path_sid = '{0}/{1}'.format(LOCAL_WEB_ROOT, instance['sid'])
    instance_web_path_path = '{0}/{1}'.format(LOCAL_WEB_ROOT, instance['path'])
    log.debug('Instance | Provision | Instance sid path - %s', instance_code_path_sid)
    # Setup code assets
    profile = utilities.get_single_eve('code', instance['code']['profile'])
    log.debug('Instance | Provision | Profile - %s', profile)
    core = utilities.get_single_eve('code', instance['code']['core'])
    # Setup code paths
    core_path = utilities.code_path(core)
    profile_path = utilities.code_path(profile)
    # Create structure in LOCAL_INSTANCE_ROOT
    if os.path.exists(instance_code_path_sid):
        raise Exception('Destinaton directory already exists')
    os.makedirs(instance_code_path_sid)
    ## Add Core
    # Get a list of files in the Core source directory
    core_files = os.listdir(core_path)
    # Iterate through the source files and symlink when applicable.
    for core_file in core_files:
        if core_file in ['sites', 'profiles']:
            continue
        if utilities.ignore_code_file(core_file):
            continue
        source_path = core_path + '/' + core_file
        destination_path = instance_code_path_sid + '/' + core_file
        os.symlink(source_path, destination_path)
   # Create Instance specific directory structure
    directories_to_create = ['sites',
                             'sites/all',
                             'sites/all/modules',
                             'sites/all/libraries',
                             'sites/all/themes',
                             'sites/default',
                             'sites/default/files',
                             'profiles']
    for directory in directories_to_create:
        target_dir = instance_code_path_sid + '/' + directory
        os.mkdir(target_dir)
    # Copy over default settings file so that this instance is like a default install.
    source_path = core_path + '/sites/default/default.settings.php'
    destination_path = instance_code_path_sid + '/sites/default/default.settings.php'
    copyfile(source_path, destination_path)
    # Include links to the profiles that we are not using so that the site doesn't white screen if
    # the deployed profile gets disabled.
    core_profiles = os.listdir(core_path + '/profiles')
    for core_profile in core_profiles:
        source_path = core_path + '/profiles/' + core_profile
        destination_path = instance_code_path_sid + '/profiles/' + core_profile
        os.symlink(source_path, destination_path)
    ## Add profile
    destination_path = instance_code_path_sid + '/profiles/' + profile['meta']['name']
    os.symlink(profile_path, destination_path)
    ## Add packages
    if 'package' in instance['code']:
        for item in instance['code']['package']:
            package = utilities.get_single_eve('code', item)
            destination_path = instance_code_path_sid + '/sites/all/' + package['meta']['name']
            os.symlink(utilities.code_path(package), destination_path)
    ## Add NFS mounted files directory
    if NFS_MOUNT_FILES_DIR:
        # Setup paths
        nfs_files_dir = NFS_MOUNT_LOCATION[ENVIRONMENT] + '/' + instance['sid']
        site_files_dir = instance_code_path_sid + '/sites/default/files'
        nfs_src = nfs_files_dir + '/files'
         # Make dir on mount
        nfs_directories_to_create = [ nfs_files_dir, nfs_src, nfs_files_dir + '/tmp']
        for directory in nfs_directories_to_create:
            os.mkdir(directory)
        # Replace default files dir with one from NFS mount
        # Will error if there are files in the directory
        os.rmdir(site_files_dir)
        os.symlink(nfs_src, site_files_dir)
    # Create setttings file
    create_settings_files(instance)
    # Correct file permissions
    correct_fs_permissions(instance)
    # Create symlinks for current in instance root, 'sid' and 'path' (if needed) in web root.
    os.symlink(instance_code_path_sid, instance_code_path_current)
    os.symlink(instance_code_path_sid, instance_web_path_sid)
    if instance['path'] is not instance['sid']:
        os.symlink(instance_code_path_sid, instance_web_path_path)


def create_settings_files(instance):
    """Create settings.php from template and render the resulting file onto the server.

    Arguments:
        instance {dict} -- full site object
    """
    log.info('Instance | Settings file | Instance ID - %s', instance['_id'])

    # If the settings file exists, change permissions to allow us to update the template.
    file_destination = "{0}/{1}/{1}/sites/default/settings.php".format(
        LOCAL_INSTANCE_ROOT, instance['sid'])
    # Check to see if file exists and is not writable.
    if os.access(file_destination, os.F_OK) and not os.access(file_destination, os.W_OK):
        # Make it writeable
        os.chmod(file_destination, stat.S_IWRITE)

    # Setup variables
    if instance['settings'].get('siteimprove_site'):
        siteimprove_site = instance['settings']['siteimprove_site']
    else:
        siteimprove_site = None
    if instance['settings'].get('siteimprove_group'):
        siteimprove_group = instance['settings']['siteimprove_group']
    else:
        siteimprove_group = None

    profile = utilities.get_single_eve('code', instance['code']['profile'])

    if ('cse_creator' in instance['settings']) and ('cse_id' in instance['settings']):
        google_cse_csx = instance['settings']['cse_creator'] + ':' + instance['settings']['cse_id']
    else:
        google_cse_csx = None

    tmp_path = '{0}/{1}/tmp'.format(NFS_MOUNT_LOCATION[ENVIRONMENT], instance['sid'])

    settings_variables = {
        'profile': profile['meta']['name'],
        'sid': instance['sid'],
        'atlas_id': instance['_id'],
        'atlas_url': API_URLS[ENVIRONMENT] + '/',
        'atlas_logging_url': ATLAS_LOGGING_URLS[ENVIRONMENT],
        'atlas_username': SERVICE_ACCOUNT_USERNAME,
        'atlas_password': SERVICE_ACCOUNT_PASSWORD,
        'path': instance['path'],
        'status': instance['status'],
        'atlas_statistics_id': instance['statistics'],
        'siteimprove_site': siteimprove_site,
        'siteimprove_group': siteimprove_group,
        'google_cse_csx': google_cse_csx,
        'reverse_proxies': SERVERDEFS[ENVIRONMENT]['varnish_servers'],
        'varnish_control': VARNISH_CONTROL_TERMINALS[ENVIRONMENT],
        'varnish_control_key': VARNISH_CONTROL_KEY,
        'pw': utilities.decrypt_string(instance['db_key']),
        'page_cache_maximum_age': instance['settings']['page_cache_maximum_age'],
        'database_servers': SERVERDEFS[ENVIRONMENT]['database_servers'],
        'environment': ENVIRONMENT,
        'tmp_path': tmp_path,
        'saml_pw': SAML_AUTH,
        'smtp_client_hostname': BASE_URLS[ENVIRONMENT],
        'smtp_password': SMTP_PASSWORD,
    }

    log.info('fabric_tasks | Render settings file')
    # Create a template environment with the default settings and a loader that looks up the
    # templates in the templates folder inside the Atlas python package.
    # We don't do autoescaping, because there is no PHP support.
    jinja_env = Environment(loader=PackageLoader('atlas', 'templates'))
    template = jinja_env.get_template('settings.php')
    render = template.render(settings_variables)

    # Write the render to a file.
    with open(file_destination, "wb") as open_file:
        open_file.write(render)


def correct_fs_permissions(instance):
    """Apply the correct permissions to code and NFS files, directories, and symlinks.

    Arguments:
        instance {dict} -- instance object
    """
    log.debug('Instance | Correct FS permissions | Instance - %s', instance)
    instance_path = "{0}/{1}/{1}".format(LOCAL_INSTANCE_ROOT, instance['sid'])
    # Walk produces 3-tuple for each dir or file, does not follow symlinks.
    for root, directories, files in os.walk(instance_path, topdown=False):
        for directory in [os.path.join(root, d) for d in directories]:
            # Octet mode, Python 3 compatible
            # Change directory permissions
            os.chmod(directory, 0o775)
            # Change group: lookup gid (Group ID), `fchown` uses IDs
            group = getgrnam(WEBSERVER_USER_GROUP)
            log.debug('Instance | Correct FS permissions | Group - %s', group)
            log.debug('Instance | Correct FS permissions | Group ID - %s', group.gr_gid)
            os.fchown(directory, -1, group.gr_gid)
        for file in [os.path.join(root, f) for f in files]:
            # Octet mode, Python 3 compatible
            # Change file permissions
            os.chmod(file, 0o664)


def sync_instances():
    """Copy the instance files to all of the relevant nodes.
    """
    log.info('Instances | Sync')
    hosts = SERVERDEFS[ENVIRONMENT]['webservers'] + SERVERDEFS[ENVIRONMENT]['operations_server']
    # Sync INSTANCE_ROOT then WEB_ROOT
    for root in [tuple([LOCAL_INSTANCE_ROOT, INSTANCE_ROOT]), tuple([LOCAL_WEB_ROOT, WEB_ROOT])]:
        utilities.sync(root[0], hosts, root[1])
