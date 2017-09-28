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
$local_pre_settings = dirname(__FILE__) . '/settings.local_pre.php';
if (file_exists($local_pre_settings)) {
  include $local_pre_settings;
}

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

// Memcache and Varnish Backends.
$conf['cache_backends'] = array(
  'profiles/{{profile}}/modules/contrib/varnish/varnish.cache.inc',
  'profiles/{{profile}}/modules/contrib/memcache/memcache.inc',
);

// Memcache lock file location.
$conf['lock_inc'] = 'profiles/{{profile}}/modules/contrib/memcache/memcache-lock.inc';

// Setup cache_form bin.
$conf['cache_class_cache_form'] = 'DrupalDatabaseCache';

// Set varnish as the page cache.
$conf['cache_class_cache_page'] = 'VarnishCache';

// Set memcache as default.
$conf['cache_default_class'] = 'MemCacheDrupal';

// Memcache bins and stampede protection.
$conf['memcache_bins'] = array('cache' => 'default');

// Set to FALSE on Jan 5, 2012 - drastically improved performance.
$conf['memcache_stampede_protection'] = FALSE;
$conf['memcache_stampede_semaphore'] = 15;
$conf['memcache_stampede_wait_time'] = 5;
$conf['memcache_stampede_wait_limit'] = 3;

// Disable poorman cron.
$conf['cron_safe_threshold'] = 0;

// No IP blocking from the UI, we'll take care of that at a higher level.
$conf['blocked_ips'] = array();

// Enable the environment indicator.
$conf['environment_indicator_enabled'] = TRUE;

if (isset($_SERVER['OSR_ENV'])) {
  global $base_url;

  switch($_SERVER['OSR_ENV']) {
    case 'prod':
      $base_url .= 'https://www-https.colorado.edu';
      break;
    case 'test':
      $base_url .= 'https://www-test-https.colorado.edu';
      break;
    case 'dev':
      $base_url .= 'https://www-dev-https.colorado.edu';
      break;
    case 'express_local':
      $base_url .= 'https://express.local';
      break;
  }

  if ($atlas_type = "express") {
    $base_url .= '/' . $path;
  }
}

// Memcache
$conf['memcache_key_prefix'] = $conf['cu_sid'];
{% if environment != 'local' %}
$conf['memcache_servers'] = array(
  {% for ip in memcache_servers -%}
  '{{ip}}' => 'default',
  {% endfor %}
);
{% endif %}


// Varnish
$conf['reverse_proxy'] = TRUE;
$conf['reverse_proxy_addresses'] = array({% for ip in reverse_proxies -%}'{{ip}}',{% endfor %});
// Drupal will look for IP in $_SERVER['X-Forwarded-For']
$conf['reverse_proxy_header'] = 'X-Forwarded-For';
// Define Varnish Server Pool and version.
$conf['varnish_control_terminal'] = '{{ varnish_control }}';
$conf['varnish_version'] = 4;
$conf['varnish_control_key'] = '{{ varnish_control_key }}';

{% if environment == 'dev' %}
  $conf['drupal_http_request_fails'] = FALSE;
{% endif %}

// Google Analytics
$conf['googleanalytics_account'] = 'UA-25752450-1';

{% if environment == 'local' %}
$conf['error_level'] = 2;
{% endif %}

$conf['file_temporary_path'] = '/tmp';

/**
 * Include a post local settings file if it exists.
 */
$local_post_settings = dirname(__FILE__) . '/settings.local_post.php';
if (file_exists($local_post_settings)) {
  include $local_post_settings;
}
