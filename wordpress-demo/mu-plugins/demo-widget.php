<?php
/**
 * Plugin Name: Demo Chat Widget
 * Description: Injects the public chat widget script into demo WordPress pages.
 */

declare(strict_types=1);

add_action('wp_enqueue_scripts', function (): void {
    if (is_admin()) {
        return;
    }

    $script_url = getenv('WORDPRESS_WIDGET_SCRIPT_URL');
    if ($script_url === false || $script_url === '') {
        $script_url = 'http://localhost:8000/public/chat-widget.js';
    }

    wp_enqueue_script('va-demo-widget', $script_url, [], null, [
        'in_footer' => true,
        'strategy' => 'defer',
    ]);
});
