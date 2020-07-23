import functools
from typing import Callable

import numpy as np
import pytest

from l5kit.configs import load_config_data
from l5kit.data import AGENT_DTYPE, FRAME_DTYPE, ChunkedStateDataset
from l5kit.rasterization import StubRasterizer
from l5kit.sampling import generate_agent_sample


@pytest.fixture(scope="module")
def zarr_dataset() -> ChunkedStateDataset:
    zarr_dataset = ChunkedStateDataset(path="./l5kit/tests/artefacts/single_scene.zarr")
    zarr_dataset.open()
    return zarr_dataset


@pytest.fixture(scope="module")
def cfg() -> dict:
    cfg = load_config_data("./l5kit/tests/artefacts/config.yaml")
    return cfg


def get_partial(
    cfg: dict, history_num_frames: int, history_step_size: int, future_num_frames: int, future_step_size: int
) -> Callable:
    rast_params = cfg["raster_params"]

    rasterizer = StubRasterizer(
        rast_params["raster_size"],
        np.asarray(rast_params["pixel_size"]),
        np.asarray(rast_params["ego_center"]),
        rast_params["filter_agents_threshold"],
    )
    return functools.partial(
        generate_agent_sample,
        raster_size=rast_params["raster_size"],
        pixel_size=np.asarray(rast_params["pixel_size"]),
        ego_center=np.asarray(rast_params["ego_center"]),
        history_num_frames=history_num_frames,
        history_step_size=history_step_size,
        future_num_frames=future_num_frames,
        future_step_size=future_step_size,
        filter_agents_threshold=rast_params["filter_agents_threshold"],
        rasterizer=rasterizer,
    )


def test_no_frames(zarr_dataset: ChunkedStateDataset, cfg: dict) -> None:
    gen_partial = get_partial(cfg, 2, 1, 4, 1)
    with pytest.raises(IndexError):
        gen_partial(
            state_index=0, frames=np.zeros(0, FRAME_DTYPE), agents=np.zeros(0, AGENT_DTYPE), selected_track_id=None,
        )


def test_out_bounds(zarr_dataset: ChunkedStateDataset, cfg: dict) -> None:
    gen_partial = get_partial(cfg, 0, 1, 10, 1)
    data = gen_partial(
        state_index=0,
        frames=np.asarray(zarr_dataset.frames[90:96]),
        agents=zarr_dataset.agents,
        selected_track_id=None,
    )
    assert bool(np.all(data["target_availabilities"][:5])) is True
    assert bool(np.all(data["target_availabilities"][5:])) is False


def test_future(zarr_dataset: ChunkedStateDataset, cfg: dict) -> None:
    steps = [(1, 1), (2, 2), (4, 4)]  # all of these should work
    for step, step_size in steps:
        gen_partial = get_partial(cfg, 2, 1, step, step_size)
        data = gen_partial(
            state_index=10,
            frames=np.asarray(zarr_dataset.frames[90:150]),
            agents=zarr_dataset.agents,
            selected_track_id=None,
        )
        assert data["target_positions"].shape == (step, 2)
        assert data["target_yaws"].shape == (step, 1)
        assert data["target_availabilities"].shape == (step, 3)
        assert data["centroid"].shape == (2,)
        assert isinstance(data["yaw"], float)
        assert data["extent"].shape == (3,)
        assert bool(np.all(data["target_availabilities"])) is True
