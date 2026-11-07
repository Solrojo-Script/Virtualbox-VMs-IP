#!/bin/sh
set -eu

source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/extension
uuid=virtualbox-ips@solrojo
destination=${XDG_DATA_HOME:-"$HOME/.local/share"}/gnome-shell/extensions/$uuid

if [ "$(id -u)" -eq 0 ]; then
    printf '%s\n' 'Run the installer as your regular GNOME user.' >&2
    exit 1
fi

for command in VBoxManage python3 gnome-extensions; do
    if ! command -v "$command" >/dev/null 2>&1; then
        printf 'Missing command: %s. See the requirements in the README.\n' "$command" >&2
        exit 1
    fi
done

python3 - <<'PY'
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk
PY

install -d "$destination"
install -m 755 "$source_dir/virtualbox-ips" "$destination/"
install -m 644 "$source_dir/vbox_network.py" "$source_dir/vbox_window.py" \
    "$source_dir/vbox-window.css" "$destination/"
install -m 644 "$source_dir/metadata.json" "$source_dir/stylesheet.css" "$destination/"
install -m 644 "$source_dir/extension.js" "$destination/"
python3 - "$destination" <<'PY'
import os
from pathlib import Path
import sys
data = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share'))
applications = data / 'applications'
applications.mkdir(parents=True, exist_ok=True)
helper = str(Path(sys.argv[1]) / 'virtualbox-ips')
for character in ('\\', '"', '`', '$'):
    helper = helper.replace(character, '\\' + character)
(applications / 'io.github.solrojo.VirtualBoxIPs.desktop').write_text(
    '[Desktop Entry]\nType=Application\nName=Virtualbox\nIcon=virtualbox\n'
    f'Exec=python3 "{helper}" --gui\nNoDisplay=true\nTerminal=false\n')
PY
printf 'Installed in %s\n' "$destination"
printf '%s\n' 'Log out and back in, then enable Virtualbox IPs in the Extensions app.'
