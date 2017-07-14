Running Atlas
========================

Running the first time
-------------------------

* Code items need to be created before instances.
* After a ``core`` and ``profile`` with ``meta.is_current: true`` set are created, Atlas will provision several instances.
* All endpoints have concurency control to make sure that users do not unintentionally overwrite eachother. When updating an item, you will need to include the ``etag`` in an ``If-Match`` request header.

Cronological tasks
---------------------

* Every 5 minutes
    * Available instances check - Maintains 5 ``available`` instances
    * Delete stuck 'pending' instances - Cleans up instances that fail to provision correctly.
* Every 60 minutes
    * Cron - 'launched' instances
    * Remove orphan statistics - Remove statistics items that do not have a corelating instance record.
* Every 2 hours
    * Cron - instances with the ``cu_classes_bundle``
    * Take down old installed instances - On non-production environments, remove isntalled instances that are more than 35 days old.
* Every 3 hours
    * Cron - 'installed' instances
* Every 24 hours
    * Replace available instances - Serves as routine integration testing.
    * Verify statistics updating - Verify that active statistics items have been updated in the last 36 hours.

Code
----------

Types of code
~~~~~~~~~~~~~~~~~~~

* Core
* Profile
* Package
    * Module
    * Theme
    * Library

Creating and updating code
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The safest option is always to use **POST** to create a new item and then to **PATCH** the instance to update the code for that instance.

How to create or update code:

* No current version - **POST** new code item
* Stable version - **POST** new code item
* Version with error and new version does not require an update hook - **PATCH** existing code item
* Version with error and new version *does* require an update hook - **POST** new code item

Instances and Routes
-------------

Instance items are created with a ``pending`` status and can be assigned a specific core and/or profile when created. If a core or profile is not specified, the 'current' version of the default is used.

Instance states
~~~~~~~~~~~~~~~~~~~~~
* Instances are created in a ``pending`` state, this state triggers the provision.
* After an instance is provisioned and the Drupal installation is run, the state is moved to ``available``.
    * Cron is not run on ``available`` instances and packages cannot be added to instances in this state.
* When a user is invited or otherwise allocated an instance the state should be changed to ``installing``.
    * The settings files for the instance is updated.
    * Cron is run on instances in this state.
    * State ends on ``installed`` and packages can now be added.
* ``launching`` requires a ``primary_route``
    * Update settings files.
    * Activates any associated routes that are ``active_on_launch: True``.
    * Create symlinks from route ``source`` in the web root to the code root.


Route states
~~~~~~~~~~~~~~~~~~~~~

* ``'route_status': 'active'``
    * Only ``active`` routes are added to the load balancer.
    * ``active`` routes can only be associated with a ``launched`` instance.
* If a route is associated with an instance, and has ``active_on_launch: True`` and ``'route_status': 'inactive'``


Create an instance
~~~~~~~~~~~~~~~~~~~~~~
.. code-block:: bash

    curl -i -v -X POST -d '{"status": "pending"}' -H 'Content-Type: application/json' -u 'USERNAME' https://127.0.0.1/atlas/instance

Update an instance
~~~~~~~~~~~~~~~~~~~~~
* Update the 'status' of an Instance to 'installed'
    .. code-block:: bash

        curl -i -v -X PATCH -d '{"status": "installed"}' -H "If-Match: 4173813fc614292febc79241a8b677266cbed826" -H 'Content-Type: application/json' -u 'USERNAME' https://127.0.0.1/atlas/instance/

* Update the 'profile' and 'core' of an Instance
    .. code-block:: bash

        curl -i -v -X PATCH -d '{"meta": {"core": "[code_id]", "profile":"[profile_id]"}}' -H "If-Match: [etag]" -H 'Content-Type: application/json' -u 'USERNAME' https://127.0.0.1/atlas/instance/


Commands
---------------

* Schema notes:
    * ``name`` is an end user facing field that should describe the command.
    * ``command`` is the string that is run on the server(s). Commands do not support prompts and should exit with a ``0`` exit code, this means end drush commands like `drush en [module_name] -y` with `-y`.
    * ``query`` appended to ``?where`` in a call to the Atlas API. Special characters, including all symbols, need to be unicode encoded ([Unicode Character table](https://unicode-table.com/)).
    * ``single_server`` is useful for commands that affect only the database layer like *module enable* or *Drupal cache clear*.
* There are several commands that have hooks that interrupt the normal command flow. They are:
    * ``clear_apc``
    * ``import_code``
    * ``correct_file_permissions``
    * ``update_settings_file``
    * ``update_homepage_extra_files``
* To use a command, first **POST** to create the command. Then **PATCH** the item to 'run' the command. 
    .. note::
        In the future, commands will be run by sending a **POST** to ``command/<command_id>/execute/``.
