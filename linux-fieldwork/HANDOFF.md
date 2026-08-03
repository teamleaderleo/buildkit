# Linux Fieldwork handoff — rootless OCI reproducibility

Updated: 2026-08-03
State: CANDIDATE EXECUTION QUEUED
Branch: `linux-fieldwork/rootless-reproducibility`
Current branch head: `4f7e6d6aff82c969e7d8080f56c5669db028f8ac`
Fork base: `master` at `df0761886a20e368d75e0aa6bb3f20874f58b692`
Internal review carrier: `teamleaderleo/buildkit#3`
Upstream issue: `moby/buildkit#6686`

## Exact reproduced defect

Focused workflow `30836946481`, job `91764326951`, built matching rootful and rootless BuildKit daemons from exact source head `7207045e68e3b8888926d0429a6b726834ececf1`. Both used the native snapshotter and runc. The fixture used `FROM scratch`, a deterministic locally compiled static helper, no registry input, no cache, and exporter timestamp rewriting at epoch `946684800`.

The helper-copy layer was identical. The `RUN` layer differed:

- rootful diff ID: `sha256:0bc3d5671a2ae10fcc90ba7bcdd2395a922802ff40dc0ccbca9500a8a527ffa1`;
- rootless diff ID: `sha256:8543a6b1010bf77ec314441cac03ad659f0061c7f64aec807810dfe3661eaef6`.

Exact mountpoint metadata:

- rootful committed `proc/` and `sys/`, both directory mode `0755`, uid/gid `0`, mtime `946684800`;
- rootless committed `proc/` with identical metadata and did not commit `sys/`.

This is a missing-member divergence, not a timestamp, mode, uid/gid, PAX, compression, base-image, registry, or cache difference.

Retained artifact:

- artifact ID: `8865260431`;
- digest: `sha256:6f0effc21071f58b3a0b0cc7a28b5f6427d6b883ec79c2c2bf6d28508439235c`.

## Source owner

The runc executor generates the OCI spec and then applies `rootlessspecconv.ToRootless(spec)` only for the rootless worker. `ToRootless()` deliberately removes every mount whose destination begins with `/sys`.

Therefore:

- rootful retains the default sysfs mount, so runc creates an absent lower-root `/sys` mountpoint;
- rootless removes that mount, so runc creates no `/sys` path;
- the rootful empty mountpoint reaches the committed snapshot.

BuildKit already has the correct ownership abstraction in `executor.MountStubsCleaner()`: it records mount destinations absent before execution, removes only empty stubs afterward, and restores parent timestamps. Its blind spot is call timing. Both OCI executors register cleanup before the finalized spec exists and pass only BuildKit's explicit mounts, so default OCI destinations such as `/proc` and `/sys` are omitted.

## Selected candidate

Retained source patch:

- `linux-fieldwork/0001-executor-clean-finalized-oci-mount-stubs.patch`.

Candidate behavior:

1. finalize the OCI spec;
2. apply rootless conversion where applicable;
3. register cleanup from the actual `spec.Mounts[].Destination` list;
4. sort recorded paths deepest-first so nested stubs drain before parents;
5. retain the existing rule that pre-existing image paths are never removed.

This makes ownership mode-correct:

- rootful owns runtime-created `/proc` and `/sys` stubs because its final spec mounts there;
- rootless owns `/proc` but does not own `/sys` after conversion;
- an image-provided `/proc` or `/sys` is preserved;
- an empty `/sys` deliberately created by a rootless build remains user-owned.

## Candidate tests

`executor/stubs_spec_test.go` covers:

- nested runtime-created `/sys/fs/cgroup` cleanup before `/sys`;
- retention of a pre-existing image `/sys`;
- rootless-spec ownership: `/proc` is removed while user-created `/sys` survives.

The focused workflow now:

1. applies the retained source patch with `git apply --check --recount`;
2. formats changed Go files and checks the diff;
3. runs `go test ./executor`;
4. builds exact candidate `buildkitd` and `buildctl` binaries;
5. starts matching rootful and rootless native-snapshotter workers;
6. requires the implicit `FROM scratch` RUN outputs to have identical rootfs identities;
7. requires the explicit pre-created `/proc` and `/sys` control to remain identical;
8. uploads worker and comparator logs.

Candidate workflow currently queued:

- run `30838430937`.

A separate baseline-control run at pre-candidate head `ffd7a47352369b59cca940063a2fb48765c83e10` is also queued as run `30837593710`. It requires the implicit case to reproduce divergence and the explicit pre-created-directory control to converge.

## Branch contents

- `linux-fieldwork/repro-rootless-oci.sh` — deterministic two-worker build, with optional `PRECREATE_RUNTIME_DIRS=1` negative control;
- `linux-fieldwork/compare-oci-rootfs.py` — compares uncompressed rootfs diff IDs and emits exact `/proc` and `/sys` metadata;
- `executor/stubs_spec_test.go` — focused ownership tests;
- `linux-fieldwork/0001-executor-clean-finalized-oci-mount-stubs.patch` — source candidate;
- `.github/workflows/linux-fieldwork-rootless-repro.yml` — exact candidate execution;
- this handoff.

## First incomplete step

Read run `30838430937`.

- If patch application or unit tests fail, classify the source/test carrier before changing behavior.
- If workers start but implicit parity remains red, inspect the candidate layer metadata and runtime logs; do not normalize at export.
- If both implicit and explicit matrices pass, rerun the exact focused workflow once, review the complete current diff, and promote the internal PR to a human send/hold decision.

## Scope boundaries

- Current evidence covers Linux, runc, native snapshotter, scratch-based OCI export, and matching exact-source rootful/rootless workers.
- containerd executor source is included because it has the same cleanup-registration gap, but a live containerd-worker matrix has not run.
- crun and other runtimes remain unexecuted.
- The candidate does not normalize exporter tar streams or rewrite user-requested metadata.

## External-contact state

`false; none occurred`. No canonical upstream issue comment, pull request, review, reaction, email, or other interaction was created.
