<?php
global $conf;

// Define tmp directory
$conf['file_temporary_path'] = '/wwwng/sitefiles/{{sid}}/tmp';

{% if environment != 'local' %}
$databases['default']['default'] = array(
  'driver' => 'mysql',
  'database' => '{{ sid }}',
  'username' => '{{ sid }}',
  'password' => '{{ pw }}',
  'host' => '{{ database_servers.master }}',
  'port' => '3307',
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
  'port' => '3307',
  'prefix' => '',
);
{% endfor %}
{% endif %}
{% else %}
$databases['default']['default'] = array(
  'driver' => 'mysql',
  'database' => '{{ sid }}',
  'username' => 'root',
  'password' => 'root',
  'host' => '{{ database_servers.master }}',
  'port' => '3307',
  'prefix' => '',
);

{% endif %}
