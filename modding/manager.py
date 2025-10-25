from importlib import import_module

from flask import app

from .classes import Mod
from .events import Events

from quart import Quart, request, Response

import os, time, sys, json, subprocess, threading, getpass, uuid, asyncio, uvicorn

try:
    import win32process, win32job, win32con, win32event, win32api
except Exception:
    win32process, win32job = None
    
class LegoProxyHTTPServer(Quart):
    def __init__(self, mod: Mod):
        self.id = str(uuid.uuid4())
        super().__init__("legoproxy_server_" + self.id.replace("-", "_"))
        self.mod = mod
        self._bindings = {}
        self._firewall_rules = {}
        self.address = []
        # setup routes and handlers here
        
        self.add_url_rule('/', 'index', self.index)
        self.add_url_rule('/<path:path>', 'path', self.path)
        self.add_url_rule('/favicon.ico', 'favicon', self.decline)
        
    def send_firewall(self, rules: dict):
        self._firewall_rules = rules
        return True
        
    def send_bindings(self, bindings: dict):
        self._bindings = bindings
        return True
    
    async def decline(self):
        return "", 204
    
    async def index(self):
        id = str(uuid.uuid4())
        obj = {
            "event": "legoproxy_relay_request",
            "id": id,
            "payload": {
                "route": request.path,
                "method": request.method,
                "body": await request.get_data(as_text=True) if request.method == "POST" else None,
                "headers": dict(request.headers),
                "cookies": request.cookies.to_dict(),
                "source": {"ip": request.remote_addr}
            }
        }
        
        response_event = asyncio.Event()
        response_data = {}

        def response_listener(mod: Mod, event: str, **msg):
            if msg.get("id", "") != id:
                return  # not the response we're waiting for
            if mod.job_name != self.mod.job_name:
                return  # not the mod we're waiting for
            response_data.update(msg)
            response_event.set()

        self.mod.send({ **obj, "requesting_ack": True })

        # Register a one-time listener for the expected response
        self.mod.event(obj.get("event", "") + "_response")(response_listener)

        try:
            if await asyncio.wait_for(response_event.wait(), timeout=20.0): # wait for the mod to respond
                pl = response_data.get("payload", {})
                resp = Response(pl.get("body", ""), status=pl.get("status_code", 200), headers=pl.get("headers", {}))
                return resp
            else:
                return {"error": "An unknown error occurred"}, 502  # Unexpected error occurred
        except asyncio.TimeoutError:
            return {"error": "Timeout occurred"}, 502  # Timeout occurred
        
    async def path(self, path):
        return await self.index()
        
    def _serve(self):
        uvicorn.run(self, host=self.address[0], port=self.address[1], reload=False)
        
    def run_quart(self, **kwargs):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._serve()
        #self.run(loop=loop, **kwargs)
        
    def start(self):
        threading.Thread(target=self.run_quart, kwargs={
            'host': self.address[0] or '0.0.0.0',
            'port': self.address[1] or 8080
        }, daemon=True).start()
        return True

