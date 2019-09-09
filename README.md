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

## Local setup

* Create and activate virtual environment

  ```sh
  virtualenv .venv
  source .venv/bin/activate
  ```

* Install requirements
  
  ```sh
  pip install -f requirements.txt
  ```

* Install MongoDB - [Homebrew](https://docs.mongodb.com/manual/tutorial/install-mongodb-on-os-x/)

  ```sh
  brew tap mongodb/brew
  brew install mongodb-community@4.2
  # Run as a Homebrew service
  brew services start mongodb-community@4.2
  ```

* Start Atlas

  ```sh
  FLASK_APP=run.py flask run
  ```

* Import sample database

  ```sh
  mongorestore [path/to/dump/location]
  ```
