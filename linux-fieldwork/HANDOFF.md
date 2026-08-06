# Linux Fieldwork handoff — rootless OCI reproducibility

Updated: 2026-08-03
State: READY FOR HUMAN SEND/HOLD REVIEW — RUNC/NATIVE PROVEN
Branch: `linux-fieldwork/rootless-reproducibility`
Exact tested candidate head: `2c1fa9f7e5975c4a2bc46542df3c071a44c9db39`
Fork base: `master` at `df0761886a20e368d75e0aa6bb3f20874f58b692`
Internal review carrier: `teamleaderleo/buildkit#3`
Upstream issue: `moby/buildkit#6686`

## Exact reproduced defect

Baseline workflow `30836946481`, job `91764326951`, built matching rootful and rootless BuildKit daemons from exact source head `7207045e68e3b8888926d0429a6b726834ececf1`. Both used the native snapshotter and runc. The fixture used `FROM scratch`, a deterministic locally compiled static helper, no registry input, no cache, and exporter timestamp rewriting at epoch `946684800`.

The helper-copy layer was identical. The `RUN` layer differed:

- rootful diff ID: `sha256:0bc3d5671a2ae10fcc90ba7bcdd2395a922802ff40dc0ccbca9500a8a527ffa1`;
- rootless diff ID: `sha256:8543a6b1010bf77ec314441cac03ad659f0061c7f64aec807810dfe3661eaef6`.

Rootful committed empty `proc/` and `sys/` directories. Rootless committed `proc/` with identical metadata and no `sys/`. This is a missing-member divergence, not a timestamp, mode, uid/gid, PAX, compression, base-image, registry, or cache difference.

Baseline artifact:

- artifact ID: `8865260431`;
- digest: `sha256:6f0effc21071f58b3a0b0cc7a28b5f6427d6b883ec79c2c2bf6d28508439235c`.

## Negative control

Baseline-control workflow `30837593710`, job `91766481673`, required the implicit mountpoint case to reproduce and then pre-created `/proc` and `/sys` in the image input.

Result:

- implicit case diverged as above;
- explicit pre-created `/proc` and `/sys` case produced identical rootful/rootless rootfs identities.

Control artifact:

- artifact ID: `8865777349`;
- digest: `sha256:9f05ba2749fd1bfe390b875715a684629e39c7282e54cc040105550dba6b88d4`.

This proves the defect belongs to runtime-created mountpoint ownership, not exporter normalization.

## Source owner

The runc executor generates the OCI spec and applies `rootlessspecconv.ToRootless(spec)` only for rootless execution. `ToRootless()` removes mounts whose destinations begin with `/sys`.

Therefore:

- rootful retains the default sysfs mount and runc creates an absent lower-root `/sys` mountpoint;
- rootless removes that mount and creates no `/sys` path;
- the rootful runtime-created directory leaks into the committed snapshot.

BuildKit already has the right cleanup abstraction. `executor.MountStubsCleaner()` records mount destinations absent before execution, removes only empty stubs afterward, and restores parent timestamps. Its blind spot was timing: both OCI executors registered cleanup before the finalized spec existed and passed only BuildKit's explicit mounts, omitting default OCI destinations such as `/proc` and `/sys`.

## Selected candidate

Retained source patch:

- `linux-fieldwork/0001-executor-clean-finalized-oci-mount-stubs.patch`.

Candidate behavior:

1. finalize the OCI spec;
2. apply rootless conversion where applicable;
3. register cleanup from actual `spec.Mounts[].Destination` values;
4. sort recorded paths deepest-first and deduplicate them;
5. retain the existing rule that pre-existing image paths are never removed.

This makes ownership mode-correct:

- rootful owns runtime-created `/proc` and `/sys` stubs because its final spec mounts there;
- rootless owns `/proc` but not `/sys` after conversion;
- image-provided `/proc` or `/sys` paths remain untouched;
- a `/sys` deliberately created by a rootless build remains user-owned.

