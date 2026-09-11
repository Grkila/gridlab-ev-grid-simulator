# Source rules

- Use package-relative imports within a package and `mvgrid.paths` for repository locations.
- Do not open configuration or data through current-working-directory-relative paths.
- Keep `legacy` behavior compatible; put new Novi Sad behavior in `novi_sad`.
- Avoid import-time network calls and filesystem writes.
- Run syntax/import tests and the relevant integration workflow after changes.
