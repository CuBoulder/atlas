<?php
/**
 * @file
 * Drupal site-specific configuration file.
 *
 * We include a pre and post local file so that we can set variables for the
 * main file and override config as needed.
 */
global $conf;
$conf["install_profile"] = "{{profile}}";
$conf["cu_sid"] = "{{sid}}";


$conf["atlas_id"] = "{{atlas_id}}";
$conf["atlas_url"] = "{{atlas_url}}";
$conf["atlas_username"] = "{{atlas_username}}";
$conf["atlas_password"] = "{{atlas_password}}";

$path = "{{path}}";
$pool = "{{pool_full}}";

{% if status in ['launched', 'launching'] %}
$launched = TRUE;
$conf["cu_path"] = "{{ path }}";
{% else %}
$launched = FALSE;
{% endif %}
