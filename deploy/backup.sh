#!/bin/sh
set -eu
umask 077

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
destination="/backups/gyminators-${stamp}.dump"
media_destination="/backups/gyminators-media-${stamp}.tar.gz"
database_temp="${destination}.tmp"
media_temp="${media_destination}.tmp"

cleanup() {
  rm -f "$database_temp" "$media_temp"
}
trap cleanup EXIT HUP INT TERM

if [ ! -d /media ]; then
  echo "Media volume is not mounted at /media; refusing an incomplete backup." >&2
  exit 1
fi

pg_dump --format=custom --no-owner --file="$database_temp"
tar -C /media -czf "$media_temp" .

mv "$database_temp" "$destination"
mv "$media_temp" "$media_destination"

find /backups -type f -name 'gyminators-*.dump' -mtime +30 -delete
find /backups -type f -name 'gyminators-media-*.tar.gz' -mtime +30 -delete

trap - EXIT HUP INT TERM
echo "Database backup written to $destination"
echo "Media backup written to $media_destination"
