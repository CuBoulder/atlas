import logging

from flask import Blueprint, render_template, request, flash
from eve.methods.get import getitem_internal, get_internal
from wtforms import Form, TextField, validators

from atlas.config import BASE_URLS, ENVIRONMENT
from atlas_admin import helpers

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
    return render_template('instance_summary.html', summaryInstances=summaryInstances)


@atlas_admin.route('/instances/t/<siteType>')
def instances_type(siteType=None):
    instanceList = helpers.instances(siteType=siteType)
    return render_template('instances_type.html', instanceList=instanceList, siteType=siteType)


@atlas_admin.route('/instances/p/<pantheonSize>')
def instances_pantheon(pantheonSize=None):
    instanceList = helpers.instances(pantheonSize=pantheonSize)
    return render_template('instances_pantheon.html', instanceList=instanceList, pantheonSize=pantheonSize)


class SearchForm(Form):
    name = TextField('Path')

    @atlas_admin.route('/search', methods=['GET', 'POST'])
    def hello():
        form = SearchForm(request.form)

        print form.errors
        if request.method == 'POST':
            name = request.form['path']
            print path

        if form.validate():
            # Save the comment here.
            flash('Search for ' + path)
        else:
            flash('All the form fields are required. ')

        return render_template('search.html', form=form)
