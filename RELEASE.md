# Release Guide

This document describes how to prepare and publish a StableSteering release.

## Release Artifacts

A release should include:

- tagged source in Git
- release notes
- installation instructions
- published HTML documentation
- optional packaged zip artifact
- updated user/developer docs for async jobs, trace reports, and example bundles

Current release notes:

- [RELEASE_NOTES_v0.1.0.md](RELEASE_NOTES_v0.1.0.md)

## Release Checklist

1. Confirm the working tree is clean.
2. Run backend tests:
   `python -m pytest`
3. Run default browser tests:
   `npm run test:e2e:chrome`
4. If releasing from a CUDA-capable machine, optionally run:
   `python scripts/smoke_real_diffusers.py`
5. If releasing from a CUDA-capable machine, optionally refresh the real example bundle:
   `python scripts/create_real_e2e_example.py`
6. Rebuild the documentation site:
   `python scripts/build_pages_site.py`
7. Review:
   - [INSTALL.md](INSTALL.md)
   - [README.md](README.md)
   - [docs/student_tutorial.md](docs/student_tutorial.md)
   - [RELEASE_NOTES_v0.1.0.md](RELEASE_NOTES_v0.1.0.md)
8. Build a source zip if needed:
   `powershell -ExecutionPolicy Bypass -File scripts/build_release_zip.ps1 -Version v0.1.0`
9. Create the Git tag.
10. Push the tag and upload the zip if desired.

## Suggested Tagging Flow

```powershell
git tag v0.1.0
git push origin v0.1.0
```

## Build the Optional Zip Artifact

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_release_zip.ps1 -Version v0.1.0
```

The zip is written to `output/releases/`.

## Release Scope

The current release line is a research-oriented MVP. It is suitable for local development, evaluation, teaching, and architectural review, but not intended as a production deployment package.
