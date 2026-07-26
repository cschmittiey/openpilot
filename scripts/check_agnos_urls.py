#!/usr/bin/env python3
"""Verify every AGNOS partition image URL in agnos.json is reachable.

Fresh installs and OS updates download these images on device: if comma
rotates or deletes the hosted .img.xz files for the AGNOS version this tree
pins, installs fail mid-flash with no useful error on screen. Nothing else
exercises these URLs, and they can rot without any push to this repo, so
this runs on a schedule as well as on push.

Uses a 1-byte Range request so the check stays cheap; accepts 200 or 206.
"""
import json
import pathlib
import sys
import urllib.error
import urllib.request

AGNOS_JSON = pathlib.Path(__file__).resolve().parent.parent / "openpilot" / "system" / "hardware" / "tici" / "agnos.json"


def check(url: str) -> str | None:
  req = urllib.request.Request(url, headers={"Range": "bytes=0-0", "User-Agent": "fork-ci-agnos-check"})
  try:
    with urllib.request.urlopen(req, timeout=30) as resp:
      if resp.status not in (200, 206):
        return f"HTTP {resp.status}"
  except urllib.error.HTTPError as e:
    return f"HTTP {e.code}"
  except (urllib.error.URLError, TimeoutError) as e:
    return str(e)
  return None


def main() -> int:
  partitions = json.loads(AGNOS_JSON.read_text())
  failures = []
  for p in partitions:
    err = check(p["url"])
    print(f"{p['name']}: {'FAIL - ' + err if err else 'ok'} ({p['url']})")
    if err:
      failures.append(f"{p['name']}: {err} ({p['url']})")

  print()
  if failures:
    print("FAIL:")
    for f in failures:
      print(f"  {f}")
    return 1
  print(f"OK: all {len(partitions)} AGNOS image URLs reachable")
  return 0


if __name__ == "__main__":
  sys.exit(main())
