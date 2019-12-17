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

    q = get_internal('sites')
    res = q[0] if len(q) > 0 else {}
    totalItems = res.get('_meta', None).get('total', None)

    summary = {}

    if totalItems:
        summary['total'] = totalItems

        # If more items exist than initial request, reset max_results to total to get a full export
        if totalItems > res.get('_meta', None).get('max_results', None):
            # Copy the existing arguments on the request object
            setArgs = request.args.copy()
            # Set our new header
            setArgs['max_results'] = totalItems
            request.args = setArgs
            results = get_internal('sites')[0]['_items']
        else:
            results = res.get('_items', None)

        statusCount = Counter()
        typeCount = Counter()
        pantheonCount = Counter()
        # Count totals by status
        for res in results:
            statusCount[res['status']] += 1
            if 'site_type' in res:
                typeCount[res['site_type']] += 1
            if 'pantheon_size' in res:
                pantheonCount[res['pantheon_size']] += 1
        summary['status'] = OrderedDict(sorted(dict(statusCount).items()))
        summary['site_type'] = OrderedDict(sorted(dict(typeCount).items()))
        summary['pantheon_size'] = OrderedDict(sorted(dict(pantheonCount).items()))
    else:
        summary = None


    qq = get_internal('statistics')
    resStat = qq[0] if len(qq) > 0 else {}
    totalStatItems = resStat.get('_meta', None).get('total', None)

    if totalStatItems:

        # If more items exist than initial request, reset max_results to total to get a full export
        if totalStatItems > resStat.get('_meta', None).get('max_results', None):
            # Copy the existing arguments on the request object
            setStatArgs = request2.args.copy()
            # Set our new header
            setStatArgs['max_results'] = totalItems
            request2.args = setStatArgs
            results2 = get_internal('statistics')[0]['_items']
        else:
            results2 = resStat.get('_items', None)

        themeCount = Counter()
        for res2 in results2:
            if 'variable_theme_default' in res2:
                themeCount[res2['variable_theme_default']] += 1
        summary['variable_theme_default'] = OrderedDict(sorted(dict(themeCount).items()))
        #summary['variable_theme_default'] = OrderedDict(sorted(dict(themeCount).items(), key=lambda x:x[1]))
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
        q = get_internal('sites', **{"site_type": siteType})
    elif pantheonSize:
        q = get_internal('sites', **{"pantheon_size": pantheonSize})
    elif siteStatus:
        q = get_internal('sites', **{"status": siteStatus})
    elif path:
        q = get_internal('sites', **{"path": {"$regex": path}})
    elif cse:
        q = get_internal('sites', **{"settings.cse_id": {"$exists": True}})
    else:
        q = get_internal('sites')
    res = q[0] if len(q) > 0 else {}
    totalItems = res.get('_meta', None).get('total', None)

    # If more items exist than initial request, reset max_results to total to get a full export
    if totalItems > res.get('_meta', None).get('max_results', None):
        setArgs = request.args.copy()
        setArgs['max_results'] = totalItems
        request.args = setArgs
        if siteType:
            qAll = get_internal('sites', **{"site_type": siteType})
        elif pantheonSize:
            qAll = get_internal('sites', **{"pantheon_size": pantheonSize})
        elif siteStatus:
            qAll = get_internal('sites', **{"status": siteStatus})
        elif path:
            qAll = get_internal('sites', **{"path": {"$regex": path}})
        elif cse:
            qAll = get_internal('sites', **{"settings.cse_id": {"$exists": 1}})
        else:
            qAll = get_internal('sites')
        results = qAll[0].get('_items', None)
    else:
        results = res.get('_items', None)
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
    if query_type == 'username':
        kwargs = {"$or": [{"users.username.site_owner": {"$regex": query, "$options": "i"}}, {"users.username.site_editor": {"$regex": query, "$options": "i"}}, {"users.username.form_manager": {"$regex": query, "$options": "i"}}, {"users.username.edit_my_content": {"$regex": query, "$options": "i"}}, {
            "users.username.content_editor": {"$regex": query, "$options": "i"}}, {"users.username.configuration_manager": {"$regex": query, "$options": "i"}}, {"users.username.campaign_manager": {"$regex": query, "$options": "i"}}, {"users.username.access_manager": {"$regex": query, "$options": "i"}}]}
    elif query_type == 'email_address':
        # Handle mixed case in email addresses
        kwargs = {"$or": [{"users.email_address.site_owner": {"$regex": query, "$options": "i"}}, {"users.email_address.site_editor": {"$regex": query, "$options": "i"}}, {"users.email_address.form_manager": {"$regex": query, "$options": "i"}}, {"users.email_address.edit_my_content": {"$regex": query, "$options": "i"}}, {
            "users.email_address.content_editor": {"$regex": query, "$options": "i"}}, {"users.email_address.configuration_manager": {"$regex": query, "$options": "i"}}, {"users.email_address.campaign_manager": {"$regex": query, "$options": "i"}}, {"users.email_address.access_manager": {"$regex": query, "$options": "i"}}]}
    q = get_internal('statistics', **kwargs)
    res = q[0] if len(q) > 0 else {}
    totalItems = res.get('_meta', None).get('total', None)

    # If more items exist than initial request, reset max_results to total to get a full export
    if totalItems > res.get('_meta', None).get('max_results', None):
        setArgs = request.args.copy()
        setArgs['max_results'] = totalItems
        request.args = setArgs
        qAll = get_internal('statistics', **kwargs)
        results = qAll[0].get('_items', None)
    else:
        results = res.get('_items', None)
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
    """Return a list of summary statistics about users
    """

    q = get_internal('statistics')
    res = q[0] if len(q) > 0 else {}
    totalItems = res.get('_meta', None).get('total', None)

    summary = {}

    if totalItems:
        # If more items exist than initial request, reset max_results to total to get a full export
        if totalItems > res.get('_meta', None).get('max_results', None):
            # Copy the existing arguments on the request object
            setArgs = request.args.copy()
            # Set our new header
            setArgs['max_results'] = totalItems
            request.args = setArgs
            results = get_internal('statistics')[0]['_items']
        else:
            results = res.get('_items', None)

        # Sum totals by role
        for res in results:
            if 'users' in res:
                for k, v in res['users']['counts'].iteritems():
                    if k in summary:
                        summary[k] += v
                    else:
                        summary[k] = v
        summary['total'] = len(users()[0])
    else:
        summary = {}

    sortedUsers = OrderedDict(sorted(summary.items())) if summary else None

    return sortedUsers


