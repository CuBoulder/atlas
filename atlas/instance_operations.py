"""
    atlas.instance_operations
    ~~~~
    Commands that run on servers to deploy instances.

    Instance methods:
    Create - Local - All symlinks are in place, DB exists, NFS mount is attached
    Update - Local and Update code or configuration;
    Delete - Local - Remove instance symlinks, delete settings file, delete NFS files.; Remote - Delete database.

    # TODO After `util` and `ops` servers are combined
    # Repair - Local - Check that only intended code exists in instance, add any missing code. If extra code is found, raise an exception and open a ticket.
    # Install - Remote - Drupal install command runs
    # Update - Remote - Run optional clear caches, rebuild registry, and/or updb.
    # Backup - Remote - Create a database and NFS files backup of the instance.
    # Restore - Local - Restore files on an new instance; Remote - Restore database on instance.
"""
import logging
import os
import re
import stat

from grp import getgrnam
from shutil import copyfile, rmtree
from pwd import getpwuid

from jinja2 import Environment, PackageLoader

from atlas import utilities
from atlas.config import (ENVIRONMENT, INSTANCE_ROOT, WEB_ROOT, CORE_WEB_ROOT_SYMLINKS,
                          NFS_MOUNT_FILES_DIR, NFS_MOUNT_LOCATION, SAML_AUTH,
                          SERVICE_ACCOUNT_USERNAME, SERVICE_ACCOUNT_PASSWORD, VARNISH_CONTROL_KEY,
                          SMTP_PASSWORD, WEBSERVER_USER_GROUP, ATLAS_LOCATION, SITE_DOWN_PATH,
                          SSH_USER, SERVICENOW_KEY)
from atlas.config_servers import (SERVERDEFS, ATLAS_LOGGING_URLS, API_URLS,
                                  VARNISH_CONTROL_TERMINALS, BASE_URLS)

# Setup a sub-logger. See tasks.py for longer comment.
log = logging.getLogger('atlas.instance_operations')


def instance_create(instance, nfs_preserve=False):
    """Create symlink structure, settings file, and NFS space for an instance.

    Arguments:
        instance {dict} -- complete instance dict from POST request
    """
    log.info('Instance | Provision | Instance ID - %s', instance['_id'])
    log.debug('Instance | Provision | Instance ID - %s | Instance - %s', instance['_id'], instance)
    # Setup path variables
    instance_code_path_sid = '{0}/{1}/{1}'.format(INSTANCE_ROOT, instance['sid'])
    instance_code_path_current = '{0}/{1}/current'.format(INSTANCE_ROOT, instance['sid'])
    instance_web_path_sid = '{0}/{1}'.format(WEB_ROOT, instance['sid'])
    log.debug('Instance | Provision | Instance sid path - %s', instance_code_path_sid)
    # Create structure in INSTANCE_ROOT
    if os.path.exists(instance_code_path_sid):
        raise Exception('Destinaton directory already exists')
    os.makedirs(instance_code_path_sid)
    # Add Core
    switch_core(instance)
    # Add profile
    switch_profile(instance)
    # Add packages
    switch_packages(instance)
    # Add NFS mounted files directory
    if NFS_MOUNT_FILES_DIR:
        # Setup paths
        nfs_files_dir = NFS_MOUNT_LOCATION[ENVIRONMENT] + '/' + instance['sid']
        site_files_dir = instance_code_path_sid + '/sites/default/files'
        nfs_src = nfs_files_dir + '/files'
        # Make dir on mount if it does not exist or we are not preserving a previous mount.
        if not os.access(nfs_src, os.F_OK) or not nfs_preserve:
            nfs_directories_to_create = [nfs_files_dir, nfs_src, nfs_files_dir + '/tmp']
            for directory in nfs_directories_to_create:
                os.mkdir(directory)
        # Replace default files dir with one from NFS mount
        # Will error if there are files in the directory
        # Check is path exists, is a directory (matches symlink)
        if os.path.exists(site_files_dir) and os.path.isdir(site_files_dir):
            # Check for symlink
            if not os.path.islink(site_files_dir):
                # Check if directory is empty and remove it if it is
                if not os.listdir(site_files_dir):
                    os.rmdir(site_files_dir)
            else:
                # Remove symlink
                os.remove(site_files_dir)
            os.symlink(nfs_src, site_files_dir)
    # Create setttings file
    switch_settings_files(instance)
    # Correct file permissions
    correct_fs_permissions(instance)
    # Create symlinks for current in instance root, 'sid' and 'path' (if needed) in web root.
    log.info('Instance | Provision | Instance ID - %s | Symlink current - %s | Symlink web - %s',
             instance['_id'], instance_code_path_current, instance_web_path_sid)
    utilities.relative_symlink(instance_code_path_sid, instance_code_path_current)
    utilities.relative_symlink(instance_code_path_current, instance_web_path_sid)
    if instance['status'] in ['launched', 'launching']:
        switch_web_root_symlinks(instance)


