# Change log

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
