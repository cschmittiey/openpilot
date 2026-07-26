# Device install & recovery

## Installing this fork

On a comma 3/3X, during setup choose **Custom Software** and enter:

```
installer.comma.ai/cschmittiey/main
```

The device clones `github.com/cschmittiey/openpilot` at branch `main` with
submodules and LFS, then builds it on first boot with scons (via
`openpilot/system/manager/build.py`). There is no prebuilt channel: every
device compiles the tree it pulls, so an unbuildable tip bricks every device
that updates to it.

## What fork-ci guarantees before devices can pull a commit

`.github/workflows/fork-ci.yml` runs on every push to `main` (and `claude/**`
dev branches), plus daily on a schedule, because most of these can rot with no
push to this repo:

- **Submodule pins fetchable** — every gitlink exists on its remote and every
  branch named in `.gitmodules` exists. (The opendbc pin once tracked a
  deleted branch, which silently broke installs and the device updater for
  months.)
- **Device build** — the tree compiles via the exact entrypoint the device
  runs at boot, then manager smoke tests run.
- **Fresh install** — an anonymous (credential-less) clone with recursive
  submodules and `git lfs pull` succeeds, and no LFS pointer files remain.
  Catches private submodules and missing LFS objects that authenticated CI
  checkouts would hide.
- **AGNOS image URLs reachable** — fresh installs flash the OS images pinned
  in `openpilot/system/hardware/tici/agnos.json` from comma's CDN; dead URLs
  fail installs mid-flash.

## Recovering a device stuck on "openpilot failed to build"

That screen (compiler output + a Reboot button) means the on-device scons
build fails at boot. Rebooting will not help — the build fails identically
every time. Known cause on this fork: a device that sat un-updatable during
the broken-pins era can be left with a stale checkout and a stale/partial
generated header (`cereal/gen/cpp/log.capnp.h` missing `cereal::Event`),
which scons keeps treating as up to date.

SSH in (comma key setup: https://github.com/commaai/openpilot/wiki/SSH) and
capture the state first:

```bash
cd /data/openpilot
git log -1 --oneline; git status | head; git submodule status
df -h /data
```

Then reset to a clean current tree — the `git clean` is the part that
actually cures the stale-artifact case by deleting `gen/` output and
`.sconsign.dblite`:

```bash
cd /data/openpilot
git fetch origin main && git reset --hard origin/main
git submodule sync --recursive && git submodule update --init --recursive --force
git clean -xdff && sudo reboot
```

No SSH available: reinstall via the installer URL above (factory reset from
the setup screen if needed). If `/data` was full, delete old routes in
`/data/media/0/realdata` before rebuilding.
