# Change log
## v1.0.11
This release requires a MongoDB command to migrate from Site to Instance
```
db.sites.renameCollection("instance")
```

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
