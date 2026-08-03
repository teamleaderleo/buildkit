#!/bin/sh
set -eu

: "${ROOTFUL_ADDR:?set ROOTFUL_ADDR to a rootful BuildKit address}"
: "${ROOTLESS_ADDR:?set ROOTLESS_ADDR to a rootless BuildKit address}"

BASE_IMAGE=${BASE_IMAGE:-scratch}
SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-946684800}
PRECREATE_RUNTIME_DIRS=${PRECREATE_RUNTIME_DIRS:-0}

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/buildkit-rootless-repro.XXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM

mkdir -p "$work/context"
cat >"$work/helper.go" <<'EOF'
package main

import "os"

func main() {
    if err := os.MkdirAll("/generated/deeper", 0o755); err != nil {
        panic(err)
    }
    if err := os.WriteFile("/generated/value", []byte("stable-exec-output\n"), 0o644); err != nil {
        panic(err)
    }
    if err := os.WriteFile("/generated/deeper/value", []byte("stable-nested-output\n"), 0o644); err != nil {
        panic(err)
    }
}
EOF

CGO_ENABLED=0 go build \
    -trimpath \
    -ldflags='-s -w -buildid=' \
    -o "$work/context/lf-repro-helper" \
    "$work/helper.go"

if [ "$PRECREATE_RUNTIME_DIRS" = 1 ]; then
    mkdir -p "$work/context/proc" "$work/context/sys"
    cat >"$work/context/Dockerfile" <<'EOF'
ARG BASE_IMAGE=scratch
FROM ${BASE_IMAGE}
COPY proc /proc
COPY sys /sys
COPY lf-repro-helper /lf-repro-helper
ARG SOURCE_DATE_EPOCH
RUN ["/lf-repro-helper"]
EOF
else
    cat >"$work/context/Dockerfile" <<'EOF'
ARG BASE_IMAGE=scratch
FROM ${BASE_IMAGE}
COPY lf-repro-helper /lf-repro-helper
ARG SOURCE_DATE_EPOCH
RUN ["/lf-repro-helper"]
EOF
fi

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
