Command Samples
=======================

Code items
-----------------
* Drupal core 7.42
    .. code-block:: bash

        curl -i -v -X POST -d '{"git_url": "git@github.com:CuBoulder/drupal-7.x.git", "commit_hash": "9ee4a1a2fa3bedb3852d21f2198509c107c48890", "meta":{"version": "7.42", "code_type": "core", "name": "drupal", "is_current": true}}' -H 'Content-Type: application/json' -u 'USERNAME:PASSWORD' https://inventory.local/atlas/code
* Express 2.2.5
    .. code-block:: bash

        curl -i -v -X POST -d '{"git_url": "git@github.com:CuBoulder/express.git", "commit_hash": "5f1fb979cacff22d6641da3c413696d02f9cc5f5", "meta":{"version": "2.2.5", "code_type": "profile", "name": "express", "is_current": true}}' -H 'Content-Type: application/json' -u 'USERNAME:PASSWORD' https://inventory.local/atlas/code

Instance items
-------------------
* Create an Instance
    .. code-block:: bash

        curl -i -v -X POST -d '{"status": "pending"}' -H 'Content-Type: application/json' -u 'USERNAME:PASSWORD' https://inventory.local/atlas/instance

* Change the 'status' of an Instance to 'installed'
    .. code-block:: bash

        curl -i -v -X PATCH -d '{"status": "installed"}' -H "If-Match: 4173813fc614292febc79241a8b677266cbed826" -H 'Content-Type: application/json' -u 'USERNAME:PASSWORD' https://inventory.local/atlas/instance/579b8f9a89b0dc0d7d7ce090

* Update the installation profile for an Instance
    .. code-block:: bash

        curl -i -v -X PATCH -d '{"code": {"profile": "57adffc389b0dc1631822bce"}}' -H "If-Match: b8c1942d0238559ca9c3333626777ec7ce97f955" -H 'Content-Type: application/json' -u 'USERNAME:PASSWORD' https://inventory.local/atlas/instance/57adff1389b0dc1613d0f948

* Delete an Instance
    .. code-block:: bash

        curl -i -v -X DELETE -H "If-Match: 5b3bc91045cca9fdc9a8b50bfb4095ecceb2dcbe" -H 'Content-Type: application/json' -u 'USERNAME:PASSWORD' https://inventory.local/atlas/instance/57adfdb789b0dc1612c23a90

