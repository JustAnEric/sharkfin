from .classes import Mod

import json, os

class Events:
    def __init__(self, manager):
        self.manager = manager
        # permissions
        
        self.manager.set_mod_handler(['get_mod_permissions'])(self.mod_permissions_get)
        self.manager.set_mod_handler(['read_game_state'])(self.mod_read_game_state)
        
    def mod_permissions_get(self, mod: Mod, event: str, **kw):
        if event == "get_mod_permissions":
            l = self.get_mod_config(mod)
            if len(l.items()) > 0:
                return l.get('permissions', [])
            else:
                mod.log_info("error", "The mod did not have a valid manifest.")
                mod.shutdown_mod() # shutdown, there was an error
                return None
        else:
            return None
        
    def mod_read_game_state(self, mod: Mod, event: str, **kw):
        if event == "read_game_state":
            l = self.manager.game_state
            m = self.get_mod_config(mod)
            if len(m.items()) > 0 and 'permissions' in m and 'read_game_state' in m['permissions']:
                return l
            else:
                mod.log_info("error", "The mod did not have a valid manifest.")
                mod.shutdown_mod() # shutdown, there was an error
                return None
            
    def get_mod_config(self, mod: Mod):
        l: dict = {}
        try:
            with open(os.path.join(mod.mod_path, "manifest.json"), "r") as f:
                l = json.load(f)
        except:
            l: dict = {}
        return l