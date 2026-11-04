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


# ID: 6f0e07e1-cb6f-40de-92b8-d99307a9c260
def test_build_config():
    from api.serve import build_config

    with patch("api.serve.uvicorn") as mock_uvicorn:
        mock_config = MagicMock()
        mock_uvicorn.Config.return_value = mock_config

        result = build_config(app="api.main:app", log_level="debug")

        mock_uvicorn.Config.assert_called_once_with(
            "api.main:app",
            http=build_config.__globals__["PeerCredH11Protocol"],
            log_level="debug",
        )
        assert result is mock_config


from api.serve import bind_tcp_socket


# ID: 4cfa5b67-4743-4548-9959-801379cf764a
def test_bind_tcp_socket():
    fake_sock = MagicMock()

    with patch("api.serve.socket.socket", return_value=fake_sock) as mock_socket:
        result = bind_tcp_socket("127.0.0.1", 8080)

    mock_socket.assert_called_once_with(
        __import__("socket").AF_INET, __import__("socket").SOCK_STREAM
    )
    fake_sock.setsockopt.assert_called_once_with(
        __import__("socket").SOL_SOCKET, __import__("socket").SO_REUSEADDR, 1
    )
    fake_sock.bind.assert_called_once_with(("127.0.0.1", 8080))
    fake_sock.listen.assert_called_once_with(__import__("socket").SOMAXCONN)
    assert result is fake_sock


from api.serve import producer_socket


# ID: 38f48b79-9ccb-4e80-9b0a-5b78c4118714
def test_producer_socket(tmp_path):
    sock_path = tmp_path / "producer.sock"
    fake_socket = MagicMock()
    with patch("api.serve.bind_unix_socket", return_value=fake_socket) as mock_bind:
        result = producer_socket(sock_path)
    assert result is fake_socket
    mock_bind.assert_called_once()
    assert mock_bind.call_args[0][0] == sock_path



from api.serve import bind_unix_socket


# ID: ce1e445c-c2cf-4121-84a6-902b907c33cf
def test_bind_unix_socket(tmp_path: Path) -> None:
    sock_path = tmp_path / "api.sock"

    mock_sock = MagicMock()
    mock_socket_module = MagicMock()
    mock_socket_module.AF_UNIX = "AF_UNIX"
    mock_socket_module.SOCK_STREAM = "SOCK_STREAM"
    mock_socket_module.SOMAXCONN = 128
    mock_socket_module.socket.return_value = mock_sock

    with patch("api.serve.socket", mock_socket_module):
        result = bind_unix_socket(sock_path)

    mock_socket_module.socket.assert_called_once_with("AF_UNIX", "SOCK_STREAM")
    mock_sock.bind.assert_called_once_with(str(sock_path))
    mock_sock.listen.assert_called_once_with(128)
    assert result is mock_sock
