"""Thin HTTP client the desktop admin uses to talk to the PawPet server."""
import requests

CONNECT_TIMEOUT = 3     # seconds to reach the server
READ_TIMEOUT = 8        # seconds to wait for its answer


class ApiError(Exception):
    def __init__(self, message, status=0, must_change=False):
        super().__init__(message)
        self.status = status
        self.must_change = must_change


class Api:
    def __init__(self, base="http://localhost:5000"):
        self.base = base.rstrip("/")
        self.token = ""
        self.user = None

    def _call(self, method, path, body=None, params=None, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT)):
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        try:
            r = requests.request(method, self.base + "/api" + path, json=body, params=params,
                                 headers=headers, timeout=timeout)
        except requests.exceptions.ReadTimeout:
            raise ApiError("The server is taking too long to answer. Check the Wi-Fi/network and try again.")
        except requests.exceptions.InvalidURL:
            raise ApiError("The server address is not valid. It should look like http://192.168.1.10:5000")
        except requests.exceptions.RequestException:
            hint = ""
            if "localhost" in self.base or "127.0.0.1" in self.base:
                hint = " 'localhost' means THIS computer - on another laptop type the server laptop's IP address instead."
            raise ApiError("Cannot reach the server at %s. Check that it is running, that both devices are on the same "
                           "Wi-Fi, and that the address is right.%s" % (self.base, hint))
        try:
            data = r.json()
        except ValueError:
            data = {}
        if not isinstance(data, (dict, list)):
            data = {}
        if r.status_code >= 400:
            msg = data.get("error") if isinstance(data, dict) else None
            if r.status_code == 401 and self.token and path != "/login":
                msg = "Your session expired. Please sign in again."
            raise ApiError(msg or "Server error (%d). Please try again." % r.status_code, r.status_code,
                           bool(isinstance(data, dict) and data.get("must_change")))
        return data

    def get(self, path, **params):
        return self._call("GET", path, params={k: v for k, v in params.items() if v not in (None, "")})

    def post(self, path, body=None):
        return self._call("POST", path, body or {})

    def put(self, path, body):
        return self._call("PUT", path, body)

    def delete(self, path):
        return self._call("DELETE", path)

    def health(self):
        """Quick 'is the server there?' check (1.5 s at most) used before every automatic refresh."""
        try:
            requests.get(self.base + "/api/health", timeout=1.5)
            return True
        except requests.exceptions.RequestException:
            return False

    def login(self, username, password):
        r = self._call("POST", "/login", {"username": username, "password": password, "portal": "admin"})
        self.token, self.user = r["token"], r["user"]
        return self.user

    def change_password(self, old, new):
        return self._call("POST", "/change-password", {"old_password": old, "new_password": new})

    def logout(self):
        try:
            self._call("POST", "/logout", timeout=(2, 3))
        except ApiError:
            pass
        self.token, self.user = "", None
