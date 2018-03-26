# Atlas

Atlas is a RESTful API that interacts with servers to deploy and maintain [Web Express](https://github.com/CuBoulder/express) at University of Colorado Boulder.

## Features
* Chronological tasks run to keep a small number of instances available for assignment to end users.
* POST to create additional instances on demand.
* Available instances are replaced every night.
* All items are versioned.
* Backups and restore to new instance.

### API
* Prefers to receive JSON encoded POST request.
* CRUD Web Express instances

## Getting started

### Installing

See [Express_local](https://github.com/CuBoulder/express_local) for setting up a local development environment.

On servers, you will need to create the backups directory

### Configuration

Configuration is split between various files `config_*.py`. You need to create `config_local.py` and `config_servers.py` files.
If you are on anything other than a local development environment, you will also need to create a `.mylogin.cnf` file to authenticate into MySQL (http://dev.mysql.com/doc/refman/5.7/en/mysql-config-editor.html). The naming convention is `[database_user]_[environment]`.

### Populating Atlas

Code items should be created first. Required fields are: git URL, commit hash, Name, Version, and Type (core, profile, module, theme, library). Optional fields are: is_current (allows you to indicate the preferred version of a code item) and a tagging field.

Instance items are created with a 'pending' status and can be assigned a specific core and/or profile when created. If a core or profile is not specified, the 'current' version of the default is used.

## Deploying Atlas

Currently we use a `git pull` deployment. When code is changed, you need to restart Celery, Celerybeat and Apache.

Celery Flower is available via to command line to inspect tasks.
```bash
 /data/environments/atlas/bin/celery -A celery flower --conf=path/to/atlas/config_flower.py
```

Celery will return a url in the first part of a long response.
```bash
[I 170118 22:33:35 command:136] Visit me at http://[YOUR-URL]:5555
```

## Contributing

Pull requests are always welcome. Project is under active development. We are committed to keeping the Express Drupal install profile and Atlas independent of each other.

## Best Practices and Notes

### Code maintenance
*The safest option is always to use **POST** to create a new item and then to **PATCH** the instance over.*
* No current version - **POST** new code item
* Stable version - **POST** new code item
* Version with error and new version does not require an update hook - **PATCH** existing code item
* Version with error and new version *does* require an update hook - **POST** new code item

### Using Commands
* Schema notes:
  * `name` is an end user facing field that should describe the command.
  * `command` is the string that is run on the server(s). Commands do not support prompts and should exit with a `0` exit code, this means end drush commands like `drush en [module_name] -y` with `-y`.
  * `query` appended to `?where` in a call to the Atlas API. Special characters, including all symbols, need to be unicode encoded ([Unicode Character table](https://unicode-table.com/)).
  * `single_server` is useful for commands that affect only the database layer like _module enable_ or _Drupal cache clear_.
* There are several commands that have hooks that interrupt the normal command flow. They are:
  * `clear_apc`
  * `import_code`
  * `correct_file_permissions`
  * `update_settings_file`
  * `update_homepage_extra_files`
* To use a command, first **POST** to create the command. Then **PATCH** the item to 'run' the command. 
  * This is not the most intuitive pattern, but not sure what a better pattern in at the moment. Considering using an authenticated **GET** to the command item, but that would be a different pattern than all other endpoints. Also considering defining our own method.
 
  

## Sample requests

### Code items

#### Drupal core 7.42
```bash
curl -i -v -X POST -d '{"git_url": "git@github.com:CuBoulder/drupal-7.x.git", "commit_hash": "9ee4a1a2fa3bedb3852d21f2198509c107c48890", "meta":{"version": "7.42", "code_type": "core", "name": "drupal", "is_current": true}}' -H 'Content-Type: application/json' -u 'USERNAME:PASSWORD' https://inventory.local/atlas/code
```

#### Express 2.2.5
```bash
curl -i -v -X POST -d '{"git_url": "git@github.com:CuBoulder/express.git", "commit_hash": "5f1fb979cacff22d6641da3c413696d02f9cc5f5", "meta":{"version": "2.2.5", "code_type": "profile", "name": "express", "is_current": true}}' -H 'Content-Type: application/json' -u 'USERNAME:PASSWORD' https://inventory.local/atlas/code
```

### Instance items

#### Create an Instance
```bash
curl -i -v -X POST -d '{"status": "pending"}' -H 'Content-Type: application/json' -u 'USERNAME:PASSWORD' https://inventory.local/atlas/instance
```

#### Patch an Instance to 'installed'
```bash
curl -i -v -X PATCH -d '{"status": "installed"}' -H "If-Match: 4173813fc614292febc79241a8b677266cbed826" -H 'Content-Type: application/json' -u 'USERNAME:PASSWORD' https://inventory.local/atlas/instance/579b8f9a89b0dc0d7d7ce090
```

#### Patch a new Profile in (update an Instance to new version of profile)
```bash
curl -i -v -X PATCH -d '{"code": {"profile": "57adffc389b0dc1631822bce"}}' -H "If-Match: b8c1942d0238559ca9c3333626777ec7ce97f955" -H 'Content-Type: application/json' -u 'USERNAME:PASSWORD' https://inventory.local/atlas/instance/57adff1389b0dc1613d0f948
```

#### Delete an Instance
```bash
curl -i -v -X DELETE -H "If-Match: 5b3bc91045cca9fdc9a8b50bfb4095ecceb2dcbe" -H 'Content-Type: application/json' -u 'USERNAME:PASSWORD' https://inventory.local/atlas/instance/57adfdb789b0dc1612c23a90
```
