# Change log
## v1.1.0
1. Pull new code.
1. Rename `site` collection to `instance`.
    ```
    db.sites.renameCollection("instance")
    ```
1. Update python packages via `requirements.txt`.
1. Restart `celery`, `celerybeat`, and `apache`.