def instance_delete(instance, nfs_preserve=False):
    """Delete symlink structure, settings file, and NFS space for an instance.

    Arguments:
        instance {dict} -- full instance record
    """
    log.info('Instance | Delete | Instance ID - %s', instance['_id'])
    log.debug('Instance | Delete | Instance ID - %s | Instance - %s', instance['_id'], instance)
    # Setup path variables
    instance_code_path = '{0}/{1}'.format(INSTANCE_ROOT, instance['sid'])
    instance_code_path_current = '{0}/{1}/current'.format(INSTANCE_ROOT, instance['sid'])
    instance_web_path_sid = '{0}/{1}'.format(WEB_ROOT, instance['sid'])
    instance_web_path_path = '{0}/{1}'.format(WEB_ROOT, instance['path'])
    # Remove symlinks and directories
    symlinks_to_remove = [instance_code_path_current, instance_web_path_sid, instance_web_path_path]
    # Directories to remove
    directories_to_remove = [instance_code_path]
    if NFS_MOUNT_FILES_DIR:
        # Remove dir on mount unless we are preserving it, like when we 'heal' an instance.
        if not nfs_preserve:
            nfs_files_dir = NFS_MOUNT_LOCATION[ENVIRONMENT] + '/' + instance['sid']
            directories_to_remove.append(nfs_files_dir)
        # Remove symnlink to files
        symlinks_to_remove.append(instance_code_path + '/sites/default/files')
    # If the settings file exists, change permissions to allow us to delete the file.
    file_destination = "{0}/{1}/{1}/sites/default/settings.php".format(
        INSTANCE_ROOT, instance['sid'])
    # Check to see if file exists and is writable.
    utilities.file_accessable_and_writable(file_destination)
    # Remove symlinks
    for symlink in symlinks_to_remove:
        if os.path.islink(symlink):
            log.debug('Instance | Delete | Symlink - %s', symlink)
            os.remove(symlink)
    # Remove directories
    for directory in directories_to_remove:
        # Check if it exists
        if os.access(directory, os.F_OK):
            rmtree(directory)


def switch_core(instance):
    """Switch Drupal core symlinks, if no core symlinks are present add them.

    Arguments:
        instance {dict} -- full instance record
    """
    # Lookup the core we want to use.
    core = utilities.get_single_eve('code', instance['code']['core'])
    # Setup variables
    core_path = utilities.code_path(core)
    instance_code_path_sid = '{0}/{1}/{1}'.format(INSTANCE_ROOT, instance['sid'])
    # Get a list of files in the Core source directory
    core_files = os.listdir(core_path)
    # Get a list of files in the Instance target directory
    instance_files = os.listdir(instance_code_path_sid)
    # Remove any existing symlinks to a core.
    for instance_file in instance_files:
        full_path = instance_code_path_sid + '/' + instance_file
        # Check if path is a symlink.
        if os.path.islink(full_path):
            # Get the target of the symlink.
            symlink_target = os.readlink(full_path)
            # Get the name of the directory that contains the symlink target
            code_dir = os.path.dirname(symlink_target)
            # Check to see if the directory is a Drupal core, if so remove the symlink.
            regex = '((drupal)\-([\d\.x]+\-*[dev|alph|beta|rc|pl]*[\d]*))$i'
            if re.match(regex, code_dir):
                os.remove(full_path)
    # Iterate through the source files and symlink when applicable.
    for core_file in core_files:
        if core_file in ['sites', 'profiles']:
            continue
        if utilities.ignore_code_file(core_file):
            continue
        source_path = core_path + '/' + core_file
        destination_path = instance_code_path_sid + '/' + core_file
        # Remove existing symlink and add new one.
        if os.path.islink(destination_path):
            os.remove(destination_path)
            # F_OK to test the existence of path
        if not os.access(destination_path, os.F_OK):
            utilities.relative_symlink(source_path, destination_path)
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
        # If the directoey does not already exist, create it.
        if not os.access(target_dir, os.F_OK):
            os.mkdir(target_dir)
    # Copy over default settings file so that this instance is like a default install.
    source_path = core_path + '/sites/default/default.settings.php'
    destination_path = instance_code_path_sid + '/sites/default/default.settings.php'
    if os.access(destination_path, os.F_OK):
        os.remove(destination_path)
    copyfile(source_path, destination_path)
    # Include links to the profiles that we are not using so that the site doesn't white screen if
    # the deployed profile gets disabled.
    core_profiles = os.listdir(core_path + '/profiles')
    for core_profile in core_profiles:
        source_path = core_path + '/profiles/' + core_profile
        destination_path = instance_code_path_sid + '/profiles/' + core_profile
        if os.path.islink(destination_path):
            os.remove(destination_path)
            # F_OK to test the existence of path
        if not os.access(destination_path, os.F_OK):
            utilities.relative_symlink(source_path, destination_path)