## Focused ownership tests

`executor/stubs_spec_test.go` covers:

- recursive nested `/sys/fs/cgroup`, `/sys/fs`, and `/sys` cleanup deepest-first;
- retention of a pre-existing image `/sys`;
- rootless-spec ownership: `/proc` is removed while user-created `/sys` survives.

The first candidate unit run used `recursive=false` for the nested case and correctly left `/sys/fs`, preventing `/sys` removal. Dockerfile `RUN` uses recursive mount-stub cleanup, so the test was corrected to the real product contract rather than widening deletion policy.

## Final strict candidate execution

Final focused workflow:

- run: `30840454069`;
- job: `91775919207`;
- exact tested candidate head: `2c1fa9f7e5975c4a2bc46542df3c071a44c9db39`;
- generated merge: `4a27723011a9d6a363352ceb962b508588605031`;
- result: success.

Passed gates:

- ordinary `git apply --check` and `git apply`, without recount or fuzz;
- formatting and `git diff --check`;
- `go test ./executor`;
- exact candidate `buildkitd` and `buildctl` builds;
- matching rootful and rootless native-snapshotter/runc workers;
- implicit `FROM scratch` rootfs parity;
- explicit pre-created `/proc` and `/sys` parity;
- worker shutdown and artifact retention.

Final artifact:

- artifact ID: `8866569988`;
- digest: `sha256:9c501b17b283baacc64d5034a90b441557eb4ea7023a4fc62fa399fc8030f024`.

Exact repaired implicit identities, both rootful and rootless:

- helper layer: `sha256:d09c8e5639600a2e168c9c6caf1df9810a4e1a99185897a36b473f57b4be42c8`;
- `RUN` layer: `sha256:6bacde96cb524f50dc158fef2c87c3cbc9e49c30137062eb3a6d44610ae04ec7`.

Exact explicit-control identities, both modes:

- `/proc` layer: `sha256:a003acf257ec52a93538231869f9d091f93d8de27f90076303fdb47668cefbe1`;
- `/sys` layer: `sha256:3c0069bda34a8285b81abb2a1cc1e82213e441704a1b6fdb0a27b70c0ba5bc86`;
- helper layer: `sha256:d09c8e5639600a2e168c9c6caf1df9810a4e1a99185897a36b473f57b4be42c8`;
- `RUN` layer: `sha256:6bacde96cb524f50dc158fef2c87c3cbc9e49c30137062eb3a6d44610ae04ec7`.

## Review result

GitHub Advanced Security reported three unpinned workflow actions. Checkout, setup-go, and upload-artifact were pinned to the exact revisions already used by the successful runner, and all three review threads were resolved.

Complete-diff review remains bounded to:

- one retained product patch;
- one focused ownership test;
- deterministic reproducer and comparator;
- focused CI;
- this handoff.

No exporter post-processing or broad snapshot normalization was added.

## Remaining boundary

Proven:

- Linux;
- runc;
- native snapshotter;
- scratch-based OCI export;
- matching exact-source rootful/rootless workers;
- cleanup, artifact retention, and immediate clean rerun.

Not yet live-executed:

- containerd worker;
- crun or other OCI runtimes.

The retained source patch includes the analogous containerd executor timing correction. Source review confirms `createOCISpec()` returns after mode-specific rootless conversion, and the changed containerd path compiles through the candidate build. A live containerd-worker parity matrix remains the principal technical caveat.

## Next human decision

Choose one:

1. authorize preparation of a canonical-upstream pull request, clearly stating that runc/native is executed and containerd live execution remains a follow-up caveat; or
2. hold for a live containerd-worker matrix before any external submission.

No further source hypothesis is required for the reproduced runc/native defect.

## External-contact state

`false; none occurred`. No canonical upstream issue comment, pull request, review, reaction, email, or other interaction was created.
