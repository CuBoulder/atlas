<?php
/**
 * @file
 * Drupal site-specific configuration file.
 *
 * We include a pre and post local file so that we can set variables for the
 * main file and override config as needed.
 */

/**
 * Include a pre local settings file if it exists.
 */
global $conf;

// Atlas information
$conf["install_profile"] = "{{profile}}";
$conf["cu_sid"] = "{{sid}}";
$conf['sn_key'] = "{{ servicenow_key }}";

$conf["atlas_id"] = "{{atlas_id}}";
$conf["atlas_url"] = "{{atlas_url}}";
$conf["atlas_username"] = "{{atlas_username}}";
$conf["atlas_password"] = "{{atlas_password}}";
$conf["atlas_status"] = "{{status}}";
$conf["atlas_statistics_id"] = "{{atlas_statistics_id}}";
$conf["atlas_logging_url"] = "{{atlas_logging_url|join(sid)}}";

$path = "{{path}}";
{% if status in ['launched', 'launching'] -%}
$launched = TRUE;
{% else -%}
$launched = FALSE;
{% endif %}
{% if path == 'homepage' -%}
$conf["cu_path"] = "";
{% else -%}
$conf["cu_path"] = "{{path}}";
{%- endif %}

// Google Data
{% if google_cse_csx -%}
$conf["google_cse_cx"] = "{{google_cse_csx}}";
{% else -%}
$conf["google_cse_cx"] = NULL;
{% endif %}
$conf['googleanalytics_account'] = 'UA-25752450-1';

{% if ( (google_tag_client_container_id) and (environment in ['local','dev','test']) ) %}
  $conf['google_tag_client_container_id'] = '{{ google_tag_client_container_id }}';
{% endif %}

// SMTP configuration, see also relevant hosting module install hook.
$conf["smtp_client_hostname"] = "{{smtp_client_hostname}}";
$conf["smtp_password"] = "{{smtp_password}}";

// Redirect URLs that include a p1 to path version if site is launched.
if (isset($launched) && $launched && isset($conf["cu_path"])) {
  if (strpos($_SERVER['REQUEST_URI'], $conf['cu_sid']) !== false) {
    header('HTTP/1.0 301 Moved Permanently');
    header('Location: {{base_url}}' . str_replace($conf['cu_sid'], $conf["cu_path"], $_SERVER['REQUEST_URI']));
    exit();
  }
}
/**
 * Cookies
 *
 * Drupal generates a unique session cookie name for each site based on its full domain name.
 * Since we want different cookies per environment, we need to specify that here.
 * Make sure to always start the $cookie_domain with a leading dot, as per RFC 2109.
 * We also set the cookie path so that we don't bypass Varnish for instances we are not logged into.
 */
global $base_url;
$base_url .= '{{base_url}}';
$cookie_domain = '.{{domain}}';
// We don't need a cookie_domain for locals.
ini_set('session.cookie_lifetime', 93600);
{% if path != 'homepage' -%}
ini_set('session.cookie_path', '/' . $conf["cu_path"]);
$base_url .= '/' . $conf["cu_path"];
{% else -%}
ini_set('session.cookie_path', '/');
{% endif -%}

$host = $_SERVER['HTTP_HOST'];

/*
 * Caching and performance
 */
