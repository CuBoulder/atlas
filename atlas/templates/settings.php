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
$conf["install_profile"] = "{{profile}}";
$conf["cu_sid"] = "{{sid}}";

$conf["atlas_id"] = "{{atlas_id}}";
$conf["atlas_url"] = "{{atlas_url}}";
$conf["atlas_username"] = "{{atlas_username}}";
$conf["atlas_password"] = "{{atlas_password}}";
$conf["atlas_status"] = "{{status}}";
$conf["atlas_statistics_id"] = "{{atlas_statistics_id}}";
$conf["atlas_logging_url"] = "{{atlas_logging_url|join(sid)}}";
{% if google_cse_csx %}
$conf["google_cse_cx"] = "{{google_cse_csx}}";
{% else %}
$conf["google_cse_cx"] = NULL;
{% endif %}
$path = "{{path}}";

{% if status in ['launched', 'launching'] %}
$launched = TRUE;
$conf["cu_path"] = "{{path}}";
{% else %}
$launched = FALSE;
{% endif %}

if (isset($launched) && $launched && isset($conf["cu_path"])) {
  if (isset($_SERVER['OSR_ENV'])) {
    if ($_SERVER['OSR_ENV'] == 'prod' &&
      strpos($_SERVER['REQUEST_URI'], $conf['cu_sid']) !== false) {
      header('HTTP/1.0 301 Moved Permanently');
      header('Location: https://www-https.colorado.edu'. str_replace($conf['cu_sid'], $conf["cu_path"], $_SERVER['REQUEST_URI']));
      exit();
    }
    elseif ($_SERVER['OSR_ENV'] == 'test' &&
      strpos($_SERVER['REQUEST_URI'], $conf['cu_sid']) !== false) {
      header('HTTP/1.0 301 Moved Permanently');
      header('Location: https://www-test-https.colorado.edu'. str_replace($conf['cu_sid'], $conf["cu_path"], $_SERVER['REQUEST_URI']));
      exit();
    }
    elseif ($_SERVER['OSR_ENV'] == 'dev' &&
      strpos($_SERVER['REQUEST_URI'], $conf['cu_sid']) !== false) {
      header('HTTP/1.0 301 Moved Permanently');
      header('Location: https://www-dev-https.colorado.edu'. str_replace($conf['cu_sid'], $conf["cu_path"], $_SERVER['REQUEST_URI']));
      exit();
    }
    elseif ($_SERVER['OSR_ENV'] == 'local' &&
      strpos($_SERVER['REQUEST_URI'], $conf['cu_sid']) !== false) {
      header('HTTP/1.0 301 Moved Permanently');
      header('Location: https://express.local'. str_replace($conf['cu_sid'], $conf["cu_path"], $_SERVER['REQUEST_URI']));
      exit();
    }
  }
}

$host = $_SERVER['HTTP_HOST'];

// Compress cached pages always off; we use mod_deflate
$conf['page_compression'] = 0;

// Never allow updating modules through UI.
$conf['allow_authorize_operations'] = FALSE;

// Caching across all of Express.
$conf['cache'] = 1;
// @todo Solve js inclusion issues to re-enable block cache.
// @see #attached.
$conf['block_cache'] = 0;

// Aggregate css and js files.
$conf['preprocess_css'] = TRUE;
$conf['preprocess_js'] = TRUE;

// Drupal doesn't cache if we invoke hooks during bootstrap.
$conf['page_cache_invoke_hooks'] = FALSE;

{% if environment != 'local' %}
// Varnish Backends.
$conf['cache_backends'] = array(
  'profiles/{{profile}}/modules/contrib/varnish/varnish.cache.inc',
);
{% endif %}

// Setup cache_form bin.
$conf['cache_class_cache_form'] = 'DrupalDatabaseCache';

// Disable poorman cron.
$conf['cron_safe_threshold'] = 0;

// No IP blocking from the UI, we'll take care of that at a higher level.
$conf['blocked_ips'] = array();

if (isset($_SERVER['OSR_ENV'])) {
  global $base_url;

  /**
   * Drupal automatically generates a unique session cookie name for each site
   * based on its full domain name. Since we want different cookies per
   * environment, we need to specify that here. Make sure to always start the
   * $cookie_domain with a leading dot, as per RFC 2109. We also set the
   * cookie path so that we don't bypass Varnish for instances we are not
   * logged into.
   */
  switch($_SERVER['OSR_ENV']) {
    case 'prod':
      $base_url .= 'https://www-https.colorado.edu';
      $cookie_domain = '.www-https.colorado.edu';
      break;
    case 'test':
      $base_url .= 'https://www-test-https.colorado.edu';
      $cookie_domain = '.www-test-https.colorado.edu';
      break;
    case 'dev':
      $base_url .= 'https://www-dev-https.colorado.edu';
      $cookie_domain = '.www-dev-https.colorado.edu';
      break;
    case 'express_local':
      $base_url .= 'https://express.local';
      // We don't need a cookie_domain for locals.
      break;
  }
  ini_set('session.cookie_lifetime', 93600);
  ini_set('session.cookie_path', '/' . $path);
{% if site_type == 'express' %}  $base_url .= '/' . $path;{% endif %}
}

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
{% endif %}

{% if environment in ['local','dev'] %}$conf['drupal_http_request_fails'] = FALSE;{% endif %}
// Google Analytics
$conf['googleanalytics_account'] = 'UA-25752450-1';

{% if environment == 'local' %}$conf['error_level'] = 2;{% endif %}

$conf['file_temporary_path'] = '/tmp';

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
