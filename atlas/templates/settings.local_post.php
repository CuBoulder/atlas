<?php
global $conf;

// Min cache lifetime 0, max defaults to 300 seconds.
$conf['cache_lifetime'] = 0;
$conf['page_cache_maximum_age'] = {{ page_cache_maximum_age }};

{% if environment != 'local' %}
$databases['default']['default'] = array(
  'driver' => 'mysql',
  'database' => '{{ sid }}',
  'username' => '{{ sid }}',
  'password' => '{{ pw }}',
  'host' => '{{ database_servers.master }}',
  'port' => '{{ database_servers.port }}',
  'prefix' => '',
);
{% if database_servers.slaves %}
{% for slave in database_servers.slaves -%}
// Define our slave database(s)
$databases['default']['slave'][] = array(
  'driver' => 'mysql',
  'database' => '{{ sid }}',
  'username' => '{{ sid }}',
  'password' => '{{ pw }}',
  'host' => '{{ slave }}',
  'port' => '{{ database_servers.port }}',
  'prefix' => '',
);
{% endfor %}
{% endif %}
{% else %}
$databases['default']['default'] = array(
  'driver' => 'mysql',
  'database' => '{{ sid }}',
  'username' => '{{ sid }}',
  'password' => '{{ pw }}',
  'host' => 'localhost',
  'port' => '{{ port }}',
  'prefix' => '',
);
{% endif %}

{% if environment == 'local' %}
// Allow self signed certs for python.local.
$conf['drupal_ssl_context_options'] = array(
  'default' => array(
    'ssl' => array(
      'verify_peer' => TRUE,
      'verify_peer_name' => TRUE,
      'allow_self_signed' => FALSE,
    ),
  ),
  'python.local' => array(
    'ssl' => array(
      'verify_peer' => FALSE,
      'verify_peer_name' => FALSE,
      'allow_self_signed' => TRUE,
    ),
  ),
);
{% endif %}
