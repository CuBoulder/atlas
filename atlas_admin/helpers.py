import re

from operator import itemgetter
from collections import Counter, OrderedDict
from flask import request
from eve.methods.get import getitem_internal, get_internal


def availableInstances():
    """Get a list of available instances and display them with links to invitation pages
    """
    availableInstances = get_internal('sites', **{"status": "available"})
    availableInstancesSidList = []
    if availableInstances and availableInstances[4]:
        for header in availableInstances[4]:
            if header and header[0] == 'X-Total-Count' and header[1] > 0:
                for item in availableInstances[0]['_items']:
                    availableInstancesSidList.append(item['sid'])
    else:
        availableInstancesSidList = None

    return availableInstancesSidList


def summaryInstances():
    """Return a list of summary statistics about instances
        Instance Count
          Total - Done
          by state - Done
          with bundles - To Do
    """

    summary = {}
    results, totalItems = getAllResults(atlasType='sites')

    if results:
        statusCount = Counter()
        typeCount = Counter()
        pantheonCount = Counter()
        # Count totals by status
        for res in results:
            if 'status' in res:
                 statusCount[res['status']] += 1
            if 'site_type' in res:
                typeCount[res['site_type']] += 1
            if 'pantheon_size' in res:
                pantheonCount[res['pantheon_size']] += 1
        summary['total'] = totalItems
        summary['status'] = OrderedDict(sorted(dict(statusCount).items()))
        summary['site_type'] = OrderedDict(sorted(dict(typeCount).items()))
        summary['pantheon_size'] = OrderedDict(sorted(dict(pantheonCount).items()))
    else:
        summary = None

    return summary


def instanceSummary(instance):
    instanceSummary = {}

    # Get site record
    q = get_internal('sites', **{"_id": instance})
    instances = q[0].get('_items', None)
    instanceSummary['instance'] = instances[0]
    # Get statistics record
    s = get_internal('statistics', **{"_id": instanceSummary['instance']['statistics']})
    statistics = s[0].get('_items', None)
    instanceSummary['statistics'] = statistics[0]

    return instanceSummary


def instances(siteType=None, pantheonSize=None, path=None, siteStatus=None, cse=False):
    if siteType:
        findThisElement = {"site_type": siteType}
    elif pantheonSize:
        findThisElement = {"pantheon_size": pantheonSize}
    elif siteStatus:
        findThisElement = {"status": siteStatus}
    elif path:
        findThisElement = {"path": {"$regex": path}}
    elif cse:
        findThisElement = {"settings.cse_id": {"$exists": True}}

    results, totalItems = getAllResults(atlasType='sites', **findThisElement)
    # Get list of all instances
    instanceList = []
    for r in results:
        if siteType or siteStatus:
            instanceList.append((r['_id'], r['path'], r.get('pantheon_size', 'no size')))
        elif pantheonSize or path:
            instanceList.append((r['_id'], r['path'], r.get('site_type', 'no type')))
        elif cse:
            instanceList.append(
                (r['_id'], r['path'], r['settings']['cse_id'], r['settings']['cse_creator']))

    return instanceList


def instancesUserLookup(query=None, query_type=None):
    """
    Return a list of sites to which the requested user belongs
    Display on  /search
    """

    if query_type == 'username':
        kwargs = {"$or": [{"users.username.site_owner": {"$regex": query, "$options": "i"}}, {"users.username.site_editor": {"$regex": query, "$options": "i"}}, {"users.username.form_manager": {"$regex": query, "$options": "i"}}, {"users.username.edit_my_content": {"$regex": query, "$options": "i"}}, {
            "users.username.content_editor": {"$regex": query, "$options": "i"}}, {"users.username.configuration_manager": {"$regex": query, "$options": "i"}}, {"users.username.campaign_manager": {"$regex": query, "$options": "i"}}, {"users.username.access_manager": {"$regex": query, "$options": "i"}}]}
    elif query_type == 'email_address':
        # Handle mixed case in email addresses
        kwargs = {"$or": [{"users.email_address.site_owner": {"$regex": query, "$options": "i"}}, {"users.email_address.site_editor": {"$regex": query, "$options": "i"}}, {"users.email_address.form_manager": {"$regex": query, "$options": "i"}}, {"users.email_address.edit_my_content": {"$regex": query, "$options": "i"}}, {
            "users.email_address.content_editor": {"$regex": query, "$options": "i"}}, {"users.email_address.configuration_manager": {"$regex": query, "$options": "i"}}, {"users.email_address.campaign_manager": {"$regex": query, "$options": "i"}}, {"users.email_address.access_manager": {"$regex": query, "$options": "i"}}]}

    results, totalItems = getAllResults(atlasType='statistics', **kwargs)

    # Get list of all instances
    instanceList = []
    for r in results:
        instance = get_internal(
            'sites', **{"_id": r['site']})[0]['_items'][0]
        for role, user in r['users'][query_type].iteritems():
            # Handle mixed case in email addresses
            if query.lower() in lowerList(user):
                instanceList.append((instance['_id'], instance['path'], role))

    return instanceList


