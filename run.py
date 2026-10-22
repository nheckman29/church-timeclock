"""Start the time clock for everyday use.

    python run.py

Serves on the local network with waitress. Flask's own dev server is not used here
because it is single-threaded and explicity not meant for real use.
"""

import os
import socket

from waitress import serve

import db
from app import app


def lan_address():
    """Best-effort LAN IP, so the tablet URL can be printed at startup."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8080"))

    conn = db.connect(app.config["DB_PATH"])
    new_pin = db.init_db(conn)
    conn.close()

    if new_pin:
        print("\n" + "=" * 52)
        print(f" First run. Your office administrator PIN is: {new_pin}")
        print(" Write it down and then change it under Settings.")
        print("=" * 52, flush=True)

    print (f"\nTime clock running. On this machine: http://localhost:{port}")
    print(f"From the tablet or another computer: http://{lan_address()}:{port}")
    print("Press Ctrl+C to stop.\n", flush=True)

    serve(app, host=host, port=port)