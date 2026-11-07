"""GTK interaction tests. Run on an isolated display, as shown in the README."""
import sys
from pathlib import Path
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'extension'))
from vbox_network import AdapterAddress
from vbox_window import Adw, CopyIpButton, Gdk, Gio, GLib, Gtk, VirtualBoxWindow


def wait_until(predicate, seconds=3):
    """Let clipboard callbacks and feedback timers run without blocking GTK."""
    deadline = time.monotonic() + seconds
    context = GLib.MainContext.default()
    while time.monotonic() < deadline:
        while context.pending():
            context.iteration(False)
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError('GTK condition did not become true before the deadline.')


def descendants(widget):
    yield widget
    child = widget.get_first_child()
    while child:
        yield from descendants(child)
        child = child.get_next_sibling()


class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Adw.init()
        cls.app = Adw.Application(application_id='io.github.solrojo.VirtualBoxIPs.Test',
                                  flags=Gio.ApplicationFlags.NON_UNIQUE)
        cls.app.register(None)

    def setUp(self):
        self.window = VirtualBoxWindow(self.app, [
            AdapterAddress('Example VM', 'enp0s3', '192.0.2.10'),
            AdapterAddress('Example VM', 'enp0s8', '198.51.100.11'),
        ])
        self.window.present()
        wait_until(lambda: self.window.get_mapped())

    def tearDown(self):
        self.window.close()
        wait_until(lambda: not self.window.get_visible())

    def test_title_columns_and_non_selectable_labels(self):
        widgets = list(descendants(self.window))
        labels = [widget for widget in widgets if isinstance(widget, Gtk.Label)]
        self.assertEqual(self.window.get_title(), 'Virtualbox')
        for text in ('VM', 'Adapter', 'IP', 'enp0s3', 'enp0s8'):
            self.assertIn(text, [label.get_label() for label in labels])
        self.assertFalse(any(label.get_selectable() for label in labels))
        self.assertEqual(sum(isinstance(widget, CopyIpButton) for widget in widgets), 2)
        self.assertLessEqual(self.window.get_width(), 800)
        self.assertLess(self.window.get_height(), 400)

    def test_copy_writes_one_ip_and_feedback_resets(self):
        button = next(widget for widget in descendants(self.window) if isinstance(widget, CopyIpButton))
        button.emit('clicked')
        self.assertEqual(button.get_icon_name(), 'emblem-ok-symbolic')
        self.assertTrue(button.has_css_class('copied'))
        received = []
        def read(clipboard, result):
            received.append(clipboard.read_text_finish(result))
        button.get_clipboard().read_text_async(None, read)
        wait_until(lambda: bool(received))
        self.assertEqual(received, ['192.0.2.10'])
        wait_until(lambda: button.get_icon_name() == 'edit-copy-symbolic')
        self.assertFalse(button.has_css_class('copied'))

    def test_repeated_copy_restarts_feedback_and_close_cancels_it(self):
        button = next(widget for widget in descendants(self.window) if isinstance(widget, CopyIpButton))
        button.emit('clicked')
        previous_source = button._reset_source
        button.emit('clicked')
        self.assertNotEqual(button._reset_source, previous_source)
        self.window.close()
        wait_until(lambda: button._reset_source == 0)
        self.assertFalse(button.has_css_class('copied'))

    def test_escape_closes_the_window(self):
        result = self.window._on_key_pressed(None, Gdk.KEY_Escape, 0, 0)
        self.assertTrue(result)
        wait_until(lambda: not self.window.get_visible())


if __name__ == '__main__':
    unittest.main()
