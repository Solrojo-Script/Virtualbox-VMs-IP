# Virtualbox IPs

A GNOME Shell extension that shows the IP addresses of VirtualBox virtual machines in the top bar. The icon appears when the extension detects at least one address.

- Hover over the icon to see the virtual machines and their IP addresses.
- Click the icon to open **Virtualbox - VMs**. The table adjusts to its contents, and each row has a button to copy that VM's addresses.

## Requirements

- GNOME Shell 46, the version declared by the extension.
- VirtualBox installed on the host, with `VBoxManage` available to your GNOME user.
- Python 3 with PyGObject, GTK 4, and libadwaita. On Zorin OS and Ubuntu, the packages are `python3-gi`, `gir1.2-gtk-4.0`, and `gir1.2-adw-1`.
- Guest Additions in each VM that should report its IP addresses. The guest needs a configured network interface and must publish its network properties.

## Installation

1. Download or clone this repository and open a terminal in its directory.
2. Run the installer as your regular user.

   ```sh
   ./install.sh
   ```

3. Log out and back in so GNOME loads the extension files.
4. Enable **Virtualbox IPs** in the **Extensions** app, or run:

   ```sh
   gnome-extensions enable virtualbox-ips@solrojo
   ```

5. Start a VM. The extension checks VirtualBox when enabled and every ten seconds after that.

To update, run the installer again and log out and back in.

## Troubleshooting

If the indicator does not appear, run these commands from the same user session where VirtualBox is running:

```sh
VBoxManage list runningvms
"${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/virtualbox-ips@solrojo/virtualbox-ips"
```

If VirtualBox lists a running VM but the helper reports no IP address, check the network configuration and the Guest Additions service inside the guest. The indicator appears as soon as the helper finds an address.

## Uninstallation

Disable the extension and remove its installation directory.

```sh
gnome-extensions disable virtualbox-ips@solrojo
rm -r -- "${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/virtualbox-ips@solrojo"
```
