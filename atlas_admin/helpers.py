from collections import Counter
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
            results = get_internal('sites')
        else:
            results = res.get('_items', None)

        statusCount = Counter()
        # Count totals by status
        for res in results[0]['_items']:
            statusCount[res['status']] += 1
        summary.update(dict(statusCount))
    else:
        summary = None

    return summary


def users():
    """Return a list of user names and email addresses
    """
    q = get_internal('statistics')

    res = q[0] if len(q) > 0 else {}
    totalItems = res.get('_meta', None).get('total', None)

    results = []

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
                userNameList += v
            for k, v in r['users']['email_address'].items():
                userEmailList += v

    # Get a de-duped list
    uniqueUserNameList = uniqueList(userNameList)
    uniqueUserEmailList = uniqueList(userEmailList)

    return (uniqueUserNameList, uniqueUserEmailList)


def uniqueList(li):
    newList = []
    for x in li:
        if x not in newList:
            newList.append(x)
    return newList
