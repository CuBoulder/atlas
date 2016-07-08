"""
Fabric Commands

Commands that run on servers to do the actual work.
"""
import sys
import requests
import re

from fabric.contrib.files import append, exists, sed
from fabric.api import *
from jinja2 import Environment, PackageLoader
from random import randint
from time import time
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
    if item['meta']['code_type'] == 'library':
        code_type_dir = 'libraries'
    else:
        code_type_dir = item['meta']['code_type'] + 's'
    code_folder = '{0}/{1}/{2}/{2}-{3}'.format(code_root, code_type_dir, item['meta']['name'], item['meta']['version'])
    _create_directory_structure(code_folder)
    _clone_repo(item["git_url"], item["commit_hash"], code_folder)
    if item['meta']['is_current']:
        code_folder_current = '{0}/{1}/{2}/{2}-current'.format(code_root, code_type_dir, item['meta']['name'])
        _update_symlink(code_folder, code_folder_current)


@roles('webservers')
def code_update(item):
    """
    Responds to PATCHes to update code in the right places on the server.

    :param item:
    :return:
    """
    if item['meta']['code_type'] == 'library':
        code_type_dir = 'libraries'
    else:
        code_type_dir = item['meta']['code_type'] + 's'
    code_folder = '{0}/{1}/{2}/{2}-{3}'.format(code_root, code_type_dir, item['meta']['name'], item['meta']['version'])
    _checkout_repo(item["commit_hash"], code_folder)
    if item['meta']['is_current']:
        code_folder_current = '{0}/{1}/{2}/{2}-current'.format(code_root, code_type_dir, item['meta']['name'])
        _update_symlink(code_folder,code_folder_current)


@roles('webservers')
def code_remove(item):
    """
    Responds to DELETEs to remove code from the server.

    :param item: Item to remove
    :return:
    """
    if item['meta']['code_type'] == 'library':
        code_type_dir = 'libraries'
    else:
        code_type_dir = item['meta']['code_type'] + 's'
    code_folder = '{0}/{1}/{2}/{2}-{3}'.format(code_root, code_type_dir, item['meta']['name'], item['meta']['version'])
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
    profile = utilities.get_single_eve('code', site['code']['profile'])
    profile_name = profile['meta']['name']

    _create_database(site)

    _create_settings_files(site, profile_name)

    _create_directory_structure(code_directory)

    with cd(code_directory):
        # TODO: Get core from site object.
        core = utilities.get_single_eve('code', site['code']['core'])
        core_name = core['meta']['name']
        core_version = core['meta']['version']
        core_complete = '{0}-{1}'.format(core_name, core_version)
        run('drush dslm-new {0} {1}'.format(site['sid'], core_complete))

    _update_symlink(code_directory_sid, code_directory_current)

    with cd(code_directory_current):
        # TODO: Get profile from site object.
        profile_version = profile['meta']['version']
        profile_complete = '{0}-{1}'.format(profile_name, profile_version)
        run('drush dslm-add-profile {0}'.format(profile_complete))

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
@roles('webservers')
def site_launch(site):
    print('Site Launch\n{0}'.format(site))
    code_directory = '{0}/{1}'.format(sites_code_root, site['sid'])
    code_directory_current = '{0}/current'.format(code_directory)
    profile = utilities.get_single_eve('code', site['code']['profile'])
    profile_name = profile['meta']['name']

    _create_settings_files(site, profile_name)
    _push_settings_files(site, code_directory_current)

    if environment is 'prod' and site['pool'] is 'poolb-express':
        # Create GSA collection if needed.
        gsa_task = _create_gsa(site)
        if gsa_task is True:
            print ('GSA Collection - Success')
            _launch_site(site=site, gsa_collection=machine_name)
            return
        else:
            print ('GSA Collection - Failed')
            _launch_site(site=site)
    else:
        _launch_site(site=site)

    if environment is not 'local':
        _diff_f5()
        _update_f5()


