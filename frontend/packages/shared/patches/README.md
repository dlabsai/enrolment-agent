# patches/

This folder contains `patch-package` patches applied after `npm install`.

## Why these patches exist

The public chat widget renders inside a Shadow DOM. Radix Dialog/AlertDialog include runtime accessibility warnings that use `document.getElementById(...)` to verify that `DialogTitle`/`DialogDescription` exist.

In a ShadowRoot, `document.getElementById(...)` cannot see elements inside the shadow tree, so these checks can false-positive and spam the console even when the markup is correct.

In the Radix versions used by this repo, the warning components are wired into `DialogContent`/`AlertDialogContent` unconditionally, so simply building for production does not guarantee they disappear.

To keep the console clean (and avoid misleading “missing title/description” messages), we patch Radix to stop rendering the warning components.

## How patches are applied

- `patch-package` is installed as a dev dependency.
- `npm` runs `postinstall`, which executes `patch-package` and applies the patches automatically.

## Patches currently in use

- `@radix-ui/react-dialog` (disables Title/Description warnings)
- `@radix-ui/react-alert-dialog` (disables Description warning)

## Upgrading Radix

When upgrading `@radix-ui/*`:

1. Update the dependency version(s) intentionally.
2. Run `npm install`.
3. If `patch-package` fails, regenerate the patches:
    - `npx patch-package @radix-ui/react-dialog`
    - `npx patch-package @radix-ui/react-alert-dialog`
4. Rebuild and verify the console is clean in Firefox.

If Radix adds Shadow DOM-aware checks upstream, consider deleting these patches entirely.
