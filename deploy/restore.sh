#!/bin/sh
set -eu

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  echo "Usage: restore /backups/gyminators-TIMESTAMP.dump [/backups/gyminators-media-TIMESTAMP.tar.gz]" >&2
  exit 1
fi

database_backup="$1"
media_root="/media"

if [ "$#" -eq 2 ]; then
  media_backup="$2"
else
  database_name="$(basename "$database_backup")"
  case "$database_name" in
    gyminators-*.dump)
      stamp="${database_name#gyminators-}"
      stamp="${stamp%.dump}"
      media_backup="$(dirname "$database_backup")/gyminators-media-${stamp}.tar.gz"
      ;;
    *)
      echo "Cannot infer the media backup name from $database_backup; provide it explicitly." >&2
      exit 1
      ;;
  esac
fi

if [ ! -r "$database_backup" ]; then
  echo "Database backup is not readable: $database_backup" >&2
  exit 1
fi
if [ ! -r "$media_backup" ]; then
  echo "Matching media backup is not readable: $media_backup" >&2
  exit 1
fi
if [ ! -d "$media_root" ] || [ "$media_root" = "/" ]; then
  echo "Media volume is not safely mounted at $media_root." >&2
  exit 1
fi

listing="$(mktemp)"
staging="$media_root/.restore-$$"
cleanup() {
  rm -f "$listing"
  rm -rf "$staging"
}
trap cleanup EXIT HUP INT TERM

# Validate and stage uploaded files before changing either live data store.
tar -tzf "$media_backup" > "$listing"
if grep -Eq '(^/|(^|/)\.\.(/|$))' "$listing"; then
  echo "Media archive contains an unsafe path; restore aborted." >&2
  exit 1
fi
if tar -tvzf "$media_backup" | grep -Eq '^[^d-]'; then
  echo "Media archive contains a link or special file; restore aborted." >&2
  exit 1
fi
mkdir "$staging"
tar -xzf "$media_backup" -C "$staging"

pg_restore --exit-on-error --clean --if-exists --no-owner --dbname="$PGDATABASE" "$database_backup"

# The application must be stopped while this replacement is performed.
for path in "$media_root"/* "$media_root"/.[!.]* "$media_root"/..?*; do
  [ -e "$path" ] || continue
  [ "$path" = "$staging" ] && continue
  rm -rf "$path"
done
for path in "$staging"/* "$staging"/.[!.]* "$staging"/..?*; do
  [ -e "$path" ] || continue
  mv "$path" "$media_root"/
done

rm -rf "$staging"
rm -f "$listing"
trap - EXIT HUP INT TERM

echo "Database restored from $database_backup"
echo "Uploaded media restored from $media_backup"
