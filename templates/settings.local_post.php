<?php
global $conf;

// Min cache lifetime 0, max defaults to 300 seconds.
$conf['cache_lifetime'] = 0;
$conf['page_cache_maximum_age'] = {{ page_cache_maximum_age }};

// Define tmp directory
$conf['file_temporary_path'] = '{{ tmp_files_directory }}';

{% if environment != 'local' %}
$databases['default']['default'] = array(
  'driver' => 'mysql',
  'database' => '{{ sid }}',
  'username' => '{{ sid }}',
  'password' => '{{ pw }}',
  'host' => '{{ database_servers.master }}',
  'port' => '{{ port }}',
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
  'port' => '{{ port }}',
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
