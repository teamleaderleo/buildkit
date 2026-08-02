# Linux Fieldwork handoff — rootless OCI reproducibility

Updated: 2026-08-02
State: REPRODUCTION READY
Branch: `linux-fieldwork/rootless-reproducibility`
Base: fork `master` at `df0761886a20e368d75e0aa6bb3f20874f58b692`
Upstream issue: `moby/buildkit#6686`

## Finding

BuildKit issue #6686 reports that rootless and rootful workers produce different image rootfs identities because runtime-created `/proc` and `/sys` stub directories differ. The issue remains open and unassigned.

This is independently corroborated by merged PR #6681. Its compatibility test had to pre-create `/proc` and `/sys` specifically to avoid a rootless/non-rootless runtime snapshot difference. That workaround keeps compatibility goldens stable while leaving the underlying worker divergence unresolved.

## Ownership boundary observed

`executor/oci.GenerateSpec()` constructs the OCI spec and then, when BuildKit itself runs in a user namespace, applies `rootlessmountopts.FixUpOCI()` to bind mounts. `FixUpOCI()` only preserves kernel-locked unprivileged mount flags; it does not intentionally define `/proc` or `/sys` directory metadata.

Therefore the next discriminator must establish where the different stub metadata first appears:

1. generated OCI spec;
2. rootfs before runtime start;
3. rootfs after runtime setup and exit;
4. committed snapshot diff.

A source fix before that capture would guess across BuildKit, containerd OCI defaults, and the selected OCI runtime.

## Branch contents

- `linux-fieldwork/repro-rootless-oci.sh`
  - builds the same no-cache exec layer through caller-supplied rootful and rootless BuildKit addresses;
  - exports both results as OCI archives;
  - fixes build timestamps through `SOURCE_DATE_EPOCH` plus exporter timestamp rewriting;
  - delegates structural comparison to the Python tool.
- `linux-fieldwork/compare-oci-rootfs.py`
  - resolves a single-platform OCI archive;
  - compares uncompressed `rootfs.diff_ids` rather than incidental manifest annotations;
  - on divergence, prints the first differing layer descriptor and exact `/proc` and `/sys` tar metadata;
  - exits 0 for identical rootfs identities, 1 for a reproduced divergence, and 2 for invalid input/tooling errors.

## Local validation

The execution environment did not contain two BuildKit daemons, so the live rootful/rootless gate remains pending.

Completed local gates:

- Python syntax compilation: PASS;
- shell syntax with `/bin/sh -n`: PASS;
- two synthetic identical OCI archives: comparator status 0, `rootfs-identical`;
- synthetic archives differing only in `/proc` directory mode: comparator status 1, `rootfs-different`, first differing layer 0, and exact runtime-mountpoint metadata emitted;
- temporary synthetic archives were removed.

## Exact live command

```text
ROOTFUL_ADDR=unix:///run/buildkit/buildkitd.sock \
ROOTLESS_ADDR=unix:///run/user/1000/buildkit/buildkitd.sock \
./linux-fieldwork/repro-rootless-oci.sh
```

The current defect is reproduced when the command exits 1 and the output isolates `/proc` or `/sys` metadata in the first differing layer. A repaired implementation should make the command exit 0.

Pin `BASE_IMAGE` to a digest when collecting durable evidence, for example:

```text
BASE_IMAGE=docker.io/library/busybox@sha256:<digest> ...
```

## Next technical step

Run the live gate against matching rootful and rootless workers built from this exact commit. If it reproduces:

1. capture the generated OCI specs for the exec operation;
2. compare `/proc` and `/sys` metadata before runtime start, after runtime exit, and in the committed upper snapshot;
3. repeat with both runc and crun where available;
4. place the fix at the earliest BuildKit-owned boundary that can normalize the metadata without masking runtime-owned changes;
5. convert the reproducer into the smallest integration test supported by the worker matrix.

## Scope exclusions

- Do not retain PR #6681's pre-created-directory workaround as the product fix; it changes test input to hide the divergence.
- Do not normalize the whole exported tar stream after the fact; that would conceal other rootless reproducibility defects.
- Do not assume `FixUpOCI()` owns the defect until the generated spec and runtime transition are compared.

## External-contact state

`false; none occurred`. No upstream issue, pull request, comment, review, discussion, or email was created.
