# Release
Everything can be build via GitHub workflows.

## Server
This one is straight forward, new artifact are built on every push and PR.

When creating a new release, just attach the latest builds to the release.

TODO: This can probably also be done automatically when tagging

## Client
Client is a bit more complicated:

### Python
Build of custom python version can be triggered manually. This should not be necessary too often, unless we need to upgrade to a new specific version for some reason.

This will result in an artifact with a deb file, attach that to the latest release.

TODO: as above - do this automatically when tagging

### v3xctrl
Build of v3xctrl can be triggered manually.

This will result in an artifact with a deb file, attach that to the latest release.

TODO: as above - do this automatically when tagging
TODO: This does not take too long to build, we could consider building this on every push and PR too.
