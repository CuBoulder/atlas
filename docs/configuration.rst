Configuration and Deployment
=================================

Atlas is tested and run on RHEL 7 uing ``mod_wsgi`` and Apache 2.4 with the following additional packages installed:

* ``openldap``
* ``openldap-devel``
* ``libffi-devel``
* ``gcc``
* ``openssl``
* ``openssl-devel``


Configuration files
-----------------------

Configuration is split between various files ``config_*.py``. You need to create ``config_local.py`` and ``config_servers.py`` files.
If you are on anything other than a local development environment, you will also need to create a `.mylogin.cnf` file to `authenticate into MySQL`_. The naming convention is `[database_user]_[environment]`.

Deploying
---------------------

Sample Apache vhost

.. code-block:: apache

    <VirtualHost *:80>
        SetEnv ATLAS_ENV production

        WSGIDaemonProcess atlas processes=2 threads=5 user=[USER] group=[GROUP] display-name=%{GROUP}
        WSGIScriptAlias / /path/to/atlas/atlas.wsgi

        <Directory "/path/to/atlas">
                WSGIPassAuthorization On
                Require all granted
        </Directory>
        CustomLog "logs/atlas-access_log" combined
        ErrorLog "logs/atlas-error_log"
    </VirtualHost>

* `Sample celeryd init script`_
* `Sample celerybeat init script`_


Additional information 
-------------------------

Celery Flower is available via to command line to inspect tasks.

.. code-block:: bash

    /path/to/virtualenv/atlas/bin/celery -A celery flower --conf=path/to/atlas/config_flower.py

Celery Flower will return a url in the first part of a long response.

.. code-block:: log
    
    [I 170118 22:33:35 command:136] Visit me at http://[YOUR-URL]:5555


.. _`authenticate into MySQL`: http://dev.mysql.com/doc/refman/5.7/en/mysql-config-editor.html
.. _`Sample celeryd init script`: http://docs.celeryproject.org/en/latest/userguide/daemonizing.html#init-script-celeryd
.. _`Sample celerybeat init script`: http://docs.celeryproject.org/en/latest/userguide/daemonizing.html#init-script-celerybeat
