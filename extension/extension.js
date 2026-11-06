import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';

export default class VirtualBoxIps extends Extension {
    enable() {
        this._rows = [];
        this._indicator = new PanelMenu.Button(0.5, 'Virtualbox - VMs', true);
        this._indicator.add_child(new St.Icon({
            icon_name: 'virtualbox',
            style: '-st-icon-style: regular;',
            style_class: 'system-status-icon',
        }));
        this._indicator.connect('notify::hover', () => this._updateTooltip());
        this._indicator.connect('button-press-event', (_actor, event) => {
            if (event.get_button() !== 1)
                return Clutter.EVENT_PROPAGATE;
            this._openDialog();
            return Clutter.EVENT_STOP;
        });
        this._indicator.connect('key-press-event', (_actor, event) => {
            if (![Clutter.KEY_Return, Clutter.KEY_KP_Enter, Clutter.KEY_space].includes(event.get_key_symbol()))
                return Clutter.EVENT_PROPAGATE;
            this._openDialog();
            return Clutter.EVENT_STOP;
        });
        Main.panel.addToStatusArea(this.uuid, this._indicator, 1, 'right');
        this._indicator.hide();
        this._refresh();
        this._pollId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 10, () => {
            this._refresh();
            return GLib.SOURCE_CONTINUE;
        });
    }

    _refresh() {
        if (this._process)
            return;
        const command = this.dir.get_child('virtualbox-ips').get_path();
        let process;
        try {
            process = Gio.Subprocess.new([command, '--json'],
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE);
        } catch (error) {
            console.warn(`VirtualBox IPs: ${error.message}`);
            return;
        }
        this._process = process;
        process.communicate_utf8_async(null, null, (proc, result) => {
            if (this._process !== proc)
                return;
            this._process = null;
            let rows = [];
            try {
                const [, stdout] = proc.communicate_utf8_finish(result);
                if (proc.get_successful())
                    rows = JSON.parse(stdout);
            } catch (error) {
                console.warn(`VirtualBox IPs: ${error.message}`);
            }
            if (JSON.stringify(rows) === JSON.stringify(this._rows))
                return;
            this._rows = rows;
            this._indicator.visible = rows.length > 0;
            this._updateTooltip();
        });
    }

    _list(styleClass) {
        const list = new St.BoxLayout({vertical: true, style_class: styleClass});
        for (const [name, address] of this._rows) {
            const row = new St.BoxLayout({style_class: 'vbox-ip-row'});
            row.add_child(new St.Label({text: name, style_class: 'vbox-ip-name'}));
            row.add_child(new St.Label({text: address, style_class: 'vbox-ip-address'}));
            list.add_child(row);
        }
        return list;
    }

    _hideTooltip() {
        if (!this._tooltip)
            return;
        Main.layoutManager.removeChrome(this._tooltip);
        this._tooltip.destroy();
        this._tooltip = null;
    }

    _updateTooltip() {
        this._hideTooltip();
        if (!this._indicator?.hover || this._dialog || !this._rows.length)
            return;

        const tooltip = this._list('vbox-ip-tooltip');
        this._tooltip = tooltip;
        Main.layoutManager.addTopChrome(tooltip, {affectsInputRegion: false});
        const [x, y] = this._indicator.get_transformed_position();
        const [width, height] = this._indicator.get_transformed_size();
        const [, naturalWidth] = tooltip.get_preferred_width(-1);
        const monitor = Main.layoutManager.findMonitorForActor(this._indicator);
        const left = x + (width - naturalWidth) / 2;
        tooltip.set_position(monitor
            ? Math.max(monitor.x + 8, Math.min(left, monitor.x + monitor.width - naturalWidth - 8))
            : left, y + height + 6);
    }

    _openDialog() {
        if (this._dialog || !this._rows.length)
            return;
        this._hideTooltip();
        const command = this.dir.get_child('virtualbox-ips').get_path();
        try {
            const dialog = Gio.Subprocess.new([command, '--panel-list'], Gio.SubprocessFlags.STDIN_PIPE);
            this._dialog = dialog;
            dialog.communicate_utf8_async(JSON.stringify(this._rows), null, (proc, result) => {
                try {
                    proc.communicate_utf8_finish(result);
                } catch (error) {
                    console.warn('VirtualBox IPs: ' + error.message);
                }
                if (this._dialog === proc)
                    this._dialog = null;
            });
        } catch (error) {
            console.warn('VirtualBox IPs: ' + error.message);
        }
    }

    disable() {
        if (this._pollId)
            GLib.Source.remove(this._pollId);
        this._pollId = 0;
        const process = this._process;
        this._process = null;
        process?.force_exit();
        this._hideTooltip();
        this._dialog?.force_exit();
        this._dialog = null;
        this._indicator?.destroy();
        this._indicator = null;
        this._rows = [];
    }
}
