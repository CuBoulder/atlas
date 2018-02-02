# Change log

## v2.1.2

Resolves:

- &#35;441 Add a cookie domain and path to settings file

## v2.1.1

Resolves:

- &#35;437 Remove commands posting to Slack
- &#35;408 Get timestamp into atlas.log
- &#35;438 Updating the current and label meta data for a code asset should not trigger a code-re-add process
- &#35;441 Add a cookie domain to settings file

## v2.1.0

This release adds granular deployment options for code assets. The following required fields (with the noted defaults) have been added to code items:
```json
"deploy": {
  "registry_rebuild": False,
  "cache_clear": True,
  "update_database": True
}
```
When a code item is added to an instance, the above drush commands will be run as indicated by the code asset. If multiple items are added, the commands will be run after all code is changed.

Need to

- Add a list of users to exclude from emails in config_local.py
- Be able to run `sudo -u [webserver_user] drush` without a password.

Resolves:

- &#35;95 Periodically check for unused code
- &#35;304 As a Service Manager, need to be able to deploy profile updates without updb
    - &#35;22 Add field for 'requires updb'
    - &#35;311 Add field for 'requires registry rebuild'
    - &#35;312 Add field for 'requires cache clear'
- &#35;330 During launch, drupal caches are cleared a lot
- &#35;412 Return something like `Command [xx:xx:xx] 2 of 16 - Success` in Slack
- &#35;10 Re-add packages to sites when changing meta data of a code item.
- &#35;338 Exclude the '_id' of the item we are updating as a query parameter
- &#35;401 Remove test accounts from bundle adding emails
- &#35;220 Started to review settings.php

## v2.0.3

Resolves:

- &#35;406 Stats are getting deleted for available instances.
- &#35;404 Fixed homepage cron command.

## v2.0.2

Resolves:

- &#35;403 Bug with code labels in email messages.

## v2.0.1

  Fixed issue that took down instance on Prod and prevented instances from restoring.

## v2.0.0

This release restructures Atlas and allows the Eve portion to be run from the command line.

Resolves:

- &#35;371 Refactor code to run as a proper python application
- &#35;329 Remove code dependencies Code
- &#35;378 Switch from APC to OPCache clearing
- &#35;331 Standardize logging structure
- &#35;397 Homepage sitemap.xml includes P1
- &#35;383 Pull stats from logs, not HTTP input
- &#35;368 Bug in slack post Bug
- &#35;391 Add `node_revision_total`
- &#35;386 Update DB settings
- &#35;200 Delete GSA code Instance
- &#35;106 Check for meta uniqueness in code items

## v1.0.26

Resolves:

- &#35;392 - When an instance gets taken down, delete it's statistic or update the status
- &#35;394 - Add days_since_last_login as int like days_since_last_edit

## v1.0.25

Resolves:

- Add fields to support CSE
- Express/&#35;1536 - Use HTTPS everywhere


## v1.0.24

Need to

- Make sure Atlas user can run `sudo -u [webserver_user] drush` without a password.
- Update Celery queues to include a `cron_queue`.

Resolves:

- &#35;53 - Handle no code state better
- &#35;352 - Separate cron properly
- &#35;354 - Atlas package emails get confusing with several bundles
- &#35;356 - Change to run drush as apache

Hotfix:

- &#35;381 - Add --uri to drush commands

## v1.0.23

Resolves:

- &#35;305 - Support new cron command syntax
- &#35;345 - Remove special handling for courses cron

## v1.0.22

Need to

- Add variable (`database_password`) to `config_local.py`. See `config_local.py.example`.
- Add variable (`database.port`) to `config_servers.py`. See `config_servers.py.example`.
- Update python packages.

Resolves:

- &#35;282 - Provision often fails, but the instance ends up 'available'
- &#35;317 - Switch to mysql-python connecter
- &#35;326 - Make SO and CE user lists nullable

## v1.0.21

Resolves:

- &#35;325 - Remove poola-custom
- &#35;315 - Settings files - Conditional for DEV
- &#35;319 - Adding query endpoint

## v1.0.02

Resolves:

- &#35;313 - Fix clear APC command
- &#35;309 - Switch to content editor

## v1.0.19

Resolves:

- &#35;306 - Add `drush cc drush` to registry rebuilds

## v1.0.18

Resolves:

- &#35;272 - Add 'locked' status
- Unbind LDAP
- &#35;282 - Continue to try a squash this bug

## v1.0.17

Resolves:

- &#35;266 - Allow More Headers In Requests
- &#35;271 - Add user count to statistics
- &#35;270 - Add status to statistics
- &#35;273 - Clean up temp files
- &#35;268 - Statistic objects for stuck 'pending' instances are not cleaning up
- &#35;265 - Verify statistics objects are getting updated
- &#35;251 - Stuck pending instances not being removed
- &#35;269 - Capture all bundles as typed or other
- &#35;282 - Provision often fails, but the instance ends up 'available'. Settings files or DB creation fails. Switched to Fabric templating. Wrapped fabric commands in exception catching.

## v1.0.16

Resolves:

- Instances are being marked as 'available' without databases.

## v1.0.15

Resolves:

- &#35;245 - Available instances are not replaced each night
- &#35;262 - Automatically clean up stats items that have deleted sites.
- &#35;259 - Need to accept variable_livechat_license_number
- &#35;256 - Code clone need labels
- &#35;251 - Math for age of a pending instance is wrong

## v1.0.14

Resolves:

- &#35;245 - Available instances are not replaced each night

## v1.0.13

Support new f5 command syntax. See &#35;204 and &#35;196.

Need to add variable (`load_balancer_config_group`) to `config_servers.py`. See  `config_servers.py.example`.

## v1.0.12

Resolves:

- Removed Celery email variables as that functionality is dprecated in 4.x
- &#35;244 Remove homepage files from Atlas
- &#35;234 Update Eve to 0.7.x

## v1.0.11

Hot fix to resolve bug in sending email.

## v1.0.10

This release requires updating Python packages and `config_local.py` (see `config_local.py.example`).

Resolves:

- &#35;224 - POST cron time to elasticsearch Improvement
- &#35;135 - Remove code to import from Inventory
- &#35;223 - Do not post to Slack on cron success.
- &#35;226 - Correct time calc
- &#35;160 - Atlas should handle the email/take down functionality Improvement
- &#35;190 - Atlas should email the user when a bundle is added Improvement
- &#35;218 - Fix pending site removal Bug
- &#35;215 - Update packages
- &#35;208 - Do not run 'add-packages' when there are no packages to add Bug
