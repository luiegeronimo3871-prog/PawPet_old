"""PawPet - connection check. Run:  py check_connection.py   (on the laptop/phone-side PC that cannot connect)

Tells you WHY the server cannot be reached: wrong network, firewall, or the server is not running."""
import socket
import sys
import urllib.request

DEFAULT_PORT = 5000


def main():
    addr = (sys.argv[1] if len(sys.argv) > 1 else input("Server laptop IP address (example 192.168.100.52): ")).strip()
    addr = addr.replace("http://", "").replace("https://", "").split("/")[0]
    host, _, port = addr.partition(":")
    port = int(port or DEFAULT_PORT)
    print("\nThis PC's addresses:", ", ".join(sorted({i[4][0] for i in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)})) or "?")
    print("Testing %s port %d ...\n" % (host, port))
    if host in ("localhost", "127.0.0.1"):
        print("NOTE: 'localhost' means THIS PC. On another laptop you must use the server laptop's IP address.\n")
    try:
        socket.create_connection((host, port), timeout=4).close()
    except ConnectionRefusedError:
        print("RESULT: the laptop answered but nothing is listening on port %d." % port)
        print("  -> The server is not running (start it with py app.py), or it uses another port.")
        return
    except socket.timeout:
        print("RESULT: no answer (timed out).")
        print("  1) Are both laptops on the SAME Wi-Fi? Their IPs must start with the same 3 numbers (192.168.100.x).")
        print("  2) On the SERVER laptop run open_firewall.bat as Administrator.")
        print("  3) Some Wi-Fi (school/guest) blocks device-to-device traffic: use a phone hotspot for both laptops.")
        print("  4) Is %s really the server laptop's address? Check the banner in the server window." % host)
        return
    except OSError as e:
        print("RESULT: cannot reach it (%s)." % e)
        print("  -> Wrong IP address, or this PC is not on the same network as the server laptop.")
        return
    try:
        body = urllib.request.urlopen("http://%s:%d/api/health" % (host, port), timeout=5).read(200).decode("utf-8", "replace")
        print("RESULT: OK - the PawPet server answered:", body.strip())
        print("  -> Use  http://%s:%d  as the Server address in the desktop app." % (host, port))
    except Exception as e:
        print("RESULT: the port is open but /api/health failed (%s). Is that really the PawPet server?" % e)


if __name__ == "__main__":
    main()
    input("\nPress Enter to close...")
