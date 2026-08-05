from pathlib import Path

path = Path("executor/stubs.go")
text = path.read_text(encoding="utf-8")

old_calls = """\treturn mountStubsCleaner(ctx, dir, names, recursive)
}

// MountStubsCleanerForSpec removes empty mountpoint stubs created for the
// finalized OCI spec. Paths that existed before execution remain untouched.
func MountStubsCleanerForSpec(ctx context.Context, dir string, mounts []specs.Mount, recursive bool) func() {
\tnames := []string{\"/etc/resolv.conf\", \"/etc/hosts\"}

\tfor _, m := range mounts {
\t\tnames = append(names, m.Destination)
\t}
\treturn mountStubsCleaner(ctx, dir, names, recursive)
}

func mountStubsCleaner(ctx context.Context, dir string, names []string, recursive bool) func() {
"""
new_calls = """\treturn mountStubsCleaner(ctx, dir, names, recursive, false)
}

// MountStubsCleanerForSpec removes empty mountpoint stubs created for the
// finalized OCI spec. Paths that existed before execution remain untouched.
func MountStubsCleanerForSpec(ctx context.Context, dir string, mounts []specs.Mount, recursive bool) func() {
\tnames := []string{\"/etc/resolv.conf\", \"/etc/hosts\"}

\tfor _, m := range mounts {
\t\tnames = append(names, m.Destination)
\t}
\treturn mountStubsCleaner(ctx, dir, names, recursive, true)
}

func mountStubsCleaner(ctx context.Context, dir string, names []string, recursive bool, deepestFirst bool) func() {
"""
if text.count(old_calls) != 1:
    raise SystemExit(f"expected one helper call block, found {text.count(old_calls)}")
text = text.replace(old_calls, new_calls, 1)

old_sort = """\tslices.SortFunc(paths, func(a, b string) int {
\t\tif n := cmp.Compare(len(b), len(a)); n != 0 {
\t\t\treturn n
\t\t}
\t\treturn strings.Compare(a, b)
\t})
\tpaths = slices.Compact(paths)
"""
new_sort = """\tif deepestFirst {
\t\tslices.SortFunc(paths, func(a, b string) int {
\t\t\tif n := cmp.Compare(len(b), len(a)); n != 0 {
\t\t\t\treturn n
\t\t\t}
\t\t\treturn strings.Compare(a, b)
\t\t})
\t\tpaths = slices.Compact(paths)
\t}
"""
if text.count(old_sort) != 1:
    raise SystemExit(f"expected one ordering block, found {text.count(old_sort)}")
path.write_text(text.replace(old_sort, new_sort, 1), encoding="utf-8")
