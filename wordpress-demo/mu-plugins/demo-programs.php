<?php
/**
 * Plugin Name: Demo Programs Post Type
 * Description: Registers the programs post type for demo WordPress data.
 */

declare(strict_types=1);

add_action('init', function (): void {
    register_post_type('programs', [
        'labels' => [
            'name' => 'Programs',
            'singular_name' => 'Program',
        ],
        'public' => true,
        'has_archive' => true,
        'rewrite' => [
            'slug' => 'programs',
        ],
        'show_in_rest' => true,
        'rest_base' => 'programs',
        'hierarchical' => true,
        'show_in_nav_menus' => true,
        'supports' => [
            'title',
            'editor',
            'excerpt',
            'page-attributes',
            'thumbnail',
        ],
    ]);
});
