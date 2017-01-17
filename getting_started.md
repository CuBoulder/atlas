# Getting started

## Installing

See [Express_local](https://github.com/CuBoulder/express_local) for setting up a local development environment.

## Configuration

Configuration is split between various files `config_*.py`. You need to create `config_local.py` and `config_servers.py` files.
If you are on anything other than a local development environment, you will also need to create a `.mylogin.cnf` file to authenticate into MySQL (http://dev.mysql.com/doc/refman/5.7/en/mysql-config-editor.html). The naming convention is `[database_user]_[environment]`.

## Populating Atlas

### Code
Code items should be created first. Required fields are: git URL, commit hash, Name, Version, and Type (core, profile, module, theme, library). Optional fields are: is_current (allows you to indicate the preferred version of a code item) and a tagging field.

#### Importing code from a JSON file

You can copy the JSON output of the code endpoint from an Atlas instance and import into another.
1. In the new instance, create a command item for `import_code` with the `query` set to the URL of the JSON file (GitHub gist has been tested). 
2. Patch the item (setting `single_server` is a good toggle) to run the import.

### Sites 
Site items are created with a 'pending' status and can be assigned a specific core and/or profile when created. If a core or profile is not specified, the 'current' version of the default is used.