#!/usr/bin/env python3
from pathlib import Path

convert = Path("frontend/dockerfile/dockerfile2llb/convert.go")
text = convert.read_text()
old = "if !isHTTPSource(src) && !isGitSource(src) {"
if text.count(old) != 2:
    raise SystemExit(f"expected two broad ADD source checks, found {text.count(old)}")
text = text.replace(old, "if isLocalContextSource(src) {")
convert.write_text(text)

copy = Path("frontend/dockerfile/dockerfile2llb/convert_copy.go")
text = copy.read_text()
marker = "func isHTTPSource(src string) bool {\n"
if text.count(marker) != 1:
    raise SystemExit("isHTTPSource marker not found exactly once")
helper = '''func isLocalContextSource(src string) bool {
	gitRef, isGit, err := dfgitutil.ParseGitRef(src)
	if err != nil && isGit {
		return false
	}
	if err == nil && gitRef != nil && !gitRef.IndistinguishableFromLocal {
		return false
	}
	return !isHTTPSource(src)
}

'''
text = text.replace(marker, helper + marker, 1)
copy.write_text(text)
