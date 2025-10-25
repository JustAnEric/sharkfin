import sys
import json
import time
import socket
import threading

from SharkfinModAPI import fin, shark

HOST = '127.0.0.1'
PORT = 5000

def handle_client(conn, addr):
    print(f"New connection from {addr}")
    with conn:
        buffer = b""
        while True:
            try:
                data = conn.recv(1024)
                if not data:
                    break

                buffer += data
                # You can define a delimiter (e.g. newline) for JSON messages
                while b"\n" in buffer:
                    message, buffer = buffer.split(b"\n", 1)
                    try:
                        obj = json.loads(message.decode('utf-8'))
                        print(f"Received from {addr}: {obj}")

                        if obj.get('get_game_state'):
                            response = {
                                "status": "ok",
                                "state": shark.read_game_state()[0]
                            }
                            conn.sendall((json.dumps(response) + "\n").encode('utf-8'))
                        elif obj.get('get_user_state'):
                            response = {
                                "status": "ok",
                                "state": shark.read_game_state()[1]
                            }
                            conn.sendall((json.dumps(response) + "\n").encode('utf-8'))
                        elif obj.get('get_server_state'):
                            response = {
                                "status": "ok",
                                "state": shark.read_game_state()[2]
                            }
                            conn.sendall((json.dumps(response) + "\n").encode('utf-8'))

                    except json.JSONDecodeError:
                        print(f"Invalid JSON from {addr}: {message}")

            except ConnectionResetError:
                print(f"Connection lost: {addr}")
                break

    print(f"Connection closed: {addr}")


def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind((HOST, PORT))
        server.listen()
        print(f"Server listening on {HOST}:{PORT}")

        while True:
            conn, addr = server.accept()
            thread = threading.Thread(target=handle_client, args=(conn, addr))
            thread.start()

@fin.event('do_work')
def handle_do_work(msg):
    fin.send_event("work_started")
    # pretend doing stuff safely
    time.sleep(0.2)
    fin.send_event("work_done", timestamp=time.time())
    response = fin.send_and_await_response({ "event": "get_mod_permissions" }, timeout=5.0)
    if response:
        fin.send_event("mod_permissions", **response)
    else:
        fin.send_event("mod_permissions_error")
    
    #main()
    
if hasattr(shark, 'legoproxy'):
    @shark.legoproxy.on_access_any_route()
    def handle_legoproxy_relay_request(request: shark._legoproxy._legoproxy_relay_request):
        request.respond({"error":"Access to LegoProxy routes is not allowed by default."}, 403)