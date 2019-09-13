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
    form = forms.instanceSearchForm(request.form)
    if request.method == 'POST':
        path = request.form['path']

    if form.validate():
        # Save the comment here.
        flash('Search for ' + path)
        instanceList = helpers.instances(path=path)
    else:
        flash('All the form fields are required. ')
        instanceList = None

    return render_template('instance_search.html', form=form, instanceList=instanceList)
