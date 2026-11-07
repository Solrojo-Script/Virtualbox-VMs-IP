# Virtualbox IPs

A GNOME Shell extension that shows the addresses of running VirtualBox VMs in the top bar, without opening their guest consoles. The indicator appears only when at least one connected VM adapter has a published, matching IP address.

- Hover over the indicator to see each VM, adapter, and IP.
- Click it to open **Virtualbox**, with a VirtualBox icon in its title bar.
- The window has three centered columns: **VM**, **Adapter**, and **IP**.
- Each IP has its own copy button. After copying, the button shows a **green check for 1.5 seconds**, then returns to the copy icon. Clicking again restarts this confirmation.
- Close the window with **Close** or **Esc**. The table sizes itself to its contents and scrolls when needed.

## How adapters are detected

Guest Additions report all guest network interfaces, which can include Docker bridges. Their enumeration order is **not** the order of the adapters in VirtualBox settings. The extension therefore does not identify a NIC by its guest-property index, interface name, or subnet.

For each running VM, the helper:

1. Reads `VBoxManage showvminfo <uuid> --machinereadable` to obtain enabled adapters, their MAC addresses, and virtual cable state.
2. Reads `VBoxManage guestproperty enumerate <uuid> --old-format` for the guest interfaces, names, MACs, status, and IPs.
3. Matches each guest interface's MAC to exactly one enabled, cable-connected VirtualBox adapter.
4. Excludes interfaces explicitly reported as down, unmatched interfaces, and adapters with ambiguous duplicate MACs.
5. Validates and deduplicates the addresses. Loopback, unspecified, multicast, and link-local addresses are omitted. Private addresses are allowed.

For a typical guest with `enp0s3`, `enp0s8`, `docker0`, and `br-…`, the two matching virtual network cards are shown; the separate Docker bridge MACs are not.

**One row represents one adapter/IP pair.** A VM with two connected adapters has two rows. An adapter with several published addresses, such as IPv4 and IPv6, has a separate row and copy button for each address. The VM and adapter names repeat to make every row unambiguous.

### Limitations

- Guest Additions must publish the interface MAC and IP. A missing MAC is never guessed from an index; that interface is omitted.
- Some guest platforms do not publish interface names. A matched card is then called **Adapter 1**, **Adapter 2**, etc., using its VirtualBox slot.
- If the guest deliberately changes a card's MAC so it no longer matches the VM settings, that interface is omitted. A bridge deliberately reusing a VM card's MAC cannot be distinguished from that card using these properties alone.
- Results are current as reported by Guest Additions; their own update interval can introduce a short delay. Saved `.vbox` properties and old log files are not used as proof that a VM or address is currently active.
- No network scanning or commands inside the guest are performed. VM configuration and guest networking are never changed.

The matching fields are documented in VirtualBox's own source: [VM adapter information](https://github.com/VirtualBox/virtualbox/blob/master/src/VBox/Frontends/VBoxManage/VBoxManageInfo.cpp) and [Guest Additions network properties](https://github.com/VirtualBox/virtualbox/blob/master/src/VBox/Additions/common/VBoxService/VBoxServiceVMInfo.cpp).

## Requirements

- GNOME Shell 46, the version declared by the extension.
- VirtualBox on the host, with `VBoxManage` available to your GNOME user.
- Python 3.10 or later, PyGObject, GTK 4, and libadwaita. On Zorin OS/Ubuntu:

  ```sh
  sudo apt install python3 python3-gi gir1.2-gtk-4.0 gir1.2-adw-1
  ```

- Guest Additions running in each VM that should report addresses.

## Installation and updates

1. Download or clone this repository and open a terminal in it.
2. Run the installer as your regular desktop user:

   ```sh
   ./install.sh
   ```

3. Log out and back in so GNOME Shell loads the updated JavaScript.
4. Enable **Virtualbox IPs** in the **Extensions** app, or run:

   ```sh
   gnome-extensions enable virtualbox-ips@solrojo
   ```

