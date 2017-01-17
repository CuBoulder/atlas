# Atlas

Atlas is a RESTful API that interacts with servers to deploy and maintain [Web Express](https://github.com/CuBoulder/express) at University of Colorado Boulder.

## Features
* Chronological tasks run to keep a small number of instances available for assignment to end users.
* POST to create additional instances on demand.
* Available instances are replaced every night.
* Code, Site, and Command items are versioned.

## API
* Prefers to receive JSON encoded POST request.
* CRUD Web Express instances

## Deploying Atlas

Currently we use a `git pull` deployment. When code is changed, you need to restart Celery, Celerybeat and Apache.

Celery Flower is available via to command line to inspect tasks.
```bash
/data/environments/atlas/bin/celery -A celery flower --conf=/data/code/atlas/config_flower.py
```

## Contributing

Pull requests are always welcome. Project is under active development. We want to make sure that Express doesn't become dependant on Atlas.

## Documentation Index
* [Getting Started](getting_started.md)
* [Sample API requests](sample_requests.md)