@roles('webservers')
def site_take_down(site):
    """
    Point the site to the 'Down' page.
    """
    print('Site Take down\n{0}'.format(site))
    code_directory_current = '{0}/{1}/current'.format(sites_code_root, site['sid'])
    _update_symlink(site_down_path, code_directory_current)


@roles('webservers')
def site_restore(site):
    """
    Point the site to the current release.
    """
    code_directory_current = '{0}/{1}/current'.format(sites_code_root, site['sid'])
    code_directory_sid = '{0}/{1}/{1}'.format(sites_code_root, site['sid'])
    _update_symlink(code_directory_sid, code_directory_current)
    with cd(code_directory_current):
        # Run updates
        action_0 = run("drush updb -y")
        action_1 = run("drush vset inactive_30_email FALSE; drush vset inactive_55_email FALSE; drush vset inactive_60_email FALSE;")
        # TODO: See if this works as intended.
        if action_0.failed:
            return task
        elif action_1.failed:
            return task


def correct_file_directory_permissions(site):
    code_directory_sid = '{0}/{1}/{1}'.format(sites_code_root, site['sid'])
    with cd(code_directory_sid):
        run('chgrp -R lapurd sites/default'.format(ssh_user_group))
        run('chgrp -R apache sites/default/files'.format(webserver_user_group))
        run('chmod -R 775 sites/default')


def clear_apc():
    run("wget -q -O - http://localhost/sysadmintools/apc/clearapc.php")

def drush_cache_clear(sid):
    code_directory_current = '{0}/{1}/current'.format(sites_code_root, sid)
    with cd(code_directory_current):
        run("drush cc all")

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
        run('git clean -f -f -d')


def _checkout_repo(checkout_item, destination):
    print('Checkout Repo: {0}\n Checkout: {1}'.format(destination, checkout_item))
    with cd(destination):
        run('git reset --hard')
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
    headers = {"Content-Type":"application/atom+xml", "Authorization":"GoogleLogin auth={0}".format(auth_token)}
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


def _gsa_auth():
    """
    Gets an auth token from the GSA.
    """
    url = "https://{0}:8443/accounts/ClientLogin".format(gsa_host)
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    r = requests.post(url, data="&Email={0}&Passwd={1}".format(gsa_username,gsa_password), headers=headers, verify=False)
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
    headers = {"Content-Type":"application/atom+xml", "Authorization":"GoogleLogin auth={0}".format(auth_token)}
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
        #id = entry[entry.find("<id>")+4:entry.find("</id>")]
        needle = "<gsa:content name='entryID'>"
        start = entry.find(needle) + len(needle)
        name = entry[start:entry.find("</gsa:content>", start)]
        needle = "<gsa:content name='followURLs'>"
        start = entry.find(needle) + len(needle)
        follow = entry[start:entry.find("</gsa:content>", start)]
        follow = follow.split("\\n")
        collections[name] = follow

    return collections

def _launch_site(site, pool='poolb-express', gsa_collection=False):
    """
    Create symlinks with new site name.
    """
    code_directory = '{0}/{1}'.format(sites_code_root, site['sid'])
    code_directory_current = '{0}/current'.format(code_directory)

    if pool in ['poolb-express', 'poolb-homepage']:
        if pool == 'poolb-express':
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
                    # Clear caches at the end of the launch process to show correct
                    # pathologic rendered URLS.
                    drush_cache_clear(site['sid'])
            # Assign it to an update group.
            update_group = randint(0, 10)
        if pool == 'poolb-homepage':
            web_directory = '{0}/{1}'.format(sites_web_root, site['type'])
            with cd(sites_web_root):
                _update_symlink(code_directory_current, web_directory)
                # enter new site directory
            with cd(web_directory):
                clear_apc()
                drush_cache_clear(site['sid'])
            # Update site document to show the site has launched and assign it to update group 12.
            update_group = 12
        payload = {'status': 'launched', 'update_group': update_group}
        utilities.patch_eve('sites', site['_id'], payload)


