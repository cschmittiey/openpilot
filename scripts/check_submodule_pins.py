#!/usr/bin/env python3
"""Verify every submodule pin is fetchable from its remote and every branch
named in .gitmodules exists.

Guards against the fork failure class where a submodule pin becomes
un-fetchable: the opendbc submodule once pointed installs at a branch
(master-cma) that was later deleted, which broke installs and silently
blocked the device updater for months. Also catches pushing this repo with
a submodule pin that was never pushed to the submodule's remote.

For submodules that declare a branch in .gitmodules, additionally verifies
the pinned commit is reachable from that branch (not just present on the
remote), since installers clone single-branch.
"""
import posixpath
import subprocess
import sys
import tempfile
from urllib.parse import urlparse

ROOT = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()


def run(args, cwd=ROOT, check=True):
  return subprocess.run(args, cwd=cwd, check=check, capture_output=True, text=True)


def gitmodules() -> dict[str, dict[str, str]]:
  out = run(["git", "config", "-f", ".gitmodules", "--get-regexp", r"^submodule\."]).stdout
  mods: dict[str, dict[str, str]] = {}
  for line in out.splitlines():
    key, _, val = line.partition(" ")
    _, name, prop = key.split(".", 2)
    mods.setdefault(name, {})[prop] = val
  return mods


def resolve_url(url: str) -> str:
  if not url.startswith(("./", "../")):
    return url
  origin = run(["git", "config", "--get", "remote.origin.url"]).stdout.strip()
  if origin.startswith("git@github.com:"):
    origin = "https://github.com/" + origin.removeprefix("git@github.com:")
  origin = origin.removesuffix(".git")
  p = urlparse(origin)
  path = posixpath.normpath(posixpath.join(p.path, url))
  return f"{p.scheme}://{p.netloc}{path}"


def pinned_sha(path: str) -> str:
  out = run(["git", "ls-tree", "HEAD", path]).stdout.split()
  assert out and out[0] == "160000", f"{path} is not a gitlink in HEAD"
  return out[2]


def main() -> int:
  failures = []
  for name, cfg in gitmodules().items():
    path, url, branch = cfg["path"], resolve_url(cfg["url"]), cfg.get("branch")
    sha = pinned_sha(path)
    print(f"{name}: {sha[:9]} @ {url}" + (f" (branch {branch})" if branch else ""))

    with tempfile.TemporaryDirectory() as td:
      run(["git", "init", "-q"], cwd=td)
      run(["git", "remote", "add", "origin", url], cwd=td)

      if branch:
        heads = run(["git", "ls-remote", "--heads", "origin", branch], cwd=td).stdout.strip()
        if not heads:
          failures.append(f"{name}: branch '{branch}' does not exist on {url}")
          continue

      if run(["git", "fetch", "-q", "--depth", "1", "origin", sha], cwd=td, check=False).returncode != 0:
        failures.append(f"{name}: pinned commit {sha[:9]} is not fetchable from {url} (unpushed or garbage-collected?)")
        continue

      if branch:
        run(["git", "fetch", "-q", "origin", branch], cwd=td)
        if run(["git", "merge-base", "--is-ancestor", sha, "FETCH_HEAD"], cwd=td, check=False).returncode != 0:
          failures.append(f"{name}: pinned commit {sha[:9]} is not reachable from branch '{branch}' on {url}")

  print()
  if failures:
    print("FAIL:")
    for f in failures:
      print(f"  {f}")
    return 1
  print("OK: all submodule pins fetchable, branches exist, branch-tracked pins reachable")
  return 0


if __name__ == "__main__":
  sys.exit(main())
