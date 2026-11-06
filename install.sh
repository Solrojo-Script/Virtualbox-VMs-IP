#!/bin/sh
set -eu

source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/extension
uuid=virtualbox-ips@solrojo
destination=${XDG_DATA_HOME:-"$HOME/.local/share"}/gnome-shell/extensions/$uuid

if [ "$(id -u)" -eq 0 ]; then
    printf '%s\n' 'Ejecuta el instalador con tu usuario de GNOME.' >&2
    exit 1
fi

for command in VBoxManage python3 gnome-extensions; do
    if ! command -v "$command" >/dev/null 2>&1; then
        printf 'Falta el comando %s. Consulta los requisitos del README.\n' "$command" >&2
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
install -m 644 "$source_dir/metadata.json" "$source_dir/stylesheet.css" "$destination/"
install -m 644 "$source_dir/extension.js" "$destination/"
printf 'Instalado en %s\n' "$destination"
printf '%s\n' 'Cierra sesión y vuelve a entrar. Después, activa Virtualbox IPs en Extensiones.'