class Manager:
    def __init__(self):
        self.mods_dir = ""
        self.main_file = ""
        
        self.frozen_config = f"C:\\Users\\{getpass.getuser()}\\AppData\\Local\\sharkfin"
        
        if self.is_frozen():
            self.mods_dir = os.path.join(self.frozen_config, "mods")
        else:
            self.mods_dir = self.resource("mods")
        
        self.mods: list[Mod] = self.search_mods(self.mods_dir)
        self.mod_event_handlers = {}
        
        self.game_state: list = [{}, {}, {}]
        
        self.evs = Events(self)
        
    def resource(self, path: str):
        return os.path.abspath(os.path.join(os.path.dirname(__file__), path))
    
    def is_frozen(self):
        """Check if the script is running in a frozen environment (like PyInstaller)."""
        return getattr(sys, 'frozen', False)
        
    def search_mods(self, mods_directory="mods") -> list[Mod]:
        """Search for mods in the specified directory and return a list of Mod instances."""
        found_mods = []
        if not os.path.isdir(mods_directory):
            print(f"Mods directory '{mods_directory}' does not exist.")
            return found_mods
        
        for folder_name in os.listdir(mods_directory):
            mod_path = os.path.join(mods_directory, folder_name)
            if os.path.isdir(mod_path):
                manifest_path = os.path.join(mod_path, "manifest.json")
                if os.path.isfile(manifest_path):
                    with open(manifest_path, "r") as f:
                        manifest = json.load(f)
                        mod = Mod(
                            folder_name=folder_name,
                            name=manifest.get("name", folder_name),
                            description=manifest.get("description", ""),
                            author=manifest.get("author", ""),
                            version=manifest.get("version", "0.1"),
                            entrypoint=manifest.get("entrypoint", "main"),
                            job_name=str(uuid.uuid4())
                        )
                        found_mods.append(mod)
        return found_mods

    def load_mod(self, mod: Mod):
        """try:
            modLoaded = mod.loaded
            if hasattr(modLoaded, "Mod") and type(modLoaded.Mod) == type(self):
                mod_instance = modLoaded.Mod()
                self.mods.append(mod_instance)
                print(f"Loaded mod: {mod.name}")
            else:
                print(f"Mod {mod.name} does not have a Mod class.")
        except Exception as e:
            print(f"Failed to load mod {mod.name}: {e}")"""
        pass
            
    def set_mod_handler(self, events: list[str]) -> bool | None:
        # check for conflicts in events
        for handler in self.mod_event_handlers:
            for event in events:
                k = self.mod_event_handlers[handler]
                if event in k['events']:
                    return None
        
        def callback(modHandler):
            self.mod_event_handlers[str(uuid.uuid4())] = {
                "handler": modHandler,
                "events": events
            }
            return True
        
        return callback
    
    def create_mod_assets(self, mod: Mod):
        """
        
        create the assets for the mod (aka, legoproxy web server, websockets, etc.)
        it grabs required permissions from the mod manifest and sets up accordingly.
        """
        cfg = mod.mod_config
        if not cfg:
            mod.log_info("error", "The mod did not have a valid manifest.")
            mod.shutdown_mod() # shutdown, there was an error
            return
        permissions = cfg.get("permissions", [])

        if "use_legoproxy_ipc" in permissions:
            legoproxy_bindings = cfg.get("legoproxy_bindings")
            if not legoproxy_bindings:
                mod.log_info("error", "The mod does not have the required legoproxy_bindings for the LegoProxy server.")
                mod.shutdown_mod()
                return
            if not isinstance(legoproxy_bindings, list):
                mod.log_info("error", "The mod's legoproxy_bindings must be a list of binding objects.")
                mod.shutdown_mod()
                return
            for binding in legoproxy_bindings:
                if not isinstance(binding, dict) or "address" not in binding or len(binding["address"]) != 2:
                    mod.log_info("error", "Each legoproxy_binding must be an object with 'address' (host, port) keys.")
                    mod.shutdown_mod()
                    return
                if not isinstance(binding["address"][1], int):
                    mod.log_info("error", "The port in legoproxy_binding must be an integer.")
                    mod.shutdown_mod()
                    return
                if not isinstance(binding["address"][0], str):
                    mod.log_info("error", "The host in legoproxy_binding must be a string.")
                    mod.shutdown_mod()
                    return
                mod.log_info("info", f"Setting up LegoProxy binding at {binding['address'][0]}:{binding['address'][1]}")
                if "type" not in binding or binding["type"] not in ["http"]:
                    mod.log_info("error", "Type attribute must be one of: 'http'.")
                    mod.shutdown_mod()
                    return
                if binding["type"] == "http":
                    mod.log_info("info", "Setting up LegoProxy HTTP server for mod.")
                    server = LegoProxyHTTPServer(mod)
                    server.address = binding["address"]
                    server.send_firewall(binding.get("firewall", {}))
                    mod.assets.append(server)
                    server.start()
                    mod.log_info("info", "LegoProxy HTTP server started.")

    def start_mod_process(self, mod: Mod, cmdline=None, run_as_user=None):
        """
        start a mod process.
        - cmdline: list or str command to run; if None, runs the bundled mod script with current python
        - run_as_user: tuple (username, domain, password) to use CreateProcessWithLogonW via pywin32
        returns: subprocess.Popen-like object (or None on error)
        """
        if cmdline is None:
            if self.is_frozen():
                cmdline = [sys.executable, "--run-mod-child", mod.mod_path]
            else:
                cmdline = [sys.executable, self.main_file, "--run-mod-child", mod.mod_path]
                           #+ os.sep + (mod.entrypoint + ".py" if not mod.entrypoint.endswith(".py") else mod.entrypoint)]
        
        print("cmdline:",cmdline)
        
        self.create_mod_assets(mod) # setup assets for the mod

        if run_as_user and win32process:
            username, domain, password = run_as_user
            # CreateProcessWithLogonW: (user, domain, password, logonFlags, appName, commandLine, creationFlags, env, cwd, startupInfo)
            try:
                si = win32process.STARTUPINFO()
                cmdline_str = cmdline if isinstance(cmdline, str) else " ".join('"{}"'.format(p) for p in cmdline)
                # LOGON_WITH_PROFILE to give a sane environment; you can also use 0 for minimal profile
                proc_info = win32process.CreateProcessWithLogonW(
                    username,
                    domain,
                    password,
                    win32con.LOGON_WITH_PROFILE,
                    None,
                    cmdline_str,
                    win32con.CREATE_NEW_CONSOLE,
                    None,
                    None,
                    si
                )
                # proc_info = (hProcess, hThread, dwProcessId, dwThreadId) depending on pywin32 version
                hProcess = proc_info[0]
                print({"pid": win32process.GetProcessId(hProcess), "handle": hProcess, "info": proc_info})
                # wrap minimal object with pid and handle so we can assign to job object
                return {"pid": win32process.GetProcessId(hProcess), "handle": hProcess, "info": proc_info}
            except Exception as e:
                print("failed to CreateProcessWithLogonW:", e)
                return None

        # fallback: use subprocess.Popen in same user
        proc = subprocess.Popen(cmdline, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return proc
    
    def assign_to_job(self, mod: Mod, process_obj, job):
        """
        assign a process to the job object.
        - process_obj can be a subprocess.Popen or the dict returned when using CreateProcessWithLogonW.
        - job should be created by win32job.CreateJobObject
        """
        if not win32job:
            return False

        try:
            if isinstance(process_obj, dict):  # returned from CreateProcessWithLogonW
                hProcess = process_obj["handle"]
                win32job.AssignProcessToJobObject(job, hProcess)
                return True
            else:
                # subprocess.Popen on windows has _handle attribute (internal)
                h = getattr(process_obj, "_handle", None)
                if h:
                    win32job.AssignProcessToJobObject(job, h)
                    return True
        except Exception as e:
            print("assign_to_job error:", e)
        return False

    def read_stdout_loop(self, proc, mod_job_name: str, label="mod"):
        if isinstance(proc, dict):
            # no stdout handle because we used CreateProcessWithLogonW in this example
            return
        for line in proc.stdout:
            rline = line.rstrip()
            print(f"[{label} stdout] {line.rstrip()}")
            
            for m in self.mods:
                if m.job_name == mod_job_name:
                    m.log_info("stdout", rline)
                    break
            
            try:
                msg: dict = json.loads(rline)
                print(f"Received message: {msg}")  # Debugging incoming message
                # handle incoming messages here
                
                handled = False
                
                for m in self.mods:
                    if m.job_name == mod_job_name:
                        if msg.get("event") in m.mod_event_handlers:
                            handlers = m.mod_event_handlers[msg.get("event")]
                            ev = msg.pop('event')
                            for i in handlers:
                                i(m, ev, **msg)
                            handled = True
                            break
                
                if handled:
                    continue
                
                if msg.get("requesting_ack") == True:
                    print("Acknowledgment requested")  # Debugging acknowledgment request
                    # example: send back an ack
                    def default_sendb(**kwargs):
                        # search for appropriate mod event handler
                        handler = None
                        for m in self.mod_event_handlers:
                            k = self.mod_event_handlers[m]
                            if msg.get("event") in k['events']:
                                handler = k['handler']
                                break
                        if handler:
                            print(f"Handler found: {handler} for event: {msg.get('event')}")  # Debugging handler
                        mod = None
                        for m in self.mods:
                            if m.job_name == mod_job_name:
                                mod = m
                                break
                        print(f"Mod found: {mod}")  # Debugging mod
                        if mod and not handler:
                            # try a different method
                            for m in mod.mod_event_handlers:
                                k = mod.mod_event_handlers[m]
                                if msg.get("event") in k['events']:
                                    handler = k['handler']
                                    break
                        if handler:
                            print(f"Handler found: {handler} for event: {msg.get('event')}")  # Debugging handler
                        if handler and mod:
                            try:
                                resp = handler(mod, msg.get("event"), **kwargs)
                                print(f"Handler response: {resp}")  # Debugging handler response
                                response_obj = {"event":f"{msg.get('event')}_response", "original": msg, "payload": resp, "id": msg.get("id", "")}
                                print(f"Sending response: {response_obj}")
                                mod.send(response_obj)
                            except Exception as e:
                                print(f"Error while executing handler: {e}")
                        else:
                            print(f"Cannot send - handler: {handler}, mod: {mod}")
                    msged = msg.copy()
                    msged.pop('event', None)
                    print(f"Message without event: {msged}")  # Debugging message payload
                    default_sendb(**msged)
                else:
                    def default_sendb(**kwargs):
                        # search for appropriate mod event handler
                        handler = None
                        for m in self.mod_event_handlers:
                            k = self.mod_event_handlers[m]
                            if msg.get("event") in k['events']:
                                handler = k['handler']
                                break
                        mod = None
                        for m in self.mods:
                            if m.job_name == mod_job_name:
                                mod = m
                                break
                        if handler and mod:
                            resp = handler(mod, msg.get("event"), **kwargs)
                            mod.send(resp)
                        else:
                            return None
                    msged = msg.copy()
                    msged.pop('event')
                    print(msged)
                    default_sendb(**msged)
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e} for line: {rline}")  # Debugging JSON errors
            except Exception as e:
                print(f"Error in acknowledgment handling: {e}")  # General error debugging
                
    def read_stderr_loop(self, proc, mod_job_name: str, label="mod"):
        if isinstance(proc, dict):
            # no stderr handle because we used CreateProcessWithLogonW in this example
            return
        for line in proc.stderr:
            rline = line.rstrip()
            print(f"[{label} stderr] {line.rstrip()}")
            for m in self.mods:
                if m.job_name == mod_job_name:
                    m.log_info("stderr", rline)
                    break
            
    def send_rpc(self, mod: Mod, obj):
        try:
            mod.proc.stdin.write(json.dumps(obj) + "\n")
            mod.proc.stdin.flush()
        except Exception as e:
            print("send failed:", e)
            
    def send_rpc_with_proc(self, proc: subprocess.Popen, obj):
        try:
            proc.stdin.write(json.dumps(obj) + "\n")
            proc.stdin.flush()
        except Exception as e:
            print("send failed:", e)

    def start_and_manage_mod(self, mod: Mod, run_as_user=None):
        job = mod.create_mod_job_object()
        proc = self.start_mod_process(mod, run_as_user=run_as_user)
        if not proc:
            print("failed to start mod process")
            return

        # assign to job if possible
        if job:
            ok = self.assign_to_job(mod, proc, job)
            print("assigned to job:", ok)

        # start reader threads if using subprocess.Popen
        if not isinstance(proc, dict):
            for mod in self.mods:
                if mod.job_name == mod.job_name:
                    mod.proc = proc
            
            t1 = threading.Thread(target=self.read_stdout_loop, args=(proc,mod.job_name), daemon=False)
            t2 = threading.Thread(target=self.read_stderr_loop, args=(proc,mod.job_name), daemon=False)
            t1.start()
            t2.start()

            mod.send({"event":"init", "payload":{"mod_id":mod.job_name}})
            time.sleep(2)
            mod.send({"event":"do_work"})

        else:
            # if launched via CreateProcessWithLogonW we didn't wire stdin/stdout here; you'd need to open pipes via pywin32
            print("started mod via CreateProcessWithLogonW: pid=", proc["pid"])
            # if you created a job, processes will be terminated when job handle is closed (or manager exits).
            # to gracefully stop, you can use other IPC mechanisms (named pipes, tcp, etc.) — see docs.

        # cleanup: close the job handle so windows kills children when process exits (optionally do this on shutdown)
        if job:
            try:
                win32api.CloseHandle(job)
            except Exception:
                pass
            
    def shutdown_mod(self, mod: Mod):
        """
        Shutdown a mod process gracefully.
        """
        self.send_rpc(mod, {"event":"shutdown"})
        # give it a moment then terminate if needed
        try:
            mod.proc.wait(timeout=3)
        except Exception:
            mod.proc.terminate()
            mod.proc.wait(timeout=2)