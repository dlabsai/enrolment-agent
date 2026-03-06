#!/usr/bin/env bash

set -euo pipefail

SCRIPT_NAME=$(basename "${BASH_SOURCE[0]}")
ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
BACKEND_DIR="${ROOT_DIR}/backend"
CONTENT_DIR="${ROOT_DIR}/wordpress-demo/content"
PAGES_DIR="${CONTENT_DIR}/pages"
PROGRAMS_DIR="${CONTENT_DIR}/programs"

COMPOSE_CMD=${COMPOSE_CMD:-"docker compose"}
COMPOSE_IGNORE_ORPHANS=${COMPOSE_IGNORE_ORPHANS:-1}
COMPOSE_PROGRESS=${COMPOSE_PROGRESS:-quiet}
export COMPOSE_IGNORE_ORPHANS COMPOSE_PROGRESS

WP_URL=${WP_DEMO_URL:-"http://localhost:8080"}
PROFILE=${WP_DEMO_PROFILE:-"wp-demo"}
SITE_TITLE=${WP_DEMO_TITLE:-"Demo University"}
ADMIN_USER=${WP_DEMO_ADMIN_USER:-admin}
ADMIN_PASSWORD=${WP_DEMO_ADMIN_PASSWORD:-admin}
ADMIN_EMAIL=${WP_DEMO_ADMIN_EMAIL:-admin@example.com}
WP_PATH=${WP_DEMO_PATH:-/var/www/html}
FORCE_SEED=${WP_DEMO_FORCE_SEED:-0}
DB_NAME=${WP_DEMO_DB_NAME:-wordpress}
DB_USER=${WP_DEMO_DB_USER:-wordpress}
DB_PASSWORD=${WP_DEMO_DB_PASSWORD:-wordpress}
DB_ROOT_PASSWORD=${WP_DEMO_DB_ROOT_PASSWORD:-wordpress}

VERBOSE=0
QUIET=0
NO_INPUT=0
FORCE=0
SEED_ONLY=0
RAG_ONLY=0
COMMAND="all"

usage() {
  cat <<EOF
Usage: ${SCRIPT_NAME} [options] [command]

Commands:
  up      Start WordPress demo services
  seed    Seed WordPress demo content
  rag     Build RAG data from WordPress
  reset   Reset WordPress and rebuild RAG
  all     Run full demo setup (default)

Options:
  -v, --verbose         Enable verbose output
  -q, --quiet           Minimize output
  --no-input            Disable prompts
  --force               Force destructive actions
  --wp-url URL          WordPress base URL (default: ${WP_URL})
  --profile PROFILE     Docker compose profile (default: ${PROFILE})
  --compose-cmd CMD     Docker compose command (default: "${COMPOSE_CMD}")
  --seed-only           Run WordPress seed only (for "all")
  --rag-only            Run RAG build only (for "all")
  --version             Print version and exit
  -h, --help            Show this help message
EOF
}

die() {
  local message=$1
  local code=${2:-1}
  echo "${message}" >&2
  exit "${code}"
}

run_command() {
  local description=$1
  local exit_code=$2
  shift 2
  local cmd=("$@")

  if (( VERBOSE )); then
    printf '$'
    printf ' %q' "${cmd[@]}"
    printf '\n'
  fi

  local status=0
  if (( QUIET )); then
    "${cmd[@]}" >/dev/null 2>&1 || status=$?
  else
    "${cmd[@]}" || status=$?
  fi

  if (( status != 0 )); then
    echo "${description} failed with exit code ${status}." >&2
    exit "${exit_code}"
  fi
}

run_command_in_dir() {
  local dir=$1
  local description=$2
  local exit_code=$3
  shift 3
  local cmd=("$@")

  if (( VERBOSE )); then
    printf '$'
    printf ' %q' "${cmd[@]}"
    printf '\n'
  fi

  local status=0
  if (( QUIET )); then
    (cd "${dir}" && "${cmd[@]}" >/dev/null 2>&1) || status=$?
  else
    (cd "${dir}" && "${cmd[@]}") || status=$?
  fi

  if (( status != 0 )); then
    echo "${description} failed with exit code ${status}." >&2
    exit "${exit_code}"
  fi
}

run_wp() {
  ${COMPOSE_CMD} --profile "${PROFILE}" exec -T wp-cli \
    wp --path="${WP_PATH}" --allow-root "$@"
}

reset_wp_db() {
  ${COMPOSE_CMD} --profile "${PROFILE}" exec -T wp-db \
    mysql -uroot -p"${DB_ROOT_PASSWORD}" -e \
    "DROP DATABASE IF EXISTS \`${DB_NAME}\`; \
     CREATE DATABASE \`${DB_NAME}\`; \
     GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'%'; \
     FLUSH PRIVILEGES;"
}

