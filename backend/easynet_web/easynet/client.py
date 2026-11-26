import asyncio
from collections.abc import Mapping

import httpx

DEFAULT_CGI_PATH = "/recepcion_datos_4.cgi"


class EasyNetError(RuntimeError):
    def __init__(self, message: str, *, raw: str | None = None, retryable: bool = False):
        super().__init__(message)
        self.raw = raw
        self.retryable = retryable


class EasyNetClient:
    """Small client for the non-concurrent HTTP protocol exposed by easyNet."""

    def __init__(
        self,
        host: str,
        username: str = "",
        password: str = "",
        *,
        verify_tls: bool = False,
        timeout_seconds: float = 10.0,
        cgi_path: str = DEFAULT_CGI_PATH,
    ) -> None:
        self.host = host.rstrip("/")
        self.cgi_url = f"{self.host}{cgi_path}"
        self._lock = asyncio.Lock()
        self._http = httpx.AsyncClient(
            auth=(username, password) if username or password else None,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=timeout_seconds,
            verify=verify_tls,
            follow_redirects=False,
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def set_host(self, host: str) -> None:
        normalized = host.rstrip("/")
        async with self._lock:
            self.host = normalized
            self.cgi_url = f"{normalized}{DEFAULT_CGI_PATH}"

    async def read_block(self, operation: int) -> list[str]:
        self._validate_operation(operation)
        for attempt in range(3):
            raw = await self._serialized_post(f"idOperacion={operation}")
            try:
                return self._parse_block(raw, operation)
            except EasyNetError as exc:
                if not exc.retryable or attempt == 2:
                    raise
                await asyncio.sleep(attempt + 1)
        raise EasyNetError(f"Easynet operation {operation} failed")

    async def read_serial(self) -> str:
        """Read the legacy 1900 response, which does not use the normal block header."""
        raw = await self._serialized_post("idOperacion=1900")
        lines = self._lines(raw)
        if len(lines) < 3 or not lines[0].isdigit():
            raise EasyNetError("Invalid Easynet serial response", raw=raw)
        return lines[0]

    async def read_registers(self, address: int, count: int) -> dict[int, str]:
        self._validate_address_range(address, count)
        body = f"idOperacion=2002&dir={address}&num={count}"
        values = await self._read_address_range(body, 2002, address, count)
        return dict(zip(range(address, address + count), values, strict=True))

    async def read_coils(self, address: int, count: int) -> dict[int, str]:
        self._validate_address_range(address, count)
        body = f"idOperacion=2001&dir={address}&num={count}"
        values = await self._read_address_range(body, 2001, address, count)
        return dict(zip(range(address, address + count), values, strict=True))

    async def write_coil(self, address: int, value: bool) -> None:
        self._validate_address_range(address, 1)
        body = f"idOperacion=2011&dir={address}&num=1&{int(value)}"
        await self._write_address(body, 2011)

    async def write_register(self, address: int, value: int) -> None:
        self._validate_address_range(address, 1)
        if not isinstance(value, int) or not -32768 <= value <= 32767:
            raise ValueError("Invalid Easynet register value")
        encoded = value & 0xFFFF
        body = f"idOperacion=2012&dir={address}&num=1&{encoded:04x}"
        await self._write_address(body, 2012)

    async def fetch_history(self, url_path: str) -> str:
        return await self._serialized_get(url_path)

    async def _serialized_post(self, body: str) -> str:
        async with self._lock:
            for attempt in range(3):
                try:
                    response = await self._http.post(self.cgi_url, content=body)
                    return self._check_response(response)
                except EasyNetError as exc:
                    if not exc.retryable or attempt == 2:
                        raise
                    await asyncio.sleep(attempt + 1)
                except httpx.TimeoutException as exc:
                    if attempt == 2:
                        raise EasyNetError("Easynet request timed out", retryable=True) from exc
                    await asyncio.sleep(attempt + 1)
                except httpx.RequestError as exc:
                    if attempt == 2:
                        raise EasyNetError("Easynet connection failed", retryable=True) from exc
                    await asyncio.sleep(attempt + 1)
            raise EasyNetError("Easynet request failed")

    async def _serialized_get(self, url_path: str) -> str:
        async with self._lock:
            if not url_path.startswith("/historic/"):
                raise EasyNetError("Invalid historic path")
            for attempt in range(3):
                try:
                    response = await self._http.get(f"{self.host}{url_path}")
                    return self._check_response(response)
                except EasyNetError as exc:
                    if not exc.retryable or attempt == 2:
                        raise
                    await asyncio.sleep(attempt + 1)
                except httpx.TimeoutException as exc:
                    if attempt == 2:
                        raise EasyNetError(
                            "Easynet history request timed out", retryable=True
                        ) from exc
                    await asyncio.sleep(attempt + 1)
                except httpx.RequestError as exc:
                    if attempt == 2:
                        raise EasyNetError(
                            "Easynet history connection failed", retryable=True
                        ) from exc
                    await asyncio.sleep(attempt + 1)
            raise EasyNetError("Easynet history request failed")

    async def _read_address_range(
        self, body: str, operation: int, address: int, count: int
    ) -> list[str]:
        for attempt in range(3):
            raw = await self._serialized_post(body)
            try:
                return self._parse_address_response(raw, operation, address, count)
            except EasyNetError as exc:
                if not exc.retryable or attempt == 2:
                    raise
                await asyncio.sleep(attempt + 1)
        raise EasyNetError("Easynet address read failed")

    async def _write_address(self, body: str, operation: int) -> None:
        for attempt in range(3):
            raw = await self._serialized_post(body)
            try:
                self._parse_write_response(raw, operation)
                return
            except EasyNetError as exc:
                if not exc.retryable or attempt == 2:
                    raise
                await asyncio.sleep(attempt + 1)
        raise EasyNetError("Easynet address write failed")

    @staticmethod
    def _check_response(response: httpx.Response) -> str:
        if response.status_code == 401:
            raise EasyNetError("Easynet authentication failed")
        if response.status_code == 404:
            raise EasyNetError("Easynet history file not found")
        if not 200 <= response.status_code < 300:
            raise EasyNetError(
                f"Easynet returned HTTP {response.status_code}",
                retryable=response.status_code >= 500,
            )
        return response.text

    @staticmethod
    def _parse_block(raw: str, operation: int) -> list[str]:
        lines = EasyNetClient._lines(raw)
        header = EasyNetClient._header(lines)
        legacy_names = {1079: "get_alarmas"}
        if header[0] != str(operation) and header[0] != legacy_names.get(operation):
            raise EasyNetError("Unexpected Easynet response operation", raw=raw)
        if header[1] != "0":
            raise EasyNetError(
                f"Easynet operation {operation} failed",
                raw=raw,
                retryable=header[1] == "-7",
            )
        if len(lines) < 3 or lines[-1] != "0":
            raise EasyNetError(f"Incomplete Easynet operation {operation}", raw=raw)
        return lines[1:-1]

    @staticmethod
    def _parse_address_response(
        raw: str, operation: int, address: int, count: int
    ) -> list[str]:
        lines = EasyNetClient._lines(raw)
        header = EasyNetClient._header(lines)
        legacy_names = {2001: "geo_get_bit", 2002: "geo_get_reg"}
        if header[0] != str(operation) and header[0] != legacy_names.get(operation):
            raise EasyNetError("Unexpected Easynet response operation", raw=raw)
        if header[1] != "0":
            raise EasyNetError(
                "Easynet register read failed",
                raw=raw,
                retryable=header[1] == "-7",
            )
        if len(lines) != 3 or lines[-1] != "0":
            raise EasyNetError("Incomplete Easynet register response", raw=raw)
        metadata = lines[1].split("&")
        if len(metadata) < 3 or metadata[0] != f"dir={address}" or metadata[1] != f"num={count}":
            raise EasyNetError("Easynet returned another address range", raw=raw)
        values = metadata[2:]
        if len(values) != count or any(" error" in value for value in values):
            raise EasyNetError("Incomplete Easynet register range", raw=raw)
        return values

    @staticmethod
    def _parse_write_response(raw: str, operation: int) -> None:
        lines = EasyNetClient._lines(raw)
        header = EasyNetClient._header(lines)
        if header[0] != str(operation):
            raise EasyNetError("Unexpected Easynet write response", raw=raw)
        if header[1] != "0":
            raise EasyNetError(
                f"Easynet write operation {operation} failed",
                raw=raw,
                retryable=header[1] == "-7",
            )
        if len(lines) != 2 or lines[-1] != "0":
            raise EasyNetError("Incomplete Easynet write response", raw=raw)

    @staticmethod
    def _header(lines: list[str]) -> tuple[str, str]:
        if not lines or not lines[0].startswith("error_") or "=" not in lines[0]:
            raise EasyNetError("Invalid Easynet response header")
        name, code = lines[0][len("error_") :].split("=", maxsplit=1)
        return name, code

    @staticmethod
    def _lines(raw: str) -> list[str]:
        return [line.strip() for line in raw.replace("\r", "").splitlines()]

    @staticmethod
    def _validate_operation(operation: int) -> None:
        if not isinstance(operation, int) or not 1 <= operation <= 65535:
            raise ValueError("Invalid Easynet operation")

    @staticmethod
    def _validate_address_range(address: int, count: int) -> None:
        if not 0 <= address <= 65535 or not 1 <= count <= 65536 - address:
            raise ValueError("Invalid Easynet address range")


async def close_clients(clients: Mapping[object, EasyNetClient]) -> None:
    await asyncio.gather(*(client.close() for client in clients.values()))

