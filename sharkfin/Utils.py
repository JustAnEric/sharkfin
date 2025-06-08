from winreg import CreateKey, SetValue, SetValueEx, CloseKey, HKEY_CURRENT_USER, REG_SZ
from subprocess import check_output
from threading import Timer
from re import split
from os import environ, path, scandir
from tempfile import gettempdir
from sys import platform

def debounce(time):
    def decorator(fn):
        timer = None
        def debounced(*args, **kwargs):
            nonlocal timer
            if timer is not None:
                timer.cancel()
            timer = Timer(time, lambda: fn(*args, **kwargs))
            timer.start()
        return debounced
    return decorator

def get_gpu_list():
    try:
        output = check_output("wmic path win32_VideoController get Name,DriverVersion", shell=True)
        decoded_output = output.decode().strip().splitlines()
        
        gpu_names = []
        for line in decoded_output[1:]:
            if line.strip():
                parts = split(r'\s{2,}', line.strip())
                if parts:
                    gpu_names.append(parts[1])
        return gpu_names
    except Exception as e:
        return f"Error retrieving GPU driver info on Windows: {e}"

def set_protocol(protocol, application_path, program_name):
    try:
        base_path = fr"Software\Classes\{protocol}"
        key = CreateKey(HKEY_CURRENT_USER, base_path)
        SetValue(key, None, REG_SZ, f"{program_name} Protocol")
        SetValueEx(key, "URL Protocol", 0, REG_SZ, "")
        SetValueEx(key, "FriendlyName", 0, REG_SZ, program_name)

        icon_key = CreateKey(key, "DefaultIcon")
        SetValue(icon_key, None, REG_SZ, application_path)
        CloseKey(icon_key)

        command_key = CreateKey(key, r"shell\open\command")
        command = f'{application_path} "%1"'
        SetValue(command_key, None, REG_SZ, command)
        CloseKey(command_key)

        CloseKey(key)
        print(f"Successfully registered protocol: {protocol} with name: {program_name}")
    except Exception as e:
        print(f"Failed to register protocol {protocol}: {e}")

def get_discord_ipc_path(pipe=None):
    ipc = 'discord-ipc-'
    if pipe:
        ipc = f"{ipc}{pipe}"

    if platform in ('linux', 'darwin'):
        tempdir = (environ.get('XDG_RUNTIME_DIR') or gettempdir())
        paths = ['.', 'snap.discord', 'app/com.discordapp.Discord', 'app/com.discordapp.DiscordCanary']
    elif platform == 'win32':
        tempdir = r'\\?\pipe'
        paths = ['.']
    else:
        return
    
    for p in paths:
        full_path = path.abspath(path.join(tempdir, p))
        if platform == 'win32' or path.isdir(full_path):
            for entry in scandir(full_path):
                if entry.name.startswith(ipc) and path.exists(entry):
                    return entry.path