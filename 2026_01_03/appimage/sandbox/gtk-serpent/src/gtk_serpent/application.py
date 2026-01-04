import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk


class GtkSerpentApplication(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.example.gtk-serpent")
        GLib.set_application_name('GTKSerpent awesome GTK4 application')

    def do_activate(self):
        window = Gtk.ApplicationWindow(application=self, title="GTKSerpent")
        window.present()

def main():
    app = GtkSerpentApplication()
    app.run()

if __name__ == "__main__":
    main()