def _diff_f5():
    """
    Copy f5 configuration file to local sever, parse txt and create or update
    site items.

    """
    f5_config_dir = '{0}/atlas/fabfile'.format(path)
    f5_config_file = '{0}/{1}'.format(f5_config_dir,f5_config_files[environment])
    # If an older config file exists, copy it to a backup folder.
    if os.path.isfile(f5_config_file):
        local( 'mv {0} /data/code/inventory/fabfile/backup/{1}.{2}'.format(f5_config_file, f5_config_files[environment], str(time()).split('.')[0]))
    # Copy config file from the f5 server to the Atlas server.
    local('scp {0}:/config/{1} {2}/'.format(serverdefs[environment]['f5_servers'][0], f5_config_files[environment], f5_config_dir))

    # Open file from f5
    with open(f5_config_file, "r") as ifile:
        data = ifile.read()
    # Use regex to parse out path values
    p = re.compile('"(.+/?)" := "(\w+(-\w+)?)",')
    sites = p.findall(data)
    # Iterate through sites found in f5 data
    for site in sites:
        f5only = False
        if site[0] in f5exceptions:
            f5only = True
        # Get path without leading slash
        path = site[0][1:]
        pool = site[1]
        # Set a type value based on pool
        if pool == 'WWWLegacy':
            type = 'legacy'
        elif pool == 'poola-homepage' or pool == 'poolb-homepage':
            type = 'homepage'
        elif pool == 'poolb-express':
            type = 'express'
        else:
            type = 'custom'

        site_query = 'where={{"path":"{0}"}}'.format(path)
        sites = utilities.get_eve('sites', site_query)

        if not sites or len(sites['_items']) == 0:
            payload = {
                "name": path,
                "path": path,
                "pool": pool,
                "status": "launched",
                "type": type,
                "f5only": f5only,
            }
            utilities.post_eve('sites', payload)
            print 'Created site record based on f5.\n{0}'.format(payload)
        elif pool != data['_items'][0]['pool']:
            site = data['_items'][0]
            payload = {
                "pool": pool,
                "status": "launched",
                "type": type,
            }
            utilities.patch_eve('sites', site['_id'], payload)
            print 'Updated site based on f5.\n{0}'.format(payload)


def _update_f5():
    # Like 'WWWNGProdDataGroup.dat'
    old_file_name = f5_config_file[environment]
    # Like 'WWWNGDevDataGroup.dat.1402433484.bac'
    new_file_name = "{0}.{1}.bac".format(f5_config_file[environment], str(time()).split('.')[0])
    f5_config_dir = '{0}/atlas/fabfile'.format(path)
    sites = get_eve('sites', 'max_results=3000')

    # TODO: delete old backups

    # Write data to file
    with open("{0}/{1}".format(f5_config_dir, f5_config_file[environment]), "w") as ofile:
        for site in sites['_items']:
            if 'path' in site:
                # If a site is down, skip to the next site
                if 'status' in site and site['status'] == 'down':
                    continue
                # In case a path was saved with a leading slash
                path = site["path"] if site["path"][0] == '/' else '/' + site["path"]
                # Ignore 'p1' paths but let the /p1 pattern through
                if not path.startswith("/p1") or len(path) == 3:
                    ofile.write('"{0}" := "{1}",\n'.format(path, site['pool']))

    execute(_exportf5, new_file_name=new_file_name, f5_config_dir=f5_config_dir)



@hosts('f5_servers')
def _exportf5(new_file_name, f5_config_dir):
    """
    Backup configuration file on f5 server, replace the active file, and reload
    the configuration.

    """
    # On an f5 server, backup the current configuration file.
    with cd("/config"):
        run("cp {0} {1}".format(f5_config_file[environment], new_file_name))
    # Copy the new configuration file to the server.
    put("{0}/{1}".format(f5_config_dir, f5_config_file[environment]), "/config")
    # Load the new configuration.
    with cd("/config"):
        run("b load;")

# Site Commands.
# Look at '@run_once' decorator to run things like DB cache clears once per Fabric run, instead of on each host.