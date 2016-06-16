# Atlas

Atlas is a RESTful API that use Ansible to interact with servers to deploy and
maintain [Web Express](https://github.com/CuBoulder/express) at University of
Colorado Boulder.

## Installing / Getting started

See [Express_local](https://github.com/CuBoulder/express_local)

## Developing

Here's a brief intro about what a developer must do in order to start developing
the project further.

### Deploying / Publishing

Currently we use a Jenkins to do a `git pull` deployment. When code is changed, you need to run the following service restart command:
```bash
sudo service celeryd restart && sudo service celerybeat restart && sudo service apache restart
```

## Features
CRUD Web Express instances
* Chronological tasks run to keep a small number of instances available for assignment to end users.
* POST to create additional instances on demand.
* Available instances are replaced every night and every time code is updated.

## Configuration

Configuration is split between several files and you will need to create a `config_local.py` file.

Servers are defined in `ansible/hosts`.

## Contributing

Pull requests are always welcome.