def switch_profile(instance):
    """Switch non-core Profile symlinks, if no appropriate symlinks are present add them.

    Arguments:
        instance {dict} -- full instance record
    """
    log.info('Instance | Switch profile | Instance - %s', instance['sid'])
    log.debug('Instance | Switch profile | Instance - %s', instance)
    # Lookup the profile we want to use.
    profile = utilities.get_single_eve('code', instance['code']['profile'])
    # Setup variables
    profile_path = utilities.code_path(profile)
    instance_code_path_sid = '{0}/{1}/{1}'.format(INSTANCE_ROOT, instance['sid'])
    destination_path = instance_code_path_sid + '/profiles/' + profile['meta']['name']
    # Remove old symlink
    if os.path.islink(destination_path):
        os.remove(destination_path)
    # Add new relative symlink
    if not os.access(destination_path, os.F_OK):
        utilities.relative_symlink(profile_path, destination_path)


def switch_packages(instance):
    """Switch Package symlinks, if no package symlinks are present add them.

    Arguments:
        instance {dict} -- full instance record
    """
    log.info('Instance | Switch package | Instance - %s', instance['sid'])
    log.debug('Instance | Switch package | Instance - %s', instance)
    instance_code_path_sid = '{0}/{1}/{1}'.format(INSTANCE_ROOT, instance['sid'])
    # Get rid of old symlinks
    # List sites/all/{modules|themes|libraries} and remove all symlinks
    for package_type_path in ['modules', 'themes', 'libraries']:
        package_path = instance_code_path_sid + '/sites/all/' + package_type_path
        log.debug('Instance | Switch Packages | listdir - %s', os.listdir(package_path))
        for item in os.listdir(package_path):
            # Get full path of item
            path = package_path + '/' + item
            log.debug('Instance | Switch Packages | Item to unlink - %s', path)
            if os.path.islink(path):
                os.remove(path)
    if 'package' in instance['code']:
        for item in instance['code']['package']:
            package = utilities.get_single_eve('code', item)
            package_path = utilities.code_path(package)
            package_type_path = utilities.code_type_directory_name(package['meta']['code_type'])
            destination_path = instance_code_path_sid + '/sites/all/' + \
                package_type_path + '/' + package['meta']['name']
            # Add new relative symlink
            if not os.access(destination_path, os.F_OK):
                utilities.relative_symlink(package_path, destination_path)