// Compress cached pages always off; we use mod_deflate
$conf['page_compression'] = 0;
// Caching across all of Express.
$conf['cache'] = 1;
// @todo Solve js inclusion issues to re-enable block cache.
// @see #attached.
$conf['block_cache'] = 0;
// Aggregate css and js files.
$conf['preprocess_css'] = TRUE;
$conf['preprocess_js'] = TRUE;
// Min cache lifetime 0, max defaults to 300 seconds.
$conf['cache_lifetime'] = 0;
$conf['page_cache_maximum_age'] = {{ page_cache_maximum_age }};
// Drupal doesn't cache if we invoke hooks during bootstrap.
$conf['page_cache_invoke_hooks'] = FALSE;
// Setup cache_form bin.
$conf['cache_default_class'] = 'MemCacheDrupal';
$conf['cache_class_cache_form'] = 'DrupalDatabaseCache';
// Memcache lock file location.
$conf['lock_inc'] = 'profiles/{{profile}}/modules/contrib/memcache/memcache-lock.inc';
$conf['cache_backends'] = array(
{% if environment != 'local' %}
  'profiles/{{profile}}/modules/contrib/varnish/varnish.cache.inc',
{% endif -%}
  'profiles/{{profile}}/modules/contrib/memcache/memcache.inc',
);
{% if environment != 'local' %}
// Varnish
$conf['reverse_proxy'] = TRUE;
$conf['reverse_proxy_addresses'] = array({% for ip in reverse_proxies -%}'{{ip}}',{% endfor %});
// Drupal will look for IP in $_SERVER['X-Forwarded-For']
$conf['reverse_proxy_header'] = 'X-Forwarded-For';
// Define Varnish Server Pool and version.
$conf['varnish_control_terminal'] = '{{ varnish_control }}';
$conf['varnish_version'] = 4;
$conf['varnish_control_key'] = '{{ varnish_control_key }}';
{%- endif %}
// Memcache bins and stampede protection.
$conf['memcache_bins'] = array('cache' => 'default');
$conf['memcache_key_prefix'] = $conf['cu_sid'];
// Set to FALSE on Jan 5, 2012 - drastically improved performance.
$conf['memcache_stampede_protection'] = FALSE;
$conf['memcache_stampede_semaphore'] = 15;
$conf['memcache_stampede_wait_time'] = 5;
$conf['memcache_stampede_wait_limit'] = 3;
// Put into to fix issue that we think might be related to hashing the persistent connections with
// the localhost haproxy setup.
$conf['memcache_persistent'] = FALSE;
// Never allow updating modules through UI.
$conf['allow_authorize_operations'] = FALSE;
// No IP blocking from the UI, we'll take care of that at a higher level.
$conf['blocked_ips'] = array();
// Disable poorman cron.
$conf['cron_safe_threshold'] = 0;
{% if environment in ['local','dev'] -%}
$conf['drupal_http_request_fails'] = FALSE;
{%- endif %}

{% if environment == 'local' -%}
$conf['error_level'] = 2;
{%- endif %}
$conf['file_temporary_path'] = '{{ tmp_path }}';

{% if environment != 'local' -%}
$databases['default']['default'] = array(
  'driver' => 'mysql',
  'database' => '{{ sid }}',
  'username' => '{{ sid }}',
  'password' => '{{ pw }}',
  'host' => '127.0.0.1',
  'port' => '3306',
  'prefix' => '',
);
// Define our slave database(s)
$databases['default']['slave'][] = array(
  'driver' => 'mysql',
  'database' => '{{ sid }}',
  'username' => '{{ sid }}',
  'password' => '{{ pw }}',
  'host' => '127.0.0.1',
  'port' => '3307',
  'prefix' => '',
);
// Memcache servers
$conf['memcache_servers'] = array(
  '127.0.0.1:11211' => 'default',
  '127.0.0.1:11212' => 'default',
);
{% else -%}
$databases['default']['default'] = array(
  'driver' => 'mysql',
  'database' => '{{ sid }}',
  'username' => '{{ sid }}',
  'password' => '{{ pw }}',
  'host' => 'localhost',
  'port' => '{{ port }}',
  'prefix' => '',
);

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
$conf['memcache_servers'] = array(
  '127.0.0.1:11211' => 'default',
);
{%- endif %}

// SAML DB
$databases['saml']['default'] = array(
  'driver' => 'mysql',
  'database' => 'saml',
  'username' => 'saml',
  'password' => '{{ saml_pw }}',
  'host' => '127.0.0.1',
  'port' => '3306',
  'prefix' => '',
);
