import sys, json, threading

class PERMISSIONS:
    READ_GAME_STATE = "read_game_state"
    MODIFY_GAME_STATE = "modify_game_state"
    ACCESS_USER_DATA = "access_user_data"
    LEGOPROXY_IPC = "use_legoproxy_ipc"
    
    def parse_permissions(perm_list):
        permissions = []
        for perm in perm_list:
            if perm == "read_game_state":
                permissions.append(PERMISSIONS.READ_GAME_STATE)
            elif perm == "modify_game_state":
                permissions.append(PERMISSIONS.MODIFY_GAME_STATE)
            elif perm == "access_user_data":
                permissions.append(PERMISSIONS.ACCESS_USER_DATA)
            elif perm == "use_legoproxy_ipc":
                permissions.append(PERMISSIONS.LEGOPROXY_IPC)
        return permissions

class fin:
    def __init__(self):
        self.buf = []
        self.command_events = {}
        self.send({"event":"started"})
        threading.Thread(target=self.listen, daemon=False).start()
        threading.Thread(target=self.run_loop, daemon=False).start()
    
    def log(self, message: str):
        self.send({"event": "log", "message": message})
        
    def invalid_json_receive(self, raw: str):
        self.send({"error":"invalid_json", "raw": raw})
        
    def crash(self, message: str):
        self.send({"error":"crash", "message": str(message)})
        
    def send(self, obj):
        sys.stdout.write(json.dumps(obj) + "\n")
        sys.stdout.flush()
        
    def send_and_await_response(self, obj, timeout=5.0):
        response_event = threading.Event()
        response_data = {}

        def response_listener(msg):
            self.send({ "event": "log", "message": "Acknowledgement event response received" })
            response_data.update(msg)
            response_event.set()

        # Register a one-time listener for the expected response
        self.event(obj.get("event", "") + "_response")(response_listener)

        self.send({ **obj, "requesting_ack": True })

        if response_event.wait(timeout):
            return response_data
        else:
            return None  # Timeout occurred
        
    def process_messages(self):
        msgs = self.buf.copy()
        self.buf.clear()
        for msg in msgs:
            if not isinstance(msg, dict):
                continue
            event = msg.get("event", "")
            
            if event == "ping":
                self.send({"event":"pong"})
            elif event == "init":
                self.send({"event":"inited", "mod_id": msg.get("payload", {}).get("mod_id")})
            elif event == "sharkfin_loaded":
                self.send({"event":"sharkfin_acknowledged"})
            elif event == "sharkfin_unloaded":
                self.send({"event":"sharkfin_goodbye"})
            elif event in self.command_events:
                for callback in self.command_events[event]:
                    try:
                        threading.Thread(target=callback, args=[msg]).start()
                    except Exception as e:
                        self.send({"error":"event_callback_error", "event": event, "message": str(e)})
        return msgs
    
    def event(self, command: str):
        def decorator(callback):
            if command not in self.command_events:
                self.command_events[command] = []
            self.command_events[command].append(callback)
            return callback
        return decorator
    
    def send_event(self, event_name: str, **kwargs):
        merged_kwargs = {"event": event_name}
        merged_kwargs.update(kwargs)
        self.send(merged_kwargs)
        
    def run_loop(self):
        while True:
            self.process_messages()

    def listen(self):
        while True:
            line = sys.stdin.readline()
            if not line:
                break
            try:
                msg = json.loads(line.strip())
                self.buf.append(msg)
            except Exception as e:
                self.invalid_json_receive(line.strip())
                
class shark:
    def __init__(self, fin_instance:fin):
        """
        This is a simpler class for mod developers to use to interact with Sharkfin.
        """
        self.fin = fin_instance
        
        self.__legoproxy = self._legoproxy(fin_instance, self)
        
    @property
    def legoproxy(self):
        return self.__legoproxy
        
    class _legoproxy:
        class _legoproxy_relay_request:
            def __init__(self, fin_instance:fin, shark_instance=None, info: dict = {}, id: str = None):
                self.fin = fin_instance
                self.shark = shark_instance
                self.info = info
                self.id = id

            def respond(self, body: str, status_code: int = 200, headers: dict = {}, cookies: dict = {}):
                response = {
                    "payload": {
                        "status_code": status_code,
                        "body": body if isinstance(body, str) else json.dumps(body) if isinstance(body, (dict, list)) else str(body),
                        "headers": headers
                    },
                    "id": self.id
                }
                self.fin.send_event("legoproxy_relay_request_response", **response)

        def __init__(self, fin_instance:fin, shark_instance=None):
            self.fin = fin_instance
            self.shark = shark_instance
        
        def send_ipc_message(self, message: str):
            response = self.fin.send_and_await_response({ "event": "legoproxy_ipc_message", "payload": { "message": message } }, timeout=5.0)
            return response.get("payload", None) if response else None
        
        def on_access_route(self, route: str):
            def decorator(callback):
                def handle_access_route(msg):
                    route_info = msg.get("payload", {})
                    id = msg.get("id", None)
                    if route_info.get("route") == route:
                        request = self._legoproxy_relay_request(self.fin, self.shark, route_info, id)
                        callback(request)
                
                self.fin.event("legoproxy_relay_request")(handle_access_route)

            return decorator
        
        def on_access_any_route(self):
            def decorator(callback):
                def handle_access_route(msg):
                    route_info = msg.get("payload", {})
                    id = msg.get("id", None)
                    request = self._legoproxy_relay_request(self.fin, self.shark, route_info, id)
                    callback(request)
                
                self.fin.event("legoproxy_relay_request")(handle_access_route)

            return decorator
        
    @property
    def PERMISSIONS(self):
        ack = self.fin.send_and_await_response({ "event": "get_mod_permissions" }, timeout=5.0)
        if not ack:
            return []
        return PERMISSIONS.parse_permissions(ack.get("payload", []))
    
    @property
    def has_permission_read_game_state(self) -> bool:
        return PERMISSIONS.READ_GAME_STATE in self.PERMISSIONS
    
    @property
    def has_permission_modify_game_state(self) -> bool:
        return PERMISSIONS.MODIFY_GAME_STATE in self.PERMISSIONS
    
    @property
    def has_permission_access_user_data(self) -> bool:
        return PERMISSIONS.ACCESS_USER_DATA in self.PERMISSIONS
    
    @property
    def has_permission_legoproxy_ipc(self) -> bool:
        return PERMISSIONS.LEGOPROXY_IPC in self.PERMISSIONS

    def log(self, message: str):
        self.fin.log(message)
        
    def read_game_state(self):
        if not self.has_permission_read_game_state:
            self.fin.crash("Mod does not have permission to read game state.")
            return None
        response = self.fin.send_and_await_response({ "event": "read_game_state" }, timeout=5.0)
        return response.get("payload", None) if response else None