md_title() {
  local file=$1
  if [[ ! -f "${file}" ]]; then
    echo "Missing content file: ${file}" >&2
    exit 1
  fi

  local title
  title=$(awk 'NR==1 && /^#[[:space:]]+/ {sub(/^#[[:space:]]+/, ""); sub(/[[:space:]]+$/, ""); print; exit}' "${file}")
  if [[ -n "${title}" ]]; then
    printf '%s\n' "${title}"
    return 0
  fi

  local stem
  stem=$(basename "${file}" .md)
  local label
  label=$(printf '%s' "${stem}" | tr '_-' ' ' | awk '{$1=$1; print}')
  if [[ -n "${label}" ]]; then
    title=$(printf '%s' "${label}" | awk '{for (i=1;i<=NF;i++) {$i=toupper(substr($i,1,1)) tolower(substr($i,2))} print}')
    printf '%s\n' "${title}"
  else
    printf '%s\n' "${stem}"
  fi
}

md_to_html() {
  local file=$1
  if [[ ! -f "${file}" ]]; then
    echo "Missing content file: ${file}" >&2
    exit 1
  fi

  awk 'NR==1 && /^#[[:space:]]+/ {next} {print}' "${file}" | \
    uvx --from markdown python -m markdown
}

ensure_wp_config() {
  if ! run_wp config path >/dev/null 2>&1; then
    run_wp config create \
      --dbname=wordpress \
      --dbuser=wordpress \
      --dbpass=wordpress \
      --dbhost=wp-db:3306 \
      --skip-check \
      --force >/dev/null
  fi
}

upsert_post() {
  local post_type=$1
  local slug=$2
  local title=$3
  local content=$4
  local excerpt=${5:-}
  local parent_id=${6:-}
  local existing_id

  existing_id=$(run_wp post list --post_type="${post_type}" --name="${slug}" --field=ID --format=ids 2>/dev/null || true)

  if [[ -n "${existing_id}" ]]; then
    run_wp post update "${existing_id}" \
      --post_title="${title}" \
      --post_content="${content}" \
      --post_excerpt="${excerpt}" \
      ${parent_id:+--post_parent="${parent_id}"} \
      --post_status=publish >/dev/null
    echo "${existing_id}"
  else
    run_wp post create \
      --post_type="${post_type}" \
      --post_title="${title}" \
      --post_name="${slug}" \
      --post_content="${content}" \
      --post_excerpt="${excerpt}" \
      ${parent_id:+--post_parent="${parent_id}"} \
      --post_status=publish \
      --porcelain
  fi
}

add_menu_item() {
  local object_id=$1
  local title=$2
  if [[ -z "${object_id}" || -z "${title}" ]]; then
    return
  fi
  run_wp menu item add-post "${menu_name}" "${object_id}" --title="${title}" --porcelain >/dev/null
}

is_preferred_page() {
  local slug=$1
  for preferred in "${preferred_pages[@]}"; do
    if [[ "${preferred}" == "${slug}" ]]; then
      return 0
    fi
  done
  return 1
}

