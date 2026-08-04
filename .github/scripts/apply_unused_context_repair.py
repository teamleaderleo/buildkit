#!/usr/bin/env python3
from pathlib import Path

path = Path("frontend/dockerfile/dockerfile2llb/convert.go")
text = path.read_text()

old = """\tvar dockerIgnoreMatcher *patternmatcher.PatternMatcher
\tif dctx.opt.Client != nil {
\t\tdockerIgnorePatterns, err := dctx.opt.Client.DockerIgnorePatterns(ctx)
\t\tif err != nil {
\t\t\treturn nil, nil, err
\t\t}
\t\tif len(dockerIgnorePatterns) > 0 {
\t\t\tdockerIgnoreMatcher, err = patternmatcher.New(dockerIgnorePatterns)
\t\t\tif err != nil {
\t\t\t\treturn nil, nil, err
\t\t\t}
\t\t}
\t}
"""
new = """\tvar dockerIgnoreMatcher *patternmatcher.PatternMatcher
\tvar dockerIgnoreMatcherErr error
\tvar dockerIgnoreMatcherOnce sync.Once
\tgetDockerIgnoreMatcher := func() (*patternmatcher.PatternMatcher, error) {
\t\tdockerIgnoreMatcherOnce.Do(func() {
\t\t\tif dctx.opt.Client == nil {
\t\t\t\treturn
\t\t\t}

\t\t\tdockerIgnorePatterns, err := dctx.opt.Client.DockerIgnorePatterns(ctx)
\t\t\tif err != nil {
\t\t\t\tdockerIgnoreMatcherErr = err
\t\t\t\treturn
\t\t\t}
\t\t\tif len(dockerIgnorePatterns) > 0 {
\t\t\t\tdockerIgnoreMatcher, dockerIgnoreMatcherErr = patternmatcher.New(dockerIgnorePatterns)
\t\t\t}
\t\t})

\t\treturn dockerIgnoreMatcher, dockerIgnoreMatcherErr
\t}
"""
if text.count(old) != 1:
    raise SystemExit("eager dockerignore block not found exactly once")
text = text.replace(old, new, 1)

old = "\t\t\tdockerIgnoreMatcher: dockerIgnoreMatcher,\n"
new = "\t\t\tdockerIgnoreMatcher: getDockerIgnoreMatcher,\n"
if text.count(old) != 1:
    raise SystemExit("dispatch matcher assignment not found exactly once")
text = text.replace(old, new, 1)

old = "\tdockerIgnoreMatcher *patternmatcher.PatternMatcher\n"
new = "\tdockerIgnoreMatcher func() (*patternmatcher.PatternMatcher, error)\n"
if text.count(old) != 1:
    raise SystemExit("dispatch option matcher field not found exactly once")
text = text.replace(old, new, 1)

old = """\tcase *instructions.AddCommand:
\t\terr = dispatchCopy(d, copyConfig{
"""
new = """\tcase *instructions.AddCommand:
\t\tvar ignoreMatcher *patternmatcher.PatternMatcher
\t\tfor _, src := range c.SourcePaths {
\t\t\tif !isHTTPSource(src) && !isGitSource(src) {
\t\t\t\tif opt.dockerIgnoreMatcher != nil {
\t\t\t\t\tignoreMatcher, err = opt.dockerIgnoreMatcher()
\t\t\t\t\tif err != nil {
\t\t\t\t\t\treturn err
\t\t\t\t\t}
\t\t\t\t}
\t\t\t\tbreak
\t\t\t}
\t\t}
\t\terr = dispatchCopy(d, copyConfig{
"""
if text.count(old) != 1:
    raise SystemExit("ADD dispatch block not found exactly once")
text = text.replace(old, new, 1)

old = "\t\t\tignoreMatcher:   opt.dockerIgnoreMatcher,\n"
new = "\t\t\tignoreMatcher:   ignoreMatcher,\n"
if text.count(old) != 1:
    raise SystemExit("ADD ignore matcher assignment not found exactly once")
text = text.replace(old, new, 1)

old = """\t\tif err == nil {
\t\t\tfor _, src := range c.SourcePaths {
\t\t\t\tif !strings.HasPrefix(src, "http://") && !strings.HasPrefix(src, "https://") {
\t\t\t\t\td.ctxPaths[path.Join("/", filepath.ToSlash(src))] = struct{}{}
\t\t\t\t}
\t\t\t}
\t\t}
"""
new = """\t\tif err == nil {
\t\t\tfor _, src := range c.SourcePaths {
\t\t\t\tif !isHTTPSource(src) && !isGitSource(src) {
\t\t\t\t\td.ctxPaths[path.Join("/", filepath.ToSlash(src))] = struct{}{}
\t\t\t\t}
\t\t\t}
\t\t}
"""
if text.count(old) != 1:
    raise SystemExit("ADD context path accounting block not found exactly once")
text = text.replace(old, new, 1)

old = """\t\t} else {
\t\t\tignoreMatcher = opt.dockerIgnoreMatcher
\t\t}
\t\terr = dispatchCopy(d, copyConfig{
"""
new = """\t\t} else if len(c.SourcePaths) > 0 && opt.dockerIgnoreMatcher != nil {
\t\t\tignoreMatcher, err = opt.dockerIgnoreMatcher()
\t\t\tif err != nil {
\t\t\t\treturn err
\t\t\t}
\t\t}
\t\terr = dispatchCopy(d, copyConfig{
"""
if text.count(old) != 1:
    raise SystemExit("COPY ignore matcher block not found exactly once")
text = text.replace(old, new, 1)

old = """\topts := filterPaths(ctxPaths)
\tbctx := dctx.opt.MainContext
\tif dctx.opt.Client != nil {
\t\tvar err error
\t\tbctx, err = dctx.opt.Client.MainContext(ctx, opts...)
\t\tif err != nil {
\t\t\treturn err
\t\t}
\t} else if bctx == nil {
\t\tbctx = dockerui.DefaultMainContext(opts...)
\t}

\tbuildContext.Output = bctx.Output()
"""
new = """\tif len(ctxPaths) > 0 || target.scanContext {
\t\topts := filterPaths(ctxPaths)
\t\tbctx := dctx.opt.MainContext
\t\tif dctx.opt.Client != nil {
\t\t\tvar err error
\t\t\tbctx, err = dctx.opt.Client.MainContext(ctx, opts...)
\t\t\tif err != nil {
\t\t\t\treturn err
\t\t\t}
\t\t} else if bctx == nil {
\t\t\tbctx = dockerui.DefaultMainContext(opts...)
\t\t}

\t\tbuildContext.Output = bctx.Output()
\t}
"""
if text.count(old) != 1:
    raise SystemExit("final context materialization block not found exactly once")
text = text.replace(old, new, 1)

path.write_text(text)
