# Atlas

Atlas is a RESTful API that interacts with servers to deploy and maintain [Drupal](https://www.drupal.org) as part of the [Web Express service](https://github.com/CuBoulder/express) at University of Colorado Boulder.


Atlas is built using Python [Eve](http://python-eve.org), [Celery](http://www.celeryproject.org), and [Fabric](http://www.fabfile.org); and [MongoDB](http://docs.mongodb.org).

## Features

* Create, update, run, and delete separate Drupal_ 7 instances (not traditional Drupal multisite).
* Gather statistics from instances, returns them from a query-able endpoint.
* Maintain and deploy routing information subdirectory based path structure.
* Slack and email notifications.
