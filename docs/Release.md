# Release
Everything can be build via GitHub workflows, directly on the server/client or via chroot. Preferably we just use Github workflows to build everything, but quotas are in place and during development it might be easier and more efficient to build on the server/client itself.

## Chroot
Probably the most convenient way to bundle everything up on your (Linux) dev machine. Start by installing the dependencies:

```bash
sudo ./build/prepare-host.sh
```

Now you can run the build script which builds the deb files:

```bash
sudo ./build/build-in-chroot.sh
```

This will build python only once, but will keep re-building the `v3xctrl` package. After build the deb files will be moved into place for building the image:

```bash
./build/customize-image.sh
```

After that you can find the custom image in `./build/tmp/v3xctrl.img.xz`.

## Locally

### Client
Once packages are built, they can be found in `./build/tmp/*.deb`

#### Python
this will install all dependencies, and build the python package on the client itself:

```bash
./bash/install.sh python
```

#### v3xctrl
This will install dependencies and build v3xctrl on the client itself:

```bash
./bash/install.sh update
```

#### Image
Base image, deb packages for python and v3xctrl need to be in place. Also a directory to mount everything needs to be in place, then run:

```bash
./build/customize-image.sh ./build/tmp/mnt ./build/tmp/dependencies/raspios-bullseye-arm64-lite.img.xz ./build/tmp/dependencies/debs ./build/tmp/v3xctrl-raspios.img.xz
```

> **NOTE**: the image builder script is meant to be run on the server, it uses chroot and qemu. Technically you can also run it on the client and then simply skip copying qemu static.

## Github Workflows
### Server
This one is straight forward, new artifact are built on every push and PR.

When creating a new release, just attach the latest builds to the release.

TODO: This can probably also be done automatically when tagging

### Client
Client is a bit more complicated:

#### Python
Build of custom python version can be triggered manually. This should not be necessary too often, unless we need to upgrade to a new specific version for some reason.

This will result in an artifact with a deb file, attach that to the latest release.

TODO: as above - do this automatically when tagging

#### v3xctrl
Build of v3xctrl can be triggered manually.

This will result in an artifact with a deb file, attach that to the latest release.

TODO: as above - do this automatically when tagging
TODO: This does not take too long to build, we could consider building this on every push and PR too.


### Image
Building of the custom PiOS image is triggered manually. This will use the `deb` packages attached to the latest release. Once the image is built, it can be attached to the latest release.

TODO: as above - do this automatically when tagging
