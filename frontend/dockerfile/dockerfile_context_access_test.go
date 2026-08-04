package dockerfile

import (
	"context"
	"errors"
	"io"
	gofs "io/fs"
	"runtime"
	"sync/atomic"
	"testing"

	"github.com/containerd/continuity/fs/fstest"
	"github.com/moby/buildkit/client"
	"github.com/moby/buildkit/frontend/dockerui"
	"github.com/moby/buildkit/util/testutil/integration"
	"github.com/stretchr/testify/require"
	"github.com/tonistiigi/fsutil"
)

type contextAccessFailFS struct {
	err      error
	accesses atomic.Int64
}

func (f *contextAccessFailFS) Walk(context.Context, string, gofs.WalkDirFunc) error {
	f.accesses.Add(1)
	return f.err
}

func (f *contextAccessFailFS) Open(string) (io.ReadCloser, error) {
	f.accesses.Add(1)
	return nil, f.err
}

func init() {
	allTests = append(allTests, integration.TestFuncs(testDockerfileLazyContextAccess)...)
}

func testDockerfileLazyContextAccess(t *testing.T, sb integration.Sandbox) {
	if runtime.GOOS != "linux" {
		t.Skip("lazy main-context access matrix requires a Linux worker")
	}

	frontend := getFrontend(t, sb)
	c, err := client.New(sb.Context(), sb.Address())
	require.NoError(t, err)
	defer c.Close()

	tests := []struct {
		name        string
		dockerfile  string
		wantAccess  bool
		wantSuccess bool
	}{
		{
			name: "metadata-only",
			dockerfile: `
FROM scratch
LABEL org.mobyproject.buildkit.test=unused-context
`,
			wantAccess:  false,
			wantSuccess: true,
		},
		{
			name: "local-copy",
			dockerfile: `
FROM scratch
COPY marker /marker
`,
			wantAccess:  true,
			wantSuccess: false,
		},
		{
			name: "context-bind-mount",
			dockerfile: `
FROM busybox
RUN --mount=type=bind,source=.,target=/src test -f /src/marker
`,
			wantAccess:  true,
			wantSuccess: false,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			dockerfileDir := integration.Tmpdir(
				t,
				fstest.CreateFile("Dockerfile", []byte(tc.dockerfile), 0600),
			)

			const sentinel = "main build context was accessed"
			contextFS := &contextAccessFailFS{err: errors.New(sentinel)}

			_, err := frontend.Solve(sb.Context(), c, client.SolveOpt{
				LocalMounts: map[string]fsutil.FS{
					dockerui.DefaultLocalNameDockerfile: dockerfileDir,
					dockerui.DefaultLocalNameContext:    contextFS,
				},
			}, nil)

			if tc.wantSuccess {
				require.NoError(t, err)
			} else {
				require.ErrorContains(t, err, sentinel)
			}

			if tc.wantAccess {
				require.Positive(t, contextFS.accesses.Load())
			} else {
				require.Zero(t, contextFS.accesses.Load())
			}
		})
	}
}
