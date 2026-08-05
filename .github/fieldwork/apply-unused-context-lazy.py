#!/usr/bin/env python3
"""Apply the reviewed lazy default-context candidate with exact source anchors."""

from pathlib import Path


SOURCE = Path("frontend/dockerfile/dockerfile2llb/convert.go")


def replace_exact(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one replacement site, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    text = SOURCE.read_text(encoding="utf-8")

    text = replace_exact(
        text,
        '''\tvar dockerIgnoreMatcher *patternmatcher.PatternMatcher
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
''',
        '''\tvar dockerIgnoreMatcherOnce sync.Once
\tvar dockerIgnoreMatcher *patternmatcher.PatternMatcher
\tvar dockerIgnoreMatcherErr error
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
''',
        "lazy dockerignore matcher",
    )

    text = replace_exact(
        text,
        "\t\t\tdockerIgnoreMatcher: dockerIgnoreMatcher,\n",
        "\t\t\tdockerIgnoreMatcher: getDockerIgnoreMatcher,\n",
        "dispatch option matcher",
    )

    text = replace_exact(
        text,
        '''\topts := filterPaths(ctxPaths)
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
''',
        '''\topts := filterPaths(ctxPaths)
\tif len(ctxPaths) > 0 || target.scanContext {
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
''',
        "lazy main context",
    )

    text = replace_exact(
        text,
        "\tdockerIgnoreMatcher *patternmatcher.PatternMatcher\n",
        "\tdockerIgnoreMatcher func() (*patternmatcher.PatternMatcher, error)\n",
        "matcher type",
    )

    text = replace_exact(
        text,
        '''\tcase *instructions.AddCommand:
\t\terr = dispatchCopy(d, copyConfig{
''',
        '''\tcase *instructions.AddCommand:
\t\tignoreMatcher, err := opt.dockerIgnoreMatcher()
\t\tif err != nil {
\t\t\treturn err
\t\t}
\t\terr = dispatchCopy(d, copyConfig{
''',
        "add matcher acquisition",
    )

    text = replace_exact(
        text,
        "\t\t\tignoreMatcher:   opt.dockerIgnoreMatcher,\n",
        "\t\t\tignoreMatcher:   ignoreMatcher,\n",
        "add matcher use",
    )

    text = replace_exact(
        text,
        '''\t\t} else {
\t\t\tignoreMatcher = opt.dockerIgnoreMatcher
\t\t}
''',
        '''\t\t} else {
\t\t\tignoreMatcher, err = opt.dockerIgnoreMatcher()
\t\t\tif err != nil {
\t\t\t\treturn err
\t\t\t}
\t\t}
''',
        "copy matcher acquisition",
    )

    SOURCE.write_text(text, encoding="utf-8")
    print("applied lazy default-context candidate")


if __name__ == "__main__":
    main()
