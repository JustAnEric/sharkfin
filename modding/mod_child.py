import sys
import os
import json
import traceback
import runpy
import types
from pathlib import Path
from typing import Any, Dict
from threading import Thread
from .SharkfinModAPI import fin, shark

accumulated_buf = []
stdin_ready = False

def send(ev: dict):
    """send json-lines back to manager via stdout (best-effort)."""
    try:
        sys.stdout.write(json.dumps(ev, default=str) + "\n")
        sys.stdout.flush()
    except Exception:
        pass
    
def listen():
    global stdin_ready, accumulated_buf
    while True:
        if stdin_ready:
            continue
        line = sys.stdin.readline()
        if not line:
            break
        try:
            msg = json.loads(line.strip())
            accumulated_buf.append(msg)
        except Exception as e:
            send({"event":"invalid_json", "raw":line.strip()})

def load_context_from_env() -> Dict[str, Any]:
    """manager can pass limited context (settings, permissions) via env var."""
    ctx_raw = os.environ.get("SHARKFIN_CONTEXT")
    if not ctx_raw:
        return {}
    try:
        return json.loads(ctx_raw)
    except Exception:
        send({"event":"warning", "message":"invalid_sharkfin_context"})
        return {}

def inject_sharkfin_api(context: Dict[str, Any]):
    """
    create a safe module named 'SharkfinModAPI' and insert it into sys.modules.
    expose minimal, non-blocking helpers. do NOT expose raw os/socket/ctypes access.
    """
    mod = types.ModuleType("SharkfinModAPI")

    # a tiny 'fin' object for logging and simple non-blocking emits
    class Fin:
        def log(self, level: str, message: str):
            # sends an api_log event to the manager; manager decides what to do with it
            send({"event":"log", "level": level, "message": message})

        def info(self, message: str):
            self.log("info", message)
        def warn(self, message: str):
            self.log("warn", message)
        def error(self, message: str):
            self.log("error", message)
        def debug(self, message: str):
            self.log("debug", message)

    # a tiny 'shark' object for read-only settings and metadata exposed by manager
    class Shark:
        def get_setting(self, key: str, default=None):
            settings = context.get("settings", {})
            return settings.get(key, default)

        def has_permission(self, name: str) -> bool:
            perms = context.get("permissions", [])
            return name in perms

    # attach to module
    mod.fin = fin()
    mod.shark = shark(mod.fin)

    # register early so "from SharkfinModAPI import fin, shark" works
    sys.modules["SharkfinModAPI"] = mod
    # also support lower-case import if mod uses snake-case (optional)
    # sys.modules["sharkfinmodapi"] = mod

def is_package_dir(p: Path) -> bool:
    return (p / "__init__.py").exists()

def find_entry_file(p: Path):
    for name in ("main.py", "mod.py"):
        cand = p / name
        if cand.exists():
            return cand
    for cand in sorted(p.glob("*.py")):
        return cand
    return None

def run_single_file(path: Path, context: Dict[str, Any]):
    send({"event":"start_single", "entry": str(path)})
    # inject safe API before executing the user's script
    inject_sharkfin_api(context)
    try:
        runpy.run_path(str(path), run_name="__main__")
        send({"event":"exited", "status":"ok"})
        send({"event":"stdin_ready", "status":"ok"})
        stdin_ready = True
        for m in accumulated_buf:
            # send the messages to the process
            send({"event":"message", "data":m})
        return 0
    except SystemExit as se:
        send({"event":"exited", "status":"sysexit", "code": int(getattr(se, 'code', 0) or 0)})
        return int(getattr(se, 'code', 0) or 0)
    except Exception as e:
        send({"event":"crash", "error": str(e), "traceback": traceback.format_exc()})
        return 2

def run_package(mod_dir: Path, context: Dict[str, Any]):
    parent = str(mod_dir.parent.resolve())
    pkg_name = mod_dir.name
    send({"event":"start_package", "package": pkg_name, "parent": parent})
    # ensure import context for relative imports
    if parent not in sys.path:
        sys.path.insert(0, parent)
    # inject safe API before package execution
    inject_sharkfin_api(context)
    try:
        runpy.run_module(pkg_name, run_name="__main__")
        send({"event":"exited", "status":"ok"})
        send({"event":"stdin_ready", "status":"ok"})
        stdin_ready = True
        return 0
    except SystemExit as se:
        send({"event":"exited", "status":"sysexit", "code": int(getattr(se, 'code', 0) or 0)})
        return int(getattr(se, 'code', 0) or 0)
    except Exception as e:
        send({"event":"crash", "error": str(e), "traceback": traceback.format_exc()})
        return 2

def run_mod_dir(mod_dir: str, chdir_into=True):
    p = Path(mod_dir).resolve()
    if not p.exists() or not p.is_dir():
        send({"event":"error", "message":"mod_dir_missing", "path": str(p)})
        return 3

    context = load_context_from_env()

    old_cwd = None
    if chdir_into:
        try:
            old_cwd = os.getcwd()
            os.chdir(str(p))
            send({"event":"chdir", "to": str(p)})
        except Exception as e:
            send({"event":"warning", "message":"chdir_failed", "error": str(e)})

    try:
        if is_package_dir(p):
            return run_package(p, context)
        else:
            entry = find_entry_file(p)
            if entry:
                return run_single_file(entry, context)
            else:
                send({"event":"error", "message":"no_entry_found", "path": str(p)})
                return 4
    finally:
        if old_cwd is not None:
            try:
                os.chdir(old_cwd)
                send({"event":"chdir_restore", "to": old_cwd})
            except Exception:
                pass

def main():
    if len(sys.argv) < 2:
        print("usage: --run-mod-child <mod_dir>", file=sys.stderr)
        sys.exit(2)
    mod_dir = sys.argv[1]
    exit_code = run_mod_dir(mod_dir, chdir_into=True)
    sys.exit(exit_code)

if __name__ == "__main__":
    Thread(target=listen, daemon=True).start()
    main()