def switch_settings_files(instance):
    """Create settings.php from template and render the resulting file onto the server.

    Arguments:
        instance {dict} -- full instance record
    """
    log.info('Instance | Settings file | Instance ID - %s', instance['_id'])

    # If the settings file exists, change permissions to allow us to update the template.
    file_destination = "{0}/{1}/{1}/sites/default/settings.php".format(
        INSTANCE_ROOT, instance['sid'])
    # Check to see if file exists and is writable.
    utilities.file_accessable_and_writable(file_destination)

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

    if NFS_MOUNT_FILES_DIR:
        tmp_path = '{0}/{1}/tmp'.format(NFS_MOUNT_LOCATION[ENVIRONMENT], instance['sid'])
    else:
        tmp_path = '/tmp'

    if 'google_tag_client_container_id' in instance['settings']:
        google_tag_client_container_id = instance['settings']['google_tag_client_container_id']
    else:
        google_tag_client_container_id = None

    domain = BASE_URLS[ENVIRONMENT].split('://')[1]

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
        'google_tag_client_container_id': google_tag_client_container_id,
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
        'base_url': BASE_URLS[ENVIRONMENT],
        'domain': domain,
        'servicenow_key': SERVICENOW_KEY
    }

    log.info('Instance | Settings file | Render settings file | Instance ID - %s', instance['_id'])
    # Create a template environment with the default settings and a loader that looks up the
    # templates in the templates folder inside the Atlas python package.
    # We don't do autoescaping, because there is no PHP support.
    jinja_env = Environment(loader=PackageLoader('atlas', 'templates'))
    template = jinja_env.get_template('settings.php')
    render = template.render(settings_variables)
    # Remove the existing file.
    if os.access(file_destination, os.F_OK):
        os.remove(file_destination)
    # Write the render to a file.
    with open(file_destination, "wb") as open_file:
        open_file.write(render)
    # Set file permissions
    # Octet mode, Python 3 compatible
    os.chmod(file_destination, 0o444)


def correct_fs_permissions(instance):
    """Apply the correct permissions to code and NFS files, directories, and symlinks.

    Arguments:
        instance {dict} -- instance object
    """
    log.info('Instance | Correct File permissions | Instance - %s', instance['sid'])
    instance_path = "{0}/{1}/{1}".format(INSTANCE_ROOT, instance['sid'])
    # Walk produces 3-tuple for each dir or file, does not follow symlinks.
    # Lookup gid (Group ID), `chown` uses IDs for user and group
    group = getgrnam(WEBSERVER_USER_GROUP)
    log.debug('Instance | Correct FS permissions | Group - %s', group)
    # `os.walk` does not follow symlinks by default.
    for root, directories, files in os.walk(instance_path, topdown=False):
        # Change directory permissions.
        for directory in [os.path.join(root, d) for d in directories]:
            # Do not need to update perms on symlinks
            if not os.path.islink(directory):
                if re.search('sites\/default$', directory, re.MULTILINE):
                    # Octet mode, Python 3 compatible
                    os.chmod(directory, 0o755)
                else:
                    os.chmod(directory, 0o775)
                # All the arguments to fchown are integers. Integer 'file descriptor' that
                # is used by the underlying implementation to request I/O operations from
                # the operating system; user id (uid), -1 to leave it unchanged; group id
                # (gid).
                log.debug('path %s | gid %s', directory, group.gr_gid)
                os.chown(directory, -1, group.gr_gid)
        # Change file permissions.
        for file in [os.path.join(root, f) for f in files]:
            log.debug('Instance | Correcy FS perms | File | File name - %s', file)
            # Use search instead of match b/c we want end of string, not exact string, silly dev.
            if re.search('settings\.php$', file, re.MULTILINE):
                # Octet mode, Python 3 compatible
                os.chmod(file, 0o444)
                log.debug('Instance | Correcy FS perms | File | File name - %s | 444', file)
            else:
                os.chmod(file, 0o664)
                log.debug('Instance | Correcy FS perms | File | File name - %s | 664', file)
            os.chown(file, -1, group.gr_gid)
    if NFS_MOUNT_FILES_DIR:
        nfs_files_dir = '{0}/{1}'.format(NFS_MOUNT_LOCATION[ENVIRONMENT], instance['sid'])
        # Files and directories all owned by Apache
        # Diretories have setgid on them
        log.debug('Instance | Correct NFS permissions | Group - %s', group)
        for root, directories, files in os.walk(nfs_files_dir, topdown=False):
            for directory in [os.path.join(root, d) for d in directories]:
                # Do not need to update perms on symlinks
                # Check if we own the file, don't try to change the perms if we don't
                # TODO Remove ownership check when the umask is in place.
                if not os.path.islink(directory):
                    # Octet mode, Python 3 compatible
                    # Include SetGID for directory
                    os.chmod(directory, 02775)
                    if not ENVIRONMENT == 'local' and getpwuid(os.stat(directory).st_uid).pw_name == SSH_USER:
                        os.chown(directory, -1, group.gr_gid)
            for file in [os.path.join(root, f) for f in files]:
                # Check if we own the file, don't try to change the perms if we don't
                # TODO Remove ownership check when the umask is in place.
                os.chmod(file, 0o664)
                if not ENVIRONMENT == 'local' and getpwuid(os.stat(file).st_uid).pw_name == SSH_USER:
                    # Octet mode, Python 3 compatible
                    os.chown(file, -1, group.gr_gid)


