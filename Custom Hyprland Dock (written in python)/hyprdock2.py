import os
import sys
import subprocess
import json
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import Gtk, Gdk, GtkLayerShell, GLib

CONFIG_PATH = os.path.expanduser("~/.config/hyprdock.json")
ICON_SIZE = 34
HIDE_DELAY_MS = 500

# Default configuration if you start completely fresh
CLEAN_DEFAULT_CONFIG = [
    {"name": "Terminal", "icon": "utilities-terminal", "cmd": "kitty"},
    {"name": "Browser", "icon": "firefox", "cmd": "firefox"},
    {"name": "Discord", "icon": "discord", "cmd": "discord"}
]

# Pure black transparent aesthetics for the dock & manager
CSS_DATA = b"""
/* Main Dock Styling */
window {
    background-color: rgba(0, 0, 0, 0.65); /* Pure black, 65% transparent */
    border: 1px solid rgba(255, 255, 255, 0.05); /* Extremely subtle border */
    border-radius: 12px;
}
button {
    background: transparent;
    border: none;
    padding: 6px;
    margin: 2px;
}
button:hover {
    background-color: rgba(255, 255, 255, 0.1);
    border-radius: 8px;
}

/* Settings Manager Window Styling */
.mgr-win {
    background-color: #000000;
    color: #ffffff;
    padding: 15px;
}
.mgr-entry {
    background-color: #111111;
    color: white;
    border: 1px solid #222222;
    border-radius: 6px;
    padding: 8px;
    margin-bottom: 12px;
}
.mgr-btn {
    background-color: #1a1a1a;
    color: white;
    border: 1px solid #333333;
    border-radius: 6px;
    padding: 8px;
    font-weight: bold;
}
.mgr-btn:hover {
    background-color: #2a2a2a;
}
.remove-btn {
    background-color: #8c1515;
    border-color: #a51d24;
}
.remove-btn:hover {
    background-color: #a51d24;
}
"""

def load_config():
    """Loads the app list, generating a clean default if none exists."""
    if not os.path.exists(CONFIG_PATH):
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump(CLEAN_DEFAULT_CONFIG, f, indent=4)
        return CLEAN_DEFAULT_CONFIG
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return CLEAN_DEFAULT_CONFIG

def save_config(data):
    """Saves the app list to the JSON file."""
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=4)


class ManagerWindow(Gtk.Window):
    """The dark-themed UI to manage dock applications."""
    def __init__(self):
        super().__init__(title="HyprDock Settings")
        self.set_default_size(360, 450)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.get_style_context().add_class("mgr-win")
        
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vbox.set_border_width(15)
        self.add(vbox)
        
        # --- Current Apps Section ---
        vbox.pack_start(Gtk.Label(label="<b>Current Apps (Click to Delete):</b>", use_markup=True, xalign=0), False, False, 0)
        
        self.apps = load_config()
        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        
        for idx, app in enumerate(self.apps):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            row.set_margin_bottom(6)
            
            lbl = Gtk.Label(label=f"{app['name']}", xalign=0)
            rem_btn = Gtk.Button(label="Delete")
            rem_btn.get_style_context().add_class("mgr-btn")
            rem_btn.get_style_context().add_class("remove-btn")
            rem_btn.connect("clicked", self.on_remove_clicked, idx)
            
            row.pack_start(lbl, True, True, 0)
            row.pack_end(rem_btn, False, False, 0)
            listbox.add(row)
            
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(160)
        scrolled.add(listbox)
        vbox.pack_start(scrolled, True, True, 5)
        
        vbox.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 10)
        
        # --- Add New App Section ---
        vbox.pack_start(Gtk.Label(label="<b>Add New App:</b>", use_markup=True, xalign=0), False, False, 0)
        
        self.name_entry = Gtk.Entry(placeholder_text="App Name (e.g., Spotify)")
        self.name_entry.get_style_context().add_class("mgr-entry")
        vbox.pack_start(self.name_entry, False, False, 0)
        
        self.icon_entry = Gtk.Entry(placeholder_text="Icon Name (e.g., spotify)")
        self.icon_entry.get_style_context().add_class("mgr-entry")
        vbox.pack_start(self.icon_entry, False, False, 0)
        
        self.cmd_entry = Gtk.Entry(placeholder_text="Command (e.g., spotify)")
        self.cmd_entry.get_style_context().add_class("mgr-entry")
        vbox.pack_start(self.cmd_entry, False, False, 0)
        
        add_btn = Gtk.Button(label="Append to Dock")
        add_btn.get_style_context().add_class("mgr-btn")
        add_btn.connect("clicked", self.on_add_clicked)
        vbox.pack_start(add_btn, False, False, 5)
        
        self.show_all()

    def on_remove_clicked(self, button, idx):
        self.apps.pop(idx)
        save_config(self.apps)
        self.destroy()
        ManagerWindow()

    def on_add_clicked(self, button):
        name = self.name_entry.get_text().strip()
        icon = self.icon_entry.get_text().strip()
        cmd = self.cmd_entry.get_text().strip()
        if name and icon and cmd:
            self.apps.append({"name": name, "icon": icon, "cmd": cmd})
            save_config(self.apps)
            self.destroy()
            ManagerWindow()


