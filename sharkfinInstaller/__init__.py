from utils import is_frozen, resource, os, shutil, sys, frozen_config, create_shortcut, getpass, start, webview, Thread

class JS_API:
    def __init__(self, win):
        self.is_installed = False
        self.win : webview.Window = win
    
    def installSharkfin(self):
        os.makedirs(frozen_config, exist_ok=True)
        os.makedirs(os.path.join(frozen_config, "mods"), exist_ok=True)
        if os.path.exists(resource("Sharkfin.exe")) and os.path.isfile(resource("Sharkfin.exe")):
            shutil.copy(resource("Sharkfin.exe"), os.path.join(frozen_config, "Sharkfin.exe"))
            create_shortcut(
                target_path=os.path.join(frozen_config, "Sharkfin.exe"),
                shortcut_path=f"C:\\Users\\{getpass.getuser()}\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs",
                shortcut_name="Sharkfin"
            )
            self.is_installed = True
            return "Sharkfin installed successfully."
        else:
            self.is_installed = False
            print("Sharkfin.exe not found in resources. Please ensure the file exists.")
            return "ERR:Sharkfin.exe not found in resources. Please ensure the file exists."
        
    def closeInstallerWithOptions(self, options):
        if options.get("openSharkfin", False) and self.is_installed:
            Thread(target=os.startfile, args=[os.path.join(frozen_config, "Sharkfin.exe")]).start()
        self.win.destroy()
        sys.exit(0)
    
    def isInstalled(self):
        return self.is_installed

if __name__ == "__main__":
    if not is_frozen():
        print("This module is not intended to be run directly. Please use the compiled installer executable.")
        sys.exit(1)
    start(JS_API)