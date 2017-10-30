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
$conf["atlas_status"] = "{{status}}";
$conf["atlas_statistics_id"] = "{{atlas_statistics_id}}";

$conf["siteimprove_site"] = "{{siteimprove_site}}";
$conf["siteimprove_group"] = "{{siteimprove_group}}";


{% if google_cse_csx %}
$conf["google_cse_cx"] = "{{google_cse_csx}}";
{% else %}
$conf["google_cse_cx"] = NULL;
{% endif %}



$path = "{{path}}";
$pool = "{{pool}}";

{% if status in ['launched', 'launching'] %}
$launched = TRUE;
$conf["cu_path"] = "{{path}}";
{% else %}
$launched = FALSE;
{% endif %}
