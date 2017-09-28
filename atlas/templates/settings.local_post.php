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
  'host' => '127.0.0.1',
  'port' => '3306',
  'prefix' => '',
);

// Define our slave connection.
$databases['default']['slave'][] = array(
  'driver' => 'mysql',
  'database' => '{{ sid }}',
  'username' => '{{ sid }}',
  'password' => '{{ pw }}',
  'host' => '127.0.0.1',
  'port' => '3307',
  'prefix' => '',
);

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
