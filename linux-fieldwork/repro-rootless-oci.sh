#!/bin/sh
set -eu

: "${ROOTFUL_ADDR:?set ROOTFUL_ADDR to a rootful BuildKit address}"
: "${ROOTLESS_ADDR:?set ROOTLESS_ADDR to a rootless BuildKit address}"

BASE_IMAGE=${BASE_IMAGE:-docker.io/library/busybox:latest}
SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-946684800}

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/buildkit-rootless-repro.XXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM

mkdir -p "$work/context"
cat >"$work/context/Dockerfile" <<'EOF'
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
RUN mkdir -p /generated/deeper \
 && printf '%s\n' stable-exec-output > /generated/value \
 && printf '%s\n' stable-nested-output > /generated/deeper/value
EOF

build_one() {
    label=$1
    address=$2
    archive=$work/$label.oci.tar

    buildctl --addr "$address" build \
        --no-cache \
        --frontend dockerfile.v0 \
        --local context="$work/context" \
        --local dockerfile="$work/context" \
        --opt filename=Dockerfile \
        --opt "build-arg:BASE_IMAGE=$BASE_IMAGE" \
        --opt "build-arg:SOURCE_DATE_EPOCH=$SOURCE_DATE_EPOCH" \
        --output "type=oci,dest=$archive,rewrite-timestamp=true"
}

build_one rootful "$ROOTFUL_ADDR"
build_one rootless "$ROOTLESS_ADDR"

python3 "$script_dir/compare-oci-rootfs.py" \
    "$work/rootful.oci.tar" \
    "$work/rootless.oci.tar"
