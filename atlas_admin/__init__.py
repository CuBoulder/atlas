import logging

from flask import Blueprint, render_template, request, flash
from eve.methods.get import getitem_internal, get_internal
from wtforms import Form, TextField, validators

from atlas.config import BASE_URLS, ENVIRONMENT
from atlas_admin import helpers, forms

atlas_admin = Blueprint('atlas_admin', __name__,
                        template_folder='templates', static_folder='static')
envVars = {'baseURL': BASE_URLS[ENVIRONMENT]}


@atlas_admin.route('/')
def index():
    availableInstances = helpers.availableInstances()
    summaryInstances = helpers.summaryInstances()
    summaryUsers = helpers.summaryUsers()
    summaryStatistics = helpers.summaryStatistics()
    # Display a list links to other reports.
    return render_template(
        'index.html',
        availableInstances=availableInstances,
        envVars=envVars,
        summaryInstances=summaryInstances,
        summaryStatistics=summaryStatistics,
        summaryUsers=summaryUsers)


@atlas_admin.route('/available')
def available():
    availableInstances = helpers.availableInstances()
    return render_template(
        'instances/available.html',
        availableInstances=availableInstances,
        envVars=envVars)


@atlas_admin.route('/users')
@atlas_admin.route('/users/<role>')
def users(role=None):
    users = helpers.users(role)
    return render_template('users.html', users=users, role=role, envVars=envVars)


@atlas_admin.route('/instances')
def instances():
    summaryInstances = helpers.summaryInstances()
    # Tuples of number and cost
    if summaryInstances:
        xs = (int(summaryInstances['pantheon_size'].get('xs', 0)), 350)
        s = (int(summaryInstances['pantheon_size'].get('s', 0)), 1375)
        m = (int(summaryInstances['pantheon_size'].get('m', 0)), 2475)
        l = (int(summaryInstances['pantheon_size'].get('l', 0)), 4950)
        xl = (int(summaryInstances['pantheon_size'].get('xl', 0)), 8250)
        e = (int(summaryInstances['pantheon_size'].get('e', 0)), 20000)
        cost_multiplier = .7
        summaryInstances['cost_multiplier'] = cost_multiplier
        summaryInstances['cost'] = ((xs[0] * xs[1]) + (s[0] * s[1]) + (m[0] * m[1]) +
                                    (l[0] * l[1]) + (xl[0] * xl[1]) + (e[0] * e[1]))
    return render_template('instances/summary.html', summaryInstances=summaryInstances)

@atlas_admin.route('/instances/themes')
def theme_summary():
    summaryInstances = helpers.summaryThemes()
    return render_template('instances/themes.html', summaryInstances=summaryInstances)

@atlas_admin.route('/instances/th/<themeName>')
def theme_instances(themeName=None):
    instanceList = helpers.siteStats(themeName=themeName)
    return render_template('instances/stats.html', instanceList=instanceList, themeName=themeName)

@atlas_admin.route('/instances/<id>')
def instance(id):
    instanceRecord = helpers.instanceSummary(id)
    return render_template('instance_summary.html', instance=instanceRecord, envVars=envVars)


@atlas_admin.route('/instances/t/<siteType>')
def instances_type(siteType=None):
    instanceList = helpers.instances(siteType=siteType)
    return render_template('instances/type.html', instanceList=instanceList, siteType=siteType)


@atlas_admin.route('/instances/p/<pantheonSize>')
def instances_pantheon(pantheonSize=None):
    instanceList = helpers.instances(pantheonSize=pantheonSize)
    return render_template('instances/pantheon.html', instanceList=instanceList, pantheonSize=pantheonSize)


@atlas_admin.route('/instances/s/<siteStatus>')
def instances_status(siteStatus=None):
    instanceList = helpers.instances(siteStatus=siteStatus)
    return render_template('instances/type.html', instanceList=instanceList, siteStatus=siteStatus)


@atlas_admin.route('/search', methods=['GET', 'POST'])
def search():
    instanceList = None
    instanceUserList = None
    query_type = None

    form = forms.searchForm(request.form)
    if request.method == 'POST':
        query = request.form['query']
        query_type = request.form['query_type']

        if form.validate():
            flash('Search for "' + query + '"')
            if query_type == 'path':
                instanceList = helpers.instances(path=query)
            elif query_type in ['username', 'email_address']:
                instanceList = helpers.instancesUserLookup(query=query, query_type=query_type)
        elif not form.validate():
            flash('Error: Form failed validation.')

    return render_template('instances/search.html', form=form, instanceList=instanceList, query_type=query_type)


@atlas_admin.route('/user/search', methods=['GET', 'POST'])
def userSearch():
    user_list = None

    form = forms.userSearchForm(request.form)
    if request.method == 'POST':
        query = request.form['query']
        query_type = request.form['query_type']

        if form.validate():
            flash('Search for "' + query + '"')
            if query_type == 'path':
                instanceList = helpers.instances(path=query)
            elif query_type == 'path_exact':
                query = '^' + query + '$'
                instanceList = helpers.instances(path=query)
            instanceIdList = []
            for (j, k, l) in instanceList:
                instanceIdList.append(j)
            user_list = helpers.userInstanceLookup(instanceIdList)
        elif not form.validate():
            flash('Error: Form failed validation.')

    return render_template('users/search.html', form=form, userList=user_list)


@atlas_admin.route('/instances/cse')
def instances_cse():
    instance_list = helpers.instances(cse=True)
    return render_template('instances/cse.html', instanceList=instance_list)