class HyprDock(Gtk.Window):
    """The lightweight Wayland dock layer."""
    def __init__(self):
        super().__init__(title="HyprDock")
        self.hide_timeout_id = None
        self.last_mtime = 0

        # Enable Transparency
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual and screen.is_composited():
            self.set_visual(visual)

        # Layer Shell Setup for Hyprland
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_namespace(self, "hyprdock")
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.BOTTOM, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, False)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, False)

        # UI Container
        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.box.set_border_width(6)
        self.add(self.box)

        self.reload_dock_ui()

        # Apply Aesthetic Styling
        style_provider = Gtk.CssProvider()
        style_provider.load_from_data(CSS_DATA)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), style_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Autohide Hover Triggers
        self.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.connect("enter-notify-event", self.on_reveal)
        self.connect("leave-notify-event", self.on_handle_leave)
        
        # Hide instantly upon drawing
        self.connect("realize", lambda w: GLib.idle_add(self.execute_hide))
        
        # Lightweight Background Watcher: Checks for app updates every 2 seconds
        GLib.timeout_add_seconds(2, self.check_config_updates)

    def reload_dock_ui(self):
        """Re-draws the icons based on the configuration file."""
        for child in self.box.get_children():
            self.box.remove(child)

        apps = load_config()
        for app in apps:
            btn = Gtk.Button()
            btn.set_tooltip_text(app["name"])
            
            icon = Gtk.Image()
            icon.set_from_icon_name(app["icon"], Gtk.IconSize.LARGE_TOOLBAR)
            icon.set_pixel_size(ICON_SIZE)
            
            btn.add(icon)
            btn.connect("clicked", self.on_app_click, app["cmd"])
            self.box.pack_start(btn, False, False, 0)
        
        self.show_all()
        
        # Remember file state to avoid unnecessary reloading
        if os.path.exists(CONFIG_PATH):
            self.last_mtime = os.path.getmtime(CONFIG_PATH)

    def check_config_updates(self):
        """Silently checks if the JSON file was modified by the manager."""
        if os.path.exists(CONFIG_PATH):
            current_mtime = os.path.getmtime(CONFIG_PATH)
            if current_mtime != self.last_mtime:
                self.reload_dock_ui()
        return True

    def on_reveal(self, widget, event):
        if self.hide_timeout_id:
            GLib.source_remove(self.hide_timeout_id)
            self.hide_timeout_id = None
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.BOTTOM, 0)
        return True

    def on_handle_leave(self, widget, event):
        if self.hide_timeout_id:
            GLib.source_remove(self.hide_timeout_id)
        self.hide_timeout_id = GLib.timeout_add(HIDE_DELAY_MS, self.execute_hide)
        return True

    def execute_hide(self):
        height = self.get_allocated_height()
        # Leave a tiny 3px transparent trigger zone at the bottom of the screen
        hidden_margin = -(height - 3) if height > 3 else -45
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.BOTTOM, hidden_margin)
        self.hide_timeout_id = None
        return False

    def on_app_click(self, widget, command):
        subprocess.Popen(command.split(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    # 1. Boot up the Settings Manager if '--manage' is passed
    if len(sys.argv) > 1 and sys.argv[1] == "--manage":
        style_provider = Gtk.CssProvider()
        style_provider.load_from_data(CSS_DATA)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), style_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        ManagerWindow()
        Gtk.main()
        
    # 2. Boot up the actual background dock
    else:
        # Ensures no duplicate docks are running
        os.system("pkill -o -f 'python.*hyprdock.py'")
        win = HyprDock()
        win.connect("destroy", Gtk.main_quit)
        Gtk.main()
