#!/bin/sh
# Wrap the content of <main> in the Blueprint theme and write a standalone sheet.
# usage: sh new.sh <record-dir>/<explore|adr|build>.html "<title>" < body.html
set -e
die() { echo "new.sh: $*" >&2; exit 1; }
[ $# -eq 2 ] || die 'usage: sh new.sh <out.html> "<title>" < body.html'
out=$1
here=$(cd "$(dirname "$0")" && pwd)
body=$(cat)
[ -n "$(printf '%s' "$body" | tr -d ' \t\r\n')" ] || die "nothing on stdin; pipe in the sheet's <main> content"
if printf '%s' "$body" | grep -qiE '<(!doctype|html|head|body|main)[ >]'; then
  die "write only what goes inside <main>, not a full page"
fi
title_html=$(printf '%s' "$2" | tr '\n\r' '  ' | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g')
title_sed=$(printf '%s' "$title_html" | sed 's/[&|\\]/\\&/g')
mkdir -p "$(dirname "$out")"
{
  sed '/<main/q' "$here/template.html" | sed "s|<title>[^<]*</title>|<title>$title_sed</title>|"
  printf '%s\n' "$body"
  printf '</main>\n</div>\n</body>\n</html>\n'
} > "$out"

# index.html opens the furthest phase written so far (used by omp and static hosting).
rec=$(dirname "$out")
case $(basename "$out") in explore.html|adr.html|build.html)
  for s in build adr explore; do
    if [ -f "$rec/$s.html" ]; then
      printf '<!doctype html>\n<meta charset="utf-8">\n<meta http-equiv="refresh" content="0; url=%s.html">\n<title>%s</title>\n<a href="%s.html">Open %s.html</a>\n' \
        "$s" "$title_html" "$s" "$s" > "$rec/index.html"
      break
    fi
  done
esac
echo "$out"
