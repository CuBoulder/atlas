from collections import Counter, OrderedDict
from flask import request
from eve.methods.get import getitem_internal, get_internal


def availableInstances():
    """Get a list of available instances and display them with links to invitation pages
    """
    availableInstances = get_internal('sites',  **{"status": "available"})
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
        Path summaries - To Do
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

    return summary


def instances(siteType=None, pantheonSize=None):
    if siteType:
        q = get_internal('sites',  **{"site_type": siteType})
    elif pantheonSize:
        q = get_internal('sites',  **{"pantheon_size": pantheonSize})
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
            qAll = get_internal('sites',  **{"site_type": siteType})
        elif pantheonSize:
            qAll = get_internal('sites',  **{"pantheon_size": pantheonSize})
        else:
            qAll = get_internal('sites')
        results = qAll[0].get('_items', None)
    else:
        results = res.get('_items', None)

    # Get list of all users
    instanceList = []
    for r in results:
        if siteType:
            instanceList.append((r['path'], r['pantheon_size']))
        elif pantheonSize:
            instanceList.append((r['path'], r.get('site_type', 'p1')))

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
        summary = None

    return OrderedDict(sorted(summary.items()))


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
        'total_nodes': 0,
        'total_beans': 0,
    }
    responsive_total = 0
    days_total = 0

    for r in results:
        summary['total_nodes'] += r.get('nodes_total', 0)
        summary['total_beans'] += r.get('beans_total', 0)
        days_total += r.get('days_since_last_edit', 0)
        if r.get('theme_is_responsive', False):
            responsive_total += 1
        # Avg nodes per site
        # percent responsive
        # avg days_since_last_login
        # total bean
        # avg beans per site

    summary['percent_responsive'] = "{0:.2f}%".format((float(responsive_total)/totalItems)*100)
    summary['avg_nodes'] = int(summary['total_nodes']/totalItems)
    summary['avg_beans'] = int(summary['total_beans']/totalItems)
    summary['avg_days_since_edit'] = int(days_total/totalItems)
    print(summary)
    return summary


def uniqueList(li):
    newList = []
    for x in li:
        if x not in newList:
            newList.append(str(x))
    return newList
