"""GTK presentation for Virtualbox IPs; network detection lives in vbox_network.

The window uses the desktop's GTK/libadwaita theme. Only the temporary copy
confirmation has its own color; there are no global desktop style overrides.
"""
from pathlib import Path

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango

from vbox_network import AdapterAddress

APP_ID = 'io.github.solrojo.VirtualBoxIPs'
WINDOW_TITLE = 'Virtualbox'
COPY_FEEDBACK_MILLISECONDS = 1500
TABLE_MAX_WIDTH = 760
TABLE_MAX_HEIGHT = 320


class CopyIpButton(Gtk.Button):
    """Copy a single IP and show a green check for 1.5 seconds.

    Repeated clicks restart the timer. Unrealizing the button cancels the timer,
    so closing the window never leaves callbacks holding on to detached widgets.
    """

    def __init__(self, address: str):
        super().__init__(icon_name='edit-copy-symbolic', tooltip_text='Copy IP',
                         css_classes=['flat', 'vbox-ip-copy'])
        self._address = address
        self._reset_source = 0
        self.update_property([Gtk.AccessibleProperty.LABEL], ['Copy IP address'])
        self.connect('clicked', self._copy_address)
        self.connect('unrealize', self._cancel_feedback)

    def _copy_address(self, _button):
        try:
            self.get_clipboard().set(self._address)
        except GLib.Error:
            self.set_tooltip_text('Could not copy IP')
            return
        if self._reset_source:
            GLib.source_remove(self._reset_source)
        self.set_icon_name('emblem-ok-symbolic')
        self.add_css_class('copied')
        self.set_tooltip_text('Copied')
        self.update_property([Gtk.AccessibleProperty.LABEL], ['IP address copied'])
        self._reset_source = GLib.timeout_add(
            COPY_FEEDBACK_MILLISECONDS, self._reset_feedback,
        )

    def _reset_feedback(self):
        self._reset_source = 0
        self.set_icon_name('edit-copy-symbolic')
        self.remove_css_class('copied')
        self.set_tooltip_text('Copy IP')
        self.update_property([Gtk.AccessibleProperty.LABEL], ['Copy IP address'])
        return GLib.SOURCE_REMOVE

    def _cancel_feedback(self, _button):
        if self._reset_source:
            GLib.source_remove(self._reset_source)
        self._reset_feedback()


class AdapterTable(Gtk.Grid):
    """A centered VM / Adapter / IP table, with one copy button per IP."""

    def __init__(self, rows: list[AdapterAddress]):
        super().__init__(column_spacing=24, row_spacing=8,
                         margin_top=12, margin_bottom=12,
                         margin_start=20, margin_end=20)
        for column, title in enumerate(('VM', 'Adapter', 'IP')):
            self.attach(Gtk.Label(label=title, xalign=0.5, hexpand=True,
                                  css_classes=['heading']), column, 0, 1, 1)
        for index, row in enumerate(rows, start=1):
            for column, value in enumerate((row.vm, row.adapter)):
                label = Gtk.Label(label=value, xalign=0.5, hexpand=True,
                                  selectable=False, max_width_chars=28,
                                  ellipsize=Pango.EllipsizeMode.MIDDLE,
                                  tooltip_text=value)
                self.attach(label, column, index, 1, 1)
            ip_cell = Gtk.Box(spacing=6, halign=Gtk.Align.CENTER)
            ip_cell.append(Gtk.Label(label=row.ip, selectable=False))
            ip_cell.append(CopyIpButton(row.ip))
            self.attach(ip_cell, 2, index, 1, 1)


class VirtualBoxWindow(Adw.ApplicationWindow):
    """A content-sized native window with a VirtualBox icon in the title bar."""

    def __init__(self, application, rows: list[AdapterAddress], notice: str = ''):
        super().__init__(application=application, title=WINDOW_TITLE, resizable=False)
        layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        header = Adw.HeaderBar(show_start_title_buttons=False, show_end_title_buttons=False)
        title = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        title.append(Gtk.Image(icon_name='virtualbox', pixel_size=20))
        title.append(Gtk.Label(label=WINDOW_TITLE, css_classes=['heading']))
        header.set_title_widget(title)
        layout.append(header)

        if rows:
            table = AdapterTable(rows)
            scroll = Gtk.ScrolledWindow(
                propagate_natural_width=True, propagate_natural_height=True,
                max_content_width=TABLE_MAX_WIDTH, max_content_height=TABLE_MAX_HEIGHT,
            )
            scroll.set_child(table)
            _, height, _, _ = table.measure(Gtk.Orientation.VERTICAL, -1)
            scroll.set_min_content_height(min(height, TABLE_MAX_HEIGHT))
            layout.append(scroll)
        else:
            layout.append(Gtk.Label(
                label=notice or 'No connected VM adapters with a published IP address.',
                wrap=True, max_width_chars=48, justify=Gtk.Justification.CENTER,
                margin_start=24, margin_end=24, margin_top=24, margin_bottom=24,
            ))
        layout.append(Gtk.Separator())
        close = Gtk.Button(label='Close', css_classes=['flat'], height_request=48)
        close.connect('clicked', self._close)
        layout.append(close)
        self.set_content(layout)
        keyboard = Gtk.EventControllerKey()
        keyboard.connect('key-pressed', self._on_key_pressed)
        self.add_controller(keyboard)

    def _close(self, _button):
        self.close()

    def _on_key_pressed(self, _controller, key, _keycode, _state):
        if key == Gdk.KEY_Escape:
            self.close()
            return Gdk.EVENT_STOP
        return Gdk.EVENT_PROPAGATE


def show_window(rows: list[AdapterAddress], notice: str = '') -> int:
    """Run one identifiable application; a second invocation raises its window."""
    app = Adw.Application(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def activate(application):
        existing = application.get_active_window()
        if existing:
            existing.present()
            return
        Gtk.Window.set_default_icon_name('virtualbox')
        css = Gtk.CssProvider()
        css.load_from_path(str(Path(__file__).with_name('vbox-window.css')))
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
        VirtualBoxWindow(application, rows, notice).present()

    app.connect('activate', activate)
    return app.run([])
