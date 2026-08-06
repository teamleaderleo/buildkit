#!/usr/bin/env python3

from pathlib import Path

path = Path("frontend/dockerfile/dockerfile2llb/convert.go")
text = path.read_text()

helper_anchor = "func dispatch(d *dispatchState, cmd command, opt dispatchOpt) error {\n"
helper_replacement = """func isDefaultContextSource(src string) bool {
	return !isHTTPSource(src) && !isGitSource(src)
}

func dispatch(d *dispatchState, cmd command, opt dispatchOpt) error {
"""

add_anchor = """	case *instructions.AddCommand:
		ignoreMatcher, err := opt.dockerIgnoreMatcher()
		if err != nil {
			return err
		}
		err = dispatchCopy(d, copyConfig{
"""
add_replacement = """	case *instructions.AddCommand:
		var ignoreMatcher *patternmatcher.PatternMatcher
		for _, src := range c.SourcePaths {
			if !isDefaultContextSource(src) {
				continue
			}
			ignoreMatcher, err = opt.dockerIgnoreMatcher()
			if err != nil {
				return err
			}
			break
		}
		err = dispatchCopy(d, copyConfig{
"""

path_anchor = """				if !strings.HasPrefix(src, \"http://\") && !strings.HasPrefix(src, \"https://\") {
					d.ctxPaths[path.Join(\"/\", filepath.ToSlash(src))] = struct{}{}
				}
"""
path_replacement = """				if isDefaultContextSource(src) {
					d.ctxPaths[path.Join(\"/\", filepath.ToSlash(src))] = struct{}{}
				}
"""

replacements = (
    (helper_anchor, helper_replacement, "dispatch helper anchor"),
    (add_anchor, add_replacement, "ADD ignore-loader anchor"),
    (path_anchor, path_replacement, "ADD context-path anchor"),
)

for old, new, label in replacements:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    text = text.replace(old, new, 1)

path.write_text(text)
