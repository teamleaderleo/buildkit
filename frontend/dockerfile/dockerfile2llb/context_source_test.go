package dockerfile2llb

import "testing"

func TestIsDefaultContextSource(t *testing.T) {
	t.Parallel()

	// These strings exercise parser classification only; the test never resolves
	// or fetches any remote source.
	tests := []struct {
		name string
		src  string
		want bool
	}{
		{name: "relative-file", src: "marker", want: true},
		{name: "relative-directory", src: "dir/subdir", want: true},
		{name: "http", src: "http://example.invalid/archive.tar", want: false},
		{name: "https", src: "https://example.invalid/archive.tar", want: false},
		{name: "https-git", src: "https://github.com/moby/buildkit.git", want: false},
		{name: "git-scheme", src: "git://github.com/moby/buildkit.git", want: false},
		{name: "scp-style-git", src: "git@github.com:moby/buildkit.git", want: false},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			if got := isDefaultContextSource(tc.src); got != tc.want {
				t.Fatalf("isDefaultContextSource(%q) = %v, want %v", tc.src, got, tc.want)
			}
		})
	}
}
