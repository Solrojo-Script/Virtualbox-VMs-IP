# Virtualbox IPs

Extensión para GNOME Shell que muestra las direcciones IP de las máquinas virtuales de VirtualBox en la barra superior. El icono aparece cuando se detecta al menos una dirección.

- Pasa el cursor por el icono para ver las máquinas y sus IP.
- Haz clic para abrir **Virtualbox - VMs**. La tabla se ajusta al contenido y cada fila tiene un botón para copiar las direcciones de esa VM.

## Requisitos

- GNOME Shell 46, la versión declarada por la extensión.
- VirtualBox instalado en el equipo anfitrión, con `VBoxManage` disponible para el usuario de GNOME.
- Python 3 con PyGObject, GTK 4 y libadwaita. En Zorin OS y Ubuntu los paquetes son `python3-gi`, `gir1.2-gtk-4.0` y `gir1.2-adw-1`.
- Guest Additions en cada máquina invitada que deba publicar sus IP. El invitado debe tener una interfaz configurada y estar publicando sus propiedades de red.

## Instalación

1. Descarga el repositorio y abre una terminal en su carpeta.
2. Ejecuta el instalador con tu usuario habitual.

   ```sh
   ./install.sh
   ```

3. Cierra sesión y vuelve a entrar para que GNOME lea los archivos.
4. Activa **Virtualbox IPs** desde **Extensiones** o ejecuta lo siguiente.

   ```sh
   gnome-extensions enable virtualbox-ips@solrojo
   ```

5. Inicia una VM. La extensión consulta VirtualBox al activarse y después cada diez segundos.

Para actualizar, ejecuta de nuevo el instalador y vuelve a iniciar sesión.

## Si el indicador no aparece

Ejecuta estas consultas desde la sesión donde tienes abierto VirtualBox.

```sh
VBoxManage list runningvms
"${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/virtualbox-ips@solrojo/virtualbox-ips"
```

Si una VM aparece como encendida pero sin IP publicada, comprueba la configuración de red y el servicio de Guest Additions dentro del invitado. El indicador solo aparece si la consulta devuelve alguna IP.

## Desinstalación

Desactiva la extensión y elimina la carpeta instalada.

```sh
gnome-extensions disable virtualbox-ips@solrojo
rm -r -- "${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/virtualbox-ips@solrojo"
```