def users(role=None):
    """Return a list of user names and email addresses
    """
    q = get_internal('statistics')
    res = q[0] if len(q) > 0 else {}
    totalItems = res.get('_meta', None).get('total', None)

    # If more items exist than initial request, reset max_results to total to get a full export
    if totalItems > res.get('_meta', None).get('max_results', None):
        setArgs = request.args.copy()
        setArgs['max_results'] = totalItems
        request.args = setArgs
        qAll = get_internal('statistics')
        results = qAll[0].get('_items', None)
    else:
        results = res.get('_items', None)

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

    Arguments:
        instanceList {list}
    """
    q = get_internal('statistics', **{"site": {"$in": instanceList}})
    res = q[0] if len(q) > 0 else {}
    totalItems = res.get('_meta', None).get('total', None)

    # If more items exist than initial request, reset max_results to total to get a full export
    if totalItems > res.get('_meta', None).get('max_results', None):
        setArgs = request.args.copy()
        setArgs['max_results'] = totalItems
        request.args = setArgs
        qAll = get_internal('statistics', **{"site": {"$in": instanceList}})
        results = qAll[0].get('_items', None)
    else:
        results = res.get('_items', None)
    userNameList = []
    for r in results:
        if r.get('users'):
            for k, v in r['users']['username'].items():
                for username in v:
                    userNameList.append((username, k))
    # Sort the list of tuples by role
    uniqueUserNameList = sorted(uniqueTupleList(userNameList), key=itemgetter(1))

    return uniqueUserNameList


def summaryStatistics():
    # TODO drupal_system_status
    q = get_internal('statistics')
    res = q[0] if len(q) > 0 else {}
    totalItems = res.get('_meta', None).get('total', None)

    # If more items exist than initial request, reset max_results to total to get a full export
    if totalItems > res.get('_meta', None).get('max_results', None):
        setArgs = request.args.copy()
        setArgs['max_results'] = totalItems
        request.args = setArgs
        qAll = get_internal('statistics')
        results = qAll[0].get('_items', None)
    else:
        results = res.get('_items', None)

    summary = {
        'nodes_total': 0,
        'beans_total': 0,
        'single_node_instances': 0,
    }
    responsive_total = 0
    days_total = 0

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


def summaryThemes():
    """
    Return a list of theme statistics
    """

    q = get_internal('statistics')
    res = q[0] if len(q) > 0 else {}
    totalItems = res.get('_meta', None).get('total', None)

    summary = {}

    if totalItems:

        # If more items exist than initial request, reset max_results to total to get a full export
        if totalItems > res.get('_meta', None).get('max_results', None):
            # Copy the existing arguments on the request object
            setArgs = request.args.copy()
            # Set our new header
            setArgs['max_results'] = totalItems
            request.args = setArgs
            results = get_internal('statistics')[0]['_items']
        else:
            results = res.get('_items', None)

        themeCount = Counter()
        for res in results:
            if 'variable_theme_default' in res:
                themeCount[res['variable_theme_default']] += 1
        summary['variable_theme_default'] = OrderedDict(sorted(dict(themeCount).items(), key=lambda x:x[1]))
    else:
        summary = None

    return summary

def siteStats(themeName=None, nodeCount=None):
    if themeName:
        q = get_internal('statistics',  **{"variable_theme_default": themeName})
    elif nodeCount:
        q = get_internal('statistics',  **{"nodes_total": nodeCount})
    else:
        q = get_internal('statistics')
    res = q[0] if len(q) > 0 else {}
    totalItems = res.get('_meta', None).get('total', None)

    # If more items exist than initial request, reset max_results to total to get a full export
    if totalItems > res.get('_meta', None).get('max_results', None):
        setArgs = request.args.copy()
        setArgs['max_results'] = totalItems
        request.args = setArgs
        if themeName:
            qAll = get_internal('statistics',  **{"variable_theme_default": themeName})
        elif nodeCount:
            qAll = get_internal('statistics',  **{"nodes_total": nodeCount})
        else:
            qAll = get_internal('statistics')
        results = qAll[0].get('_items', None)
    else:
        results = res.get('_items', None)
    # Get list of all instances
    instanceList = []
    for r in results:
        if themeName:
            instanceList.append((r['site'], r['name']))
        elif pantheonSize:
            instanceList.append((r['site'], r['name']))

    return instanceList