seed_wordpress_impl() {
  local force_seed=$1

  ${COMPOSE_CMD} --profile "${PROFILE}" up -d --quiet-pull wp-db wordpress wp-cli

  echo "Waiting for WordPress database..."

  attempts=0
  max_attempts=30
  until run_wp db query "SELECT 1" >/dev/null 2>&1; do
    attempts=$((attempts + 1))
    if (( attempts > max_attempts )); then
      echo "Timed out waiting for WordPress database."
      exit 1
    fi
    ensure_wp_config || true
    sleep 3
    echo "  still waiting..."
  done

  if [[ "${force_seed}" == "1" ]]; then
    reset_wp_db
  fi

  if ! run_wp core is-installed >/dev/null 2>&1; then
    run_wp core install \
      --url="${WP_URL}" \
      --title="${SITE_TITLE}" \
      --admin_user="${ADMIN_USER}" \
      --admin_password="${ADMIN_PASSWORD}" \
      --admin_email="${ADMIN_EMAIL}" \
      --skip-email
  fi

  sample_page_id=$(run_wp post list --post_type=page --name=sample-page --field=ID --format=ids 2>/dev/null || true)
  if [[ -n "${sample_page_id}" ]]; then
    run_wp post delete ${sample_page_id} --force >/dev/null
  fi

  sample_post_id=$(run_wp post list --post_type=post --name=hello-world --field=ID --format=ids 2>/dev/null || true)
  if [[ -n "${sample_post_id}" ]]; then
    run_wp post delete ${sample_post_id} --force >/dev/null
  fi

  if [[ "${force_seed}" != "1" ]]; then
    seeded_flag=$(run_wp option get va_demo_seeded 2>/dev/null || true)
    if [[ "${seeded_flag}" == "1" ]]; then
      echo "Demo content already seeded; skipping."
      exit 0
    fi
  fi

  run_wp option update blogdescription "Demo site for WP content ingestion" >/dev/null
  run_wp rewrite structure '/%postname%/' --hard >/dev/null
  run_wp rewrite flush --hard >/dev/null

  shopt -s nullglob

  declare -A page_titles
  page_slugs=()

  for file in "${PAGES_DIR}"/*.md; do
    slug=$(basename "${file}" .md)
    title=$(md_title "${file}")
    content=$(md_to_html "${file}")
    page_id=$(upsert_post page "${slug}" "${title}" "${content}")
    page_slugs+=("${slug}")
    page_titles["${slug}"]="${title}"
    if [[ "${slug}" == "home" ]]; then
      home_id="${page_id}"
    fi
  done

  if [[ -z "${home_id:-}" ]]; then
    echo "Home page not found in ${PAGES_DIR}." >&2
    exit 1
  fi

  run_wp option update show_on_front page >/dev/null
  run_wp option update page_on_front "${home_id}" >/dev/null
  run_wp option update page_for_posts 0 >/dev/null

  if [[ ! -f "${PAGES_DIR}/academic-programs.md" ]]; then
    echo "Missing academic-programs.md in ${PAGES_DIR}." >&2
    exit 1
  fi

  programs_parent_content=$(md_to_html "${PAGES_DIR}/academic-programs.md")
  programs_parent_id=$(upsert_post programs academic-programs "Academic Programs" "${programs_parent_content}" "")

  declare -A program_titles
  program_slugs=()

  for file in "${PROGRAMS_DIR}"/*.md; do
    slug=$(basename "${file}" .md)
    title=$(md_title "${file}")
    content=$(md_to_html "${file}")
    upsert_post programs "${slug}" "${title}" "${content}" "" "${programs_parent_id}"
    program_slugs+=("${slug}")
    program_titles["${slug}"]="${title}"
  done

  menu_name="Primary"
  menu_id=$(run_wp menu list --format=csv 2>/dev/null | awk -F, 'NR>1 && $2=="'"${menu_name}"'" {print $1; exit}')
  if [[ -z "${menu_id}" ]]; then
    menu_id=$(run_wp menu create "${menu_name}" --porcelain)
  fi

  menu_location=$(run_wp menu location list --format=csv 2>/dev/null | awk -F, 'NR>1 {print $1; exit}')
  if [[ -n "${menu_location}" ]]; then
    run_wp menu location assign "${menu_name}" "${menu_location}" >/dev/null || true
  fi

  existing_menu_items=$(run_wp menu item list "${menu_name}" --fields=ID --format=csv 2>/dev/null | tail -n +2 | tr -d '\r')
  if [[ -n "${existing_menu_items}" ]]; then
    for menu_item_id in ${existing_menu_items}; do
      run_wp menu item delete "${menu_item_id}" --force >/dev/null
    done
  fi

  run_wp option update nav_menu_options '{"auto_add":[]}' --format=json >/dev/null || true

  preferred_pages=(
    home
    academics
    academic-programs
    admissions
    financial-aid
    student-life
    contact
    academic-calendar
    learning-formats
  )

  ordered_pages=()

  for slug in "${preferred_pages[@]}"; do
    ordered_pages+=("${slug}")
    title=${page_titles["${slug}"]:-}
    object_id=$(run_wp post list --post_type=page --name="${slug}" --field=ID --format=ids 2>/dev/null || true)
    add_menu_item "${object_id}" "${title}"
  done

  for slug in "${page_slugs[@]}"; do
    if ! is_preferred_page "${slug}"; then
      ordered_pages+=("${slug}")
      title=${page_titles["${slug}"]:-}
      object_id=$(run_wp post list --post_type=page --name="${slug}" --field=ID --format=ids 2>/dev/null || true)
      add_menu_item "${object_id}" "${title}"
    fi
  done

  menu_order=1
  for slug in "${ordered_pages[@]}"; do
    object_id=$(run_wp post list --post_type=page --name="${slug}" --field=ID --format=ids 2>/dev/null || true)
    if [[ -n "${object_id}" ]]; then
      run_wp post update "${object_id}" --menu_order="${menu_order}" >/dev/null
    fi
    menu_order=$((menu_order + 1))
  done

  for slug in "${program_slugs[@]}"; do
    title=${program_titles["${slug}"]:-}
    object_id=$(run_wp post list --post_type=programs --name="${slug}" --field=ID --format=ids 2>/dev/null || true)
    add_menu_item "${object_id}" "${title}"
  done

  run_wp option update va_demo_seeded 1 >/dev/null

  echo "Seeded demo WordPress content."
}

start_wordpress() {
  local -a compose_cmd
  read -r -a compose_cmd <<< "${COMPOSE_CMD}"
  compose_cmd+=(--profile "${PROFILE}" up -d --quiet-pull wp-db wordpress wp-cli)
  run_command "Starting WordPress services" 5 "${compose_cmd[@]}"
}

seed_wordpress() {
  local force=${1:-${FORCE}}
  local force_seed=${FORCE_SEED}

  if (( force )); then
    force_seed=1
  fi

  set +e
  ( set -euo pipefail; seed_wordpress_impl "${force_seed}" )
  local status=$?
  set -e

  if (( status != 0 )); then
    echo "WordPress seed failed with exit code ${status}." >&2
    exit 3
  fi
}

build_rag() {
  local force=${1:-${FORCE}}
  local -a env_cmd=(
    env
    "WORDPRESS_MIRROR_URL=${WP_URL}"
    "WORDPRESS_WEBSITE_URL=${WP_URL}"
  )

  run_command_in_dir "${BACKEND_DIR}" "WordPress data fetch" 4 \
    "${env_cmd[@]}" uv run -m app.rag.wordpress.cli
  run_command_in_dir "${BACKEND_DIR}" "WordPress data transform" 4 \
    "${env_cmd[@]}" uv run -m app.rag.transform.transform_wp_data

  local -a build_cmd=(uv run -m app.rag.build)
  if (( force )); then
    build_cmd+=(--force-rebuild)
  fi
  run_command_in_dir "${BACKEND_DIR}" "RAG build" 4 \
    "${env_cmd[@]}" "${build_cmd[@]}"
}

confirm_reset() {
  if (( FORCE )); then
    return 0
  fi
  if (( NO_INPUT )); then
    die "Reset requires --force when running non-interactively." 2
  fi
  if [[ ! -t 0 ]]; then
    die "Reset requires --force when running non-interactively." 2
  fi
  read -r -p "Reset WordPress and rebuild RAG? [y/N]: " response
  response=${response,,}
  [[ "${response}" == "y" || "${response}" == "yes" ]]
}

run_all() {
  if (( SEED_ONLY && RAG_ONLY )); then
    die "Use --seed-only or --rag-only, not both." 2
  fi

  if (( RAG_ONLY )); then
    build_rag
    return
  fi
  if (( SEED_ONLY )); then
    seed_wordpress
    return
  fi

  start_wordpress
  seed_wordpress
  build_rag
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -v|--verbose)
      VERBOSE=1
      ;;
    -q|--quiet)
      QUIET=1
      ;;
    --no-input)
      NO_INPUT=1
      ;;
    --force)
      FORCE=1
      ;;
    --wp-url)
      shift
      [[ $# -gt 0 ]] || die "--wp-url requires a value." 2
      WP_URL=$1
      ;;
    --profile)
      shift
      [[ $# -gt 0 ]] || die "--profile requires a value." 2
      PROFILE=$1
      ;;
    --compose-cmd)
      shift
      [[ $# -gt 0 ]] || die "--compose-cmd requires a value." 2
      COMPOSE_CMD=$1
      ;;
    --seed-only)
      SEED_ONLY=1
      ;;
    --rag-only)
      RAG_ONLY=1
      ;;
    --version)
      echo "va-demo (dev)"
      exit 0
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    up|seed|rag|reset|all)
      COMMAND=$1
      ;;
    *)
      die "Unknown argument: $1" 2
      ;;
  esac
  shift
done

if (( QUIET && VERBOSE )); then
  die "Use either --quiet or --verbose, not both." 2
fi

if [[ "${COMMAND}" != "all" ]] && (( SEED_ONLY || RAG_ONLY )); then
  die "--seed-only/--rag-only are only valid with the 'all' command." 2
fi

case "${COMMAND}" in
  up)
    start_wordpress
    ;;
  seed)
    seed_wordpress
    ;;
  rag)
    build_rag
    ;;
  reset)
    if confirm_reset; then
      start_wordpress
      seed_wordpress 1
      build_rag 1
    else
      echo "Reset canceled."
    fi
    ;;
  all)
    run_all
    ;;
  *)
    die "Unknown command: ${COMMAND}" 2
    ;;
esac
