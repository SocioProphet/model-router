# Release Dry Run

`model-router` supports a development release dry-run path.

## Command

```bash
make release-dry-run
```

The command emits:

- `dist/model-router.release-dry-run.json`
- `dist/model-router.release-dry-run.sha256`

## Current status

This is a local development artifact path. It does not publish a production release and does not update a stable Homebrew artifact formula.

## Promotion requirements

A stable formula path requires:

- versioned GitHub Release;
- immutable artifact URL;
- sha256 checksum;
- SBOM;
- provenance metadata;
- formula tests.

Until those exist, `homebrew-prophet` should keep `model-router` as a source-built development formula.
