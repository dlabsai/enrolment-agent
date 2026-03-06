This directory contains **requirements-only specifications** for core app behavior
The specs are written so an AI (or engineer) can recreate the current behavior and API surface without reading the implementation

Guidelines:
- Describe **what** the system must do, not how it is implemented
- Include role/permission rules, error responses, and edge cases
- Keep specs in sync with the codebase; update specs alongside behavior changes
- Tooling-only changes should be documented outside this directory
- Specs are authoritative for expected behavior
