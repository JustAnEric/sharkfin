from importlib import import_module
from typing import Optional
import getpass, os, sys, subprocess, json, datetime, importlib.util, uuid

try:
    import win32job
except:
    win32job = None

class Mod:
    def __init__(self, folder_name: str, name: str, description: str, author: str, version: str, entrypoint: str = "main", job_name: str = ""):
        self.folder_name = folder_name
        self.name = name
        self.description = description
        self.author = author
        self.version = version
        self.entrypoint = entrypoint
        self.job_name = job_name
        self.proc : subprocess.Popen | None = None
        
        self.mod_event_handlers = {}
        self.assets = []  # hold references to assets like servers so they don't get GC'd
        
        self.current_log_file = f"{datetime.datetime.now().isoformat()}.log".replace(":", "-")
        
    @property
    def info(self) -> str:
        return f"{self.name} v{self.version} by {self.author}: {self.description}"
    
    @property
    def mod_location(self) -> str:
        return f"mods.{self.name}"
    
    @property
    def mod_location_with_entrypoint(self) -> str:
        return f"mods.{self.name}.{self.entrypoint}"
    
    @property
    def mod_config(self) -> Optional[dict]:
        try:
            with open(os.path.join(self.mod_path, "manifest.json"), "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading manifest for mod '{self.name}': {e}")
            return None
    
    @property
    def mod_path(self) -> str:
        frozen_config = f"C:\\Users\\{getpass.getuser()}\\AppData\\Local\\sharkfin"
        def resource(path: str):
            return os.path.abspath(os.path.join(os.path.dirname(__file__), path))
        def is_frozen():
            """Check if the script is running in a frozen environment (like PyInstaller)."""
            return getattr(sys, 'frozen', False)
        if is_frozen():
            return os.path.join(frozen_config, "mods", self.name)
        else:
            return resource(os.path.join("mods", self.name))
        
    @property
    def is_running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None
    
    @property
    def loaded(self):
        #try:
        #    mod = import_module(self.mod_location_with_entrypoint, package=".")
        #    return getattr(mod, "Mod", None)
        #except ImportError:
        #    return None
        #except Exception as e:
        #    print(f"Error checking mod '{self.name}': {e}")
        #    return e
        return True
        
    def log_info(self, context: str,  log: str):
        d = datetime.datetime.now().isoformat().replace(":", "-")
        print(os.path.exists(os.path.join(self.mod_path, self.current_log_file)), self.mod_path, self.current_log_file)
        if not os.path.exists(os.path.join(self.mod_path, self.current_log_file)):
            with open(os.path.join(self.mod_path, self.current_log_file), "w") as f:
                f.write(f"[SHARKFIN:{context.upper()}@{d}] {log}")
                f.close()
            return
        with open(os.path.join(self.mod_path, self.current_log_file), "a+") as f:
            f.write(f"\n[SHARKFIN:{context.upper()}@{d}] {log}")
            f.close()
        
    def send(self, obj):
        if not self.is_running or not self.proc:
            return False
        try:
            self.proc.stdin.write(json.dumps(obj) + "\n")
            self.proc.stdin.flush()
        except Exception as e:
            print("send failed:", e)
            
    def event(self, command: str):
        def decorator(callback):
            if command not in self.mod_event_handlers:
                self.mod_event_handlers[command] = []
            self.mod_event_handlers[command].append(callback)
            return callback
        return decorator
        
    def shutdown_mod(self):
        if not self.is_running or not self.proc:
            return False
        self.send({"event":"shutdown"})
        # give it a moment then terminate if needed
        try:
            self.proc.wait(timeout=3)
        except Exception:
            self.proc.terminate()
            self.proc.wait(timeout=2)
        return True
        
    def create_mod_job_object(self, name: str = None):
        if not win32job:
            return None
        job = win32job.CreateJobObject(None, name or self.job_name)
        # you can set limits here using SetInformationJobObject (advanced). for now we use job just so that
        # all children get killed when we close the job handle / exit.
        return job