5. Start a VM with a connected network adapter and functioning Guest Additions. The extension checks immediately when enabled and every ten seconds afterward.

To update, repeat the installation and log out and back in. Do not run the installer with `sudo`.

The installer copies the extension and its helper modules to:

```text
${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/virtualbox-ips@solrojo/
```

It also registers a hidden desktop entry at:

```text
${XDG_DATA_HOME:-$HOME/.local/share}/applications/io.github.solrojo.VirtualBoxIPs.desktop
```

This gives GNOME a window identity and icon without adding a Wofi launcher. The helper's network queries do not require GTK; GTK is loaded only when opening its window.

## Troubleshooting

Run these commands as the same user who runs VirtualBox:

```sh
VBoxManage list runningvms
"${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/virtualbox-ips@solrojo/virtualbox-ips" --adapter-json
```

For a VM that is missing, compare its current adapter settings and guest properties:

```sh
VBoxManage showvminfo "VM name" --machinereadable
VBoxManage guestproperty enumerate "VM name" --old-format
```

Check `nicN`, `macaddressN`, and `cableconnectedN` against `/VirtualBox/GuestInfo/Net/<index>/MAC`, `/Name`, `/Status`, and `/V4/IP`. Do not assume that `<index>` equals `N - 1`.

A query failure in one VM does not discard successfully detected rows from other VMs. The command prints diagnostic messages to stderr and exits with an error if a query failed and no usable rows remain. The indicator stays hidden when no valid address can be confirmed.

## Code layout and data contract

- `extension/extension.js`: GNOME indicator, polling, tooltip, and GTK process lifecycle. Uses asynchronous subprocesses; never blocks Shell on a VBoxManage query.
- `extension/virtualbox-ips`: small command-line entry point and JSON protocol compatibility.
- `extension/vbox_network.py`: typed data objects, read-only queries, MAC matching, filtering, and validation. No GTK dependency.
- `extension/vbox_window.py`: native GTK/libadwaita window, centered table, copy action, and feedback timer cleanup.
- `extension/vbox-window.css`: only the green copy-confirmation color; other window styling follows the desktop theme.
- `extension/stylesheet.css`: GNOME indicator and tooltip styling.
- `tests/test_network.py`: filtering and protocol regression tests with fictitious VM data.
- `tests/test_window.py`: GTK interaction tests for clipboard content, feedback reset, window sizing, and closing.

`--adapter-json` returns objects with string fields `vm`, `adapter`, and `ip`:

```json
[
  {"vm": "Example VM", "adapter": "enp0s3", "ip": "192.0.2.10"},
  {"vm": "Example VM", "adapter": "enp0s8", "ip": "198.51.100.11"}
]
```

`--panel-list` reads this array from stdin and opens the window. The legacy `--json` option still returns VM/IP pairs for older extension code already loaded in GNOME. When the window receives legacy pairs, it performs fresh adapter detection instead of guessing adapter names or displaying unfiltered old addresses.

## Tests

Network and protocol tests do not require VirtualBox or running VMs:

```sh
python3 -m unittest discover -s tests -p test_network.py -v
```

For GTK interaction tests on an isolated display, install Xvfb first:

```sh
sudo apt install xvfb xauth dbus-x11
GDK_BACKEND=x11 GTK_A11Y=none GSETTINGS_BACKEND=memory \
  dbus-run-session -- xvfb-run -a \
  python3 -m unittest discover -s tests -p test_window.py -v
```

The tests use documentation-only IP addresses and do not change any VM or desktop settings.

## Uninstallation

```sh
gnome-extensions disable virtualbox-ips@solrojo
rm -r -- "${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/virtualbox-ips@solrojo"
rm -f -- "${XDG_DATA_HOME:-$HOME/.local/share}/applications/io.github.solrojo.VirtualBoxIPs.desktop"
```
