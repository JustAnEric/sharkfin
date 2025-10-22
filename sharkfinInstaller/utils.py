import getpass, os, sys, webview, win32com.client, shutil
from threading import Thread

frozen_config = f"C:\\Users\\{getpass.getuser()}\\AppData\\Local\\sharkfin"

#* use this when accessing files outside a frozen environment. (permanent, outside frozen)
#* else just use normal paths to get files inside a frozen environment (not-permanent, inside frozen)
def resource(path: str):
    return os.path.abspath(os.path.join(os.path.dirname(__file__), path))

def is_frozen():
    """Check if the script is running in a frozen environment (like PyInstaller)."""
    return hasattr(sys, 'frozen') and sys.frozen

def create_shortcut(target_path, shortcut_path, shortcut_name):
    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortcut(os.path.join(shortcut_path, f"{shortcut_name}.lnk"))
    shortcut.TargetPath = target_path
    shortcut.WorkingDirectory = os.path.dirname(target_path)
    shortcut.save()

def start(js_api):
    win = None
    win = webview.create_window(
        title="Sharkfin Installer",
        url=resource("sharkfin_install.html"), 
        js_api=js_api(win),
        width=800,
        height=600
    )
    webview.start(debug=False)