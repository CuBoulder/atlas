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
        'instances_available.html',
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
    return render_template('instances_summary.html', summaryInstances=summaryInstances)


@atlas_admin.route('/instances/<id>')
def instance(id):
    instance = helpers.instanceSummary(id)
    return render_template('instance_summary.html', instance=instance)


@atlas_admin.route('/instances/t/<siteType>')
def instances_type(siteType=None):
    instanceList = helpers.instances(siteType=siteType)
    return render_template('instances_type.html', instanceList=instanceList, siteType=siteType)


@atlas_admin.route('/instances/p/<pantheonSize>')
def instances_pantheon(pantheonSize=None):
    instanceList = helpers.instances(pantheonSize=pantheonSize)
    return render_template('instances_pantheon.html', instanceList=instanceList, pantheonSize=pantheonSize)


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

    return render_template('search.html', form=form, instanceList=instanceList, query_type=query_type)