def summaryUsers():
    """Return a list of summary statistics about users to display on home page '/'
    """
    summary = {}
    results, totalItems = getAllResults(atlasType='statistics')
    # Sum totals by role
    for res in results:
        if 'users' in res:
            for k, v in res['users']['counts'].iteritems():
                if k in summary:
                    summary[k] += v
                else:
                    summary[k] = v
    summary['total'] = len(users()[0])

    sortedUsers = OrderedDict(sorted(summary.items())) if summary else None

    return sortedUsers


def users(role=None):
    """
    Return a list of user names and email addresses
    Display on /users and users/<role>
    """
    results, totalItems = getAllResults(atlasType='statistics')

    # Get list of all users
    userNameList = []
    userEmailList = []
    for r in results:
        if r.get('users'):
            for k, v in r['users']['username'].items():
                if role:
                    if k == role:
                        userNameList += v
                else:
                    userNameList += v
            for k, v in r['users']['email_address'].items():
                if role:
                    if k == role:
                        userEmailList += v
                else:
                    userEmailList += v

    # Get de-duped and sorted lists
    uniqueUserNameList = sorted(uniqueList(userNameList), key=str.lower)
    uniqueUserEmailList = sorted(uniqueList(userEmailList), key=str.lower)

    return (uniqueUserNameList, uniqueUserEmailList)


def userInstanceLookup(instanceList):
    """Get a list of users and roles given a list of instances
    for display on /user/search
    Arguments:
        instanceList {list}
    """

    findThisElement = {"site": {"$in": instanceList}}
    results, totalItems = getAllResults(atlasType='statistics', **findThisElement)

    userNameList = []
    for r in results:
        if r.get('users'):
            for k, v in r['users']['username'].items():
                for username in v:
                    userNameList.append((username, k))
    # Sort the list of tuples by role
    uniqueUserNameList = sorted(uniqueTupleList(userNameList), key=itemgetter(1))

    return uniqueUserNameList


def getAllResults(atlasType, **findThisElement):
    """
    Returns a complete list of site statistics
    """

    results = []

    q = get_internal(atlasType, **findThisElement)
    res = q[0] if len(q) > 0 else {}
    totalItems = res.get('_meta', None).get('total', None)
    if totalItems:
        # If more items exist than initial request, reset max_results to total to get a full export
        if totalItems > res.get('_meta', None).get('max_results', None):
            # Copy the existing arguments on the request object
            setArgs = request.args.copy()
            # Set our new header
            setArgs['max_results'] = totalItems
            request.args = setArgs
            results = get_internal(atlasType, **findThisElement)[0]['_items']
        else:
            results = res.get('_items', None)

    return results, totalItems


