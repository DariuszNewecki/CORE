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