def sync_instances(sid=None):
    """Copy the instance files to all of the relevant nodes.

    Keyword Arguments:
        sid {string} -- p1 sid for an instance (default: {None})
    """

    log.info('Instances | Sync | id - %s', sid)
    hosts = SERVERDEFS[ENVIRONMENT]['webservers'] + SERVERDEFS[ENVIRONMENT]['operations_server']
    # Sync INSTANCE_ROOT then WEB_ROOT
    if sid:
        sid_local_instance_root = INSTANCE_ROOT + '/' + sid
        sid_instance_root = INSTANCE_ROOT + '/' + sid
        utilities.sync(sid_local_instance_root, hosts, sid_instance_root, exclude='opcache')
    else:
        utilities.sync(INSTANCE_ROOT, hosts, INSTANCE_ROOT, exclude='opcache')
    sync_web_root()


def sync_web_root():
    """Copy web root symlinks and directories to the relevant nodes.
    """
    log.info('Instances | Sync | Web root')
    hosts = SERVERDEFS[ENVIRONMENT]['webservers'] + SERVERDEFS[ENVIRONMENT]['operations_server']
    utilities.sync(WEB_ROOT, hosts, WEB_ROOT, exclude='opcache')


def switch_web_root_symlinks(instance):
    """Create symlinks in web root

    Arguments:
        instance {dict} -- instance object
    """
    log.info('Instances | Launch | Instance - %s', instance['_id'])
    instance_code_path_current = '{0}/{1}/current'.format(INSTANCE_ROOT, instance['sid'])

    if instance['type'] == 'express':
        if instance['path'] != 'homepage':
            web_directory_path = '{0}/{1}'.format(WEB_ROOT, instance['path'])
            web_directory_sid = '{0}/{1}'.format(WEB_ROOT, instance['sid'])
            # If the instance has a multipart path
            if "/" in instance['path']:
                # Setup a base path, all items in 'path' except for the last one
                base_path = WEB_ROOT + '/' + '/'.join(instance['path'].split('/')[:-1])
                log.debug('Instance | Web root symlinks | base_path - %s', base_path)
                # Check to see if directory exists and create it if it does not.
                if not os.access(base_path, os.F_OK):
                    os.makedirs(base_path)
            # Remove symlinks if they exists
            if os.path.islink(web_directory_path):
                log.debug('Instance | Web root symlinks | Remove old path')
                os.remove(web_directory_path)
            if os.path.islink(web_directory_sid):
                log.debug('Instance | Web root symlinks | Remove old sid')
                os.remove(web_directory_sid)
            # If the instance is being taken down, change target for symlink
            if instance['status'] not in ['take_down', 'down']:
                utilities.relative_symlink(instance_code_path_current, web_directory_sid)
                if instance['path'] != instance['sid']:
                    utilities.relative_symlink(
                        instance_code_path_current, web_directory_path)
        elif instance['path'] == 'homepage':
            for link in CORE_WEB_ROOT_SYMLINKS:
                source_path = "{0}/{1}".format(instance_code_path_current, link)
                target_path = "{0}/{1}".format(WEB_ROOT, link)
                if os.access(target_path, os.F_OK) and os.path.islink(target_path):
                    os.remove(target_path)
                utilities.relative_symlink(source_path, target_path)


def switch_homepage_files():
    """Replace robots.txt and .htaccess for the homepage
    """
    files = [tuple([ATLAS_LOCATION + '/files/homepage_robots', WEB_ROOT + '/robots.txt']),
             tuple([ATLAS_LOCATION + '/files/homepage_htaccess', WEB_ROOT + '/.htaccess'])]
    for file in files:
        if os.access(file[1], os.F_OK):
            os.remove(file[1])
        copyfile(file[0], file[1])
