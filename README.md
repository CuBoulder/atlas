# Atlas

Atlas is a RESTful API that interacts with servers to deploy and maintain [Web Express](https://github.com/CuBoulder/express) at University of Colorado Boulder.

## Installing

See [Express_local](https://github.com/CuBoulder/express_local) for setting up a local development environment.

## Getting started

Code items should be created first. Required fields are: git URL, commit hash, Name, Version, and Type (core, profile, module, theme, library). Optional fields are: is_current (allows you to indicate the preferred version of a code item) and a tagging field.
 
Site items are created with a 'pending' status and can be assigned a specific core and/or profile when created. If a core or profile is not specified, the 'current' version of the default is used.

## Features
* Chronological tasks run to keep a small number of instances available for assignment to end users.
* POST to create additional instances on demand.
* Available instances are replaced every night.

## API
* Prefers to receive JSON encoded POST request.
* CRUD Web Express instances

## Configuration

Configuration is split between various files `config_*.py`. You need to create a `config_local.py` file and will most likely want to replace `config_servers.py`.

## Deploying Atlas

Currently we use a `git pull` deployment. When code is changed, you need to restart Celery, Celerybeat and Apache.

## Contributing

Pull requests are always welcome. Project is under active development. We want to make sure that Express doesn't become dependant on Atlas.

## Sample requests
### Code items
#### Drupal core 7.42
```bash
curl -i -v -X POST -d '{"git_url": "git@github.com:CuBoulder/drupal-7.x.git", "commit_hash": "9ee4a1a2fa3bedb3852d21f2198509c107c48890", "meta":{"version": "7.42", "code_type": "core", "name": "drupal", "is_current": true}}' -H 'Content-Type: application/json' -u 'USERNAME:PASSWORD' http://inventory.local/atlas/code
```

#### Express 2.2.5
```bash
curl -i -v -X POST -d '{"git_url": "git@github.com:CuBoulder/express.git", "commit_hash": "5f1fb979cacff22d6641da3c413696d02f9cc5f5", "meta":{"version": "2.2.5", "code_type": "profile", "name": "express", "is_current": true}}' -H 'Content-Type: application/json' -u 'USERNAME:PASSWORD' http://inventory.local/atlas/code
```

### Site items
#### Create a Site
```bash
curl -i -v -X POST -d '{"status": "pending"}' -H 'Content-Type: application/json' -u 'USERNAME:PASSWORD' http://inventory.local/atlas/sites
```

#### Patch a Site to 'installed'
```bash
curl -i -v -X PATCH -d '{"status": "installed"}' -H "If-Match: 4173813fc614292febc79241a8b677266cbed826" -H 'Content-Type: application/json' -u 'USERNAME:PASSWORD' http://inventory.local/atlas/sites/579b8f9a89b0dc0d7d7ce090
```

#### Patch a new Profile in (update site to new version of profile)
```bash
curl -i -v -X PATCH -d '{"code": {"profile": "57adffc389b0dc1631822bce"}}' -H "If-Match: b8c1942d0238559ca9c3333626777ec7ce97f955" -H 'Content-Type: application/json' -u 'USERNAME:PASSWORD' http://inventory.local/atlas/sites/57adff1389b0dc1613d0f948
```

#### Delete a site
```bash
curl -i -v -X PATCH -d '{"status":"delete"}' -H "If-Match: 5b3bc91045cca9fdc9a8b50bfb4095ecceb2dcbe" -H 'Content-Type: application/json' -u 'USERNAME:PASSWORD' http://inventory.local/atlas/sites/57adfdb789b0dc1612c23a90
```