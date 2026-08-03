package executor

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"testing"

	specs "github.com/opencontainers/runtime-spec/specs-go"
)

func TestMountStubsCleanerForSpec(t *testing.T) {
	t.Run("runtime-created nested stubs", func(t *testing.T) {
		root := t.TempDir()
		clean := MountStubsCleanerForSpec(context.Background(), root, []specs.Mount{
			{Destination: "/proc"},
			{Destination: "/sys"},
			{Destination: "/sys/fs/cgroup"},
		}, true)

		for _, path := range []string{"proc", "sys/fs/cgroup"} {
			if err := os.MkdirAll(filepath.Join(root, path), 0o755); err != nil {
				t.Fatal(err)
			}
		}
		clean()

		for _, path := range []string{"proc", "sys/fs/cgroup", "sys/fs", "sys"} {
			if _, err := os.Lstat(filepath.Join(root, path)); !errors.Is(err, os.ErrNotExist) {
				t.Fatalf("runtime-created stub %q survived cleanup: %v", path, err)
			}
		}
	})

	t.Run("pre-existing image path is retained", func(t *testing.T) {
		root := t.TempDir()
		if err := os.MkdirAll(filepath.Join(root, "sys"), 0o755); err != nil {
			t.Fatal(err)
		}

		clean := MountStubsCleanerForSpec(context.Background(), root, []specs.Mount{
			{Destination: "/proc"},
			{Destination: "/sys"},
		}, true)
		if err := os.MkdirAll(filepath.Join(root, "proc"), 0o755); err != nil {
			t.Fatal(err)
		}
		clean()

		if _, err := os.Stat(filepath.Join(root, "sys")); err != nil {
			t.Fatalf("pre-existing /sys was removed: %v", err)
		}
		if _, err := os.Lstat(filepath.Join(root, "proc")); !errors.Is(err, os.ErrNotExist) {
			t.Fatalf("runtime-created /proc survived cleanup: %v", err)
		}
	})

	t.Run("rootless spec does not own sys", func(t *testing.T) {
		root := t.TempDir()
		clean := MountStubsCleanerForSpec(context.Background(), root, []specs.Mount{
			{Destination: "/proc"},
		}, true)

		for _, path := range []string{"proc", "sys"} {
			if err := os.MkdirAll(filepath.Join(root, path), 0o755); err != nil {
				t.Fatal(err)
			}
		}
		clean()

		if _, err := os.Lstat(filepath.Join(root, "proc")); !errors.Is(err, os.ErrNotExist) {
			t.Fatalf("runtime-created /proc survived cleanup: %v", err)
		}
		if _, err := os.Stat(filepath.Join(root, "sys")); err != nil {
			t.Fatalf("rootless user-owned /sys was removed: %v", err)
		}
	})
}
