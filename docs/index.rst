.. Atlas documentation master file, created by
   sphinx-quickstart on Thu Jul 13 17:08:08 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Atlas
=================================

.. image:: https://img.shields.io/badge/license-MIT-blue.svg?style=flat-round
    :target: https://en.wikipedia.org/wiki/MIT_License

.. _about:

About Atlas
------------------

Atlas is a RESTful API that interacts with servers to deploy and maintain `Web Express`_ at University of Colorado Boulder.

Atlas is built using Python Eve_, Celery_, and Fabric_; and MongoDB_.

Features
-----------------
* Create, update, run, and delete separate Drupal_ 7 instances (not traditional Drupal multisite).
* Gather statistics from instances, returns them from a query-able endpoint.
* Maintain and deploy routing information subdirectory based path structure.
* Slack and email notifications.


Contributing
-----------------

Pull requests are always welcome. Project is under active development. We are committed to keeping the Express Drupal install profile and Atlas independent of each other.

See `express_local`_ for setting up a local development environment.

.. toctree::
    :hidden:
    :maxdepth: 3
    
    configuration
    running
    command-samples
    changelog

.. _`Web Express`: http://www.colorado.edu/webcentral
.. _Eve: http://python-eve.org
.. _Celery: http://www.celeryproject.org
.. _Fabric: http://www.fabfile.org
.. _MongoDB: http://docs.mongodb.org
.. _Drupal: https://www.drupal.org
.. _`express_local`: https://github.com/CuBoulder/express_local
