#!/usr/bin/env python3
from pathlib import Path

convert = Path("frontend/dockerfile/dockerfile2llb/convert.go")
text = convert.read_text()
broad = "if !isHTTPSource(src) && !isGitSource(src) {"
exact = "if isLocalContextSource(src) {"
if text.count(broad) == 2:
    text = text.replace(broad, exact)
elif text.count(broad) == 0 and text.count(exact) == 2:
    pass
else:
    raise SystemExit(
        f"unexpected ADD source checks: broad={text.count(broad)} exact={text.count(exact)}"
    )
convert.write_text(text)

copy = Path("frontend/dockerfile/dockerfile2llb/convert_copy.go")
text = copy.read_text()
marker = "func isHTTPSource(src string) bool {\n"
helper_marker = "func isLocalContextSource(src string) bool {\n"
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
if text.count(helper_marker) == 0:
    if text.count(marker) != 1:
        raise SystemExit("isHTTPSource marker not found exactly once")
    text = text.replace(marker, helper + marker, 1)
elif text.count(helper_marker) != 1:
    raise SystemExit(f"unexpected local-source helper count: {text.count(helper_marker)}")
copy.write_text(text)