def summaryStatistics():
    # TODO drupal_system_status
    summary = {
        'nodes_total': 0,
        'beans_total': 0,
        'single_node_instances': 0,
    }
    responsive_total = 0
    days_total = 0

    results, totalItems = getAllResults(atlasType='statistics')

    for r in results:
        summary['nodes_total'] += r.get('nodes_total', 0)
        if r.get('nodes_total') and int(r['nodes_total']) == 1:
            summary['single_node_instances'] += 1
        summary['beans_total'] += r.get('beans_total', 0)
        days_total += r.get('days_since_last_edit', 0)
        if r.get('theme_is_responsive', False):
            responsive_total += 1

    summary['percent_responsive'] = "{0:.2f}%".format(
        (float(responsive_total)/totalItems)*100) if responsive_total is not 0 else "N/A"
    summary['nodes_avg'] = int(summary['nodes_total'] /
                               totalItems) if summary['nodes_total'] is not 0 else "N/A"
    summary['beans_avg'] = int(summary['beans_total'] /
                               totalItems) if summary['beans_total'] is not 0 else "N/A"
    summary['avg_days_since_edit'] = int(days_total/totalItems) if days_total is not 0 else "N/A"

    summary['nodes_total'] = "{:,}".format(summary['nodes_total'])
    summary['beans_total'] = "{:,}".format(summary['beans_total'])

    return OrderedDict(sorted(summary.items()))


def uniqueList(li):
    newList = []
    for x in li:
        if x not in newList:
            newList.append(str(x))
    return newList


def uniqueTupleList(li):
    newList = []
    for x in li:
        if x not in newList:
            newList.append(x)
    return newList


def lowerList(mixedList):
    return [x.lower() for x in mixedList]


def statBreakdown():
    """
    Returns all site statistics
    Displays on /instances using instances/summary.html
    Displays on /instances/stats using instances/statlist.html
    """

    summary = {}
    results, totalItems = getAllResults(atlasType='statistics')

    if results:
        otherNodeTypes = ["collection_item", "class_note", "homepage_callout", "issue", "newsletter", "people_list_page", "section_page"]
        themeCount = Counter()
        nodeCount = Counter()
        otherNodesCount = Counter()
        for res in results:
            if 'variable_theme_default' in res:
                themeCount[res['variable_theme_default']] += 1
            if 'nodes_by_type' in res:
                for k, v in res["nodes_by_type"].items():
                    nodeCount[k] += v
            if "nodes_other" in res:
                for nodeType in otherNodeTypes:
                    if nodeType in res["nodes_other"]:
                        otherNodesCount[nodeType] += 1
        themeList = dict(themeCount)
        sortedThemeList = sorted(themeList.items(), key=lambda x: x[1])
        summary['variable_theme_default'] = OrderedDict(sortedThemeList)
        summary['nodes_by_type'] = OrderedDict(sorted(dict(nodeCount).items()))
        summary['nodes_other'] = OrderedDict(sorted(dict(otherNodesCount).items()))
    else:
        summary = None

    return summary


def sitesByStat(themeName=None):
    """
    Return a list of sites with the requested statistic
    Displays on individual Stat List page /instances/th/<themeName> using instances/sitestats.html
    """
    if themeName:
        findThisElement = {"variable_theme_default": themeName}

    results, totalItems = getAllResults(atlasType='statistics', **findThisElement)

    # Get list of all instances
    unsortedList = []
    instanceList = []
    for r in results:
        unsortedList.append((r['site'], r['name'], r['users']['username']['site_owner']))
        instanceList = sorted(unsortedList, key=lambda x: x[1])
    return instanceList


def sitesByNode(nodeType=None):
    """return a list of nodes by type
    """

    results, totalItems = getAllResults(atlasType='statistics')

    unsortedList = []
    instanceList = []
    for r in results:
        if "nodes_by_type" in r:
            for k, v in r["nodes_by_type"].items():
                if k == nodeType:
                    unsortedList.append((r['site'], r['name'], r['users']['username']['site_owner']))

    instanceList = sorted(unsortedList, key=lambda x: x[1])
    return instanceList


def sitesByOtherNode(nodeType=None):
    """return a list of nodes by type
    """

    results, totalItems = getAllResults(atlasType='statistics')

    unsortedList = []
    instanceList = []
    for r in results:
        if "nodes_other" in r:
            if nodeType in r["nodes_other"]:
                    unsortedList.append((r["site"], r["name"], ['Catherine Snider', 'Jim Bohannon', 'John Borton']))

    instanceList = sorted(unsortedList, key=lambda x: x[1])
    return instanceList
