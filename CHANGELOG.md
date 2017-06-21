# Change log

## v1.0.17

Resolves:

- &#35;266 - Allow More Headers In Requests
- &#35;271 - Add user count to statistics
- &#35;270 - Add status to statistics
- &#35;273 - Clean up temp files.

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
