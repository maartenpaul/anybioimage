"""The frontend sends one tile request at a time and waits for the reply that
echoes its id, so every request must be answered, also when no tile is in
bounds, and two identical requests must produce two distinct replies."""
import numpy as np
import pytest

from anybioimage import BioImageViewer


@pytest.fixture
def tiled_viewer():
    viewer = BioImageViewer()
    viewer.set_image(np.random.randint(0, 4000, (2, 1, 1, 1024, 1024), dtype=np.uint16))
    viewer._use_tile_mode = True  # set by the frontend for images of 1 MP and up
    return viewer


def _request(viewer, req_id, tiles):
    viewer._tile_request = {"tiles": tiles, "t": 1, "z": 0, "id": req_id, "timestamp": req_id}
    return viewer._tiles_data


def test_reply_echoes_request_id_with_tiles(tiled_viewer):
    reply = _request(tiled_viewer, 7, [{"tx": 0, "ty": 0}, {"tx": 1, "ty": 0}])
    assert reply["_req"] == 7
    assert set(reply) == {"_req", "1_0_0_0", "1_0_1_0"}


def test_out_of_bounds_request_still_gets_a_reply(tiled_viewer):
    reply = _request(tiled_viewer, 8, [{"tx": 99, "ty": 99}])
    assert reply == {"_req": 8}


def test_repeated_request_produces_a_new_reply(tiled_viewer):
    first = _request(tiled_viewer, 9, [{"tx": 0, "ty": 0}])
    second = _request(tiled_viewer, 10, [{"tx": 0, "ty": 0}])
    assert first != second and second["_req"] == 10
