"""Verify BioImageViewer routes chunk messages to PixelSourceMixin."""
import numpy as np

from anybioimage import BioImageViewer


def test_chunk_message_is_routed():
    v = BioImageViewer()
    v._chunk_array = np.zeros((1, 1, 1, 10, 10), dtype=np.uint8)

    sent = []
    v._send_chunk_response = lambda msg, bufs: sent.append((msg, bufs))

    v._route_message(v, {
        "kind": "chunk", "requestId": 1,
        "t": 0, "c": 0, "z": 0, "level": 0,
        "tx": 0, "ty": 0, "tileSize": 512,
    }, [])
    assert sent and sent[0][0]["ok"] is True
