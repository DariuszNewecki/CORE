from __future__ import annotations

import socket
import struct
from unittest.mock import MagicMock


# ID: d17277b4-c0e4-4348-88e1-83342d73771a
def test_read_peer_cred():
    from api.serve import read_peer_cred

    mock_sock = MagicMock(spec=socket.socket)
    mock_sock.family = socket.AF_UNIX
    expected = {"pid": 4321, "uid": 1000, "gid": 1001}
    mock_sock.getsockopt.return_value = struct.Struct("3i").pack(
        expected["pid"], expected["uid"], expected["gid"]
    )

    result = read_peer_cred(mock_sock)

    assert result == expected
    mock_sock.getsockopt.assert_called_once()


from pathlib import Path
from unittest.mock import patch

from api.serve import main


# ID: 830f1938-be6c-4487-876c-5e6ddb554966
def test_main(tmp_path):
    uds = tmp_path / "api.sock"
    tcp_sock = MagicMock(name="tcp_socket")
    unix_sock = MagicMock(name="unix_socket")
    server_instance = MagicMock()
    server_instance.started = True
    config = MagicMock(name="uvicorn_config")

    with (
        patch("api.serve.bind_tcp_socket", return_value=tcp_sock) as mock_bind_tcp,
        patch("api.serve.bind_unix_socket", return_value=unix_sock) as mock_bind_unix,
        patch("api.serve.producer_socket", return_value=None) as mock_producer,
        patch("api.serve.build_config", return_value=config) as mock_build_config,
        patch(
            "api.serve.uvicorn.Server", return_value=server_instance
        ) as mock_server_cls,
        patch.dict("os.environ", {}, clear=True),
    ):
        main(argv=["--uds", str(uds), "--host", "127.0.0.1", "--port", "8000"])

    mock_bind_tcp.assert_called_once_with("127.0.0.1", 8000)
    mock_bind_unix.assert_called_once_with(Path(uds))
    mock_build_config.assert_called_once_with("api.main:app", log_level="info")
    mock_server_cls.assert_called_once_with(config)
    server_instance.run.assert_called_once_with(sockets=[tcp_sock, unix_sock])
