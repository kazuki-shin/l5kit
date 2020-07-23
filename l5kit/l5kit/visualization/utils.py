from typing import Tuple

import cv2
import numpy as np

from l5kit.geometry import transform_points

PREDICTED_POINTS_COLOR = (0, 255, 255)
TARGET_POINTS_COLOR = (255, 0, 255)
REFERENCE_TRAJECTORY_POINT_COLOR = (255, 255, 0)
#  Arrows represent position + orientation.
ARROW_LENGTH_IN_PIXELS = 2
ARROW_THICKNESS_IN_PIXELS = 1


def draw_arrowed_line(on_image: np.ndarray, position: np.ndarray, yaw: float, rgb_color: Tuple[int, int, int]) -> None:
    """
    Draw a single arrowed line in an RGB image
    Args:
        on_image (np.ndarray): the RGB image to draw onto
        position (np.ndarray): the starting position of the arrow
        yaw (float): the arrow orientation
        rgb_color (Tuple[int, int, int]): the arrow color

    Returns: None

    """
    position = np.array(position[:2])
    start_pixel = np.int0(position)[:2]
    end_pixel = np.int0(position + np.array([np.cos(yaw), -np.sin(yaw)]) * ARROW_LENGTH_IN_PIXELS)
    cv2.arrowedLine(
        on_image, tuple(start_pixel), tuple(end_pixel), rgb_color, thickness=ARROW_THICKNESS_IN_PIXELS, tipLength=0.4
    )


def draw_trajectory(
    on_image: np.ndarray, positions: np.ndarray, yaws: np.ndarray, rgb_color: Tuple[int, int, int],
) -> None:
    """
    Draw a trajectory on oriented arrow onto an RGB image
    Args:
        on_image (np.ndarray): the RGB image to draw onto
        positions (np.ndarray): pixel coordinates in the image space (not displacements)
        yaws (np.ndarray): yaws in radians
        rgb_color (Tuple[int, int, int]): the trajectory RGB color

    Returns: None

    """
    for pos, yaw in zip(positions, yaws):
        pred_waypoint = pos[:2]
        pred_yaw = float(yaw[0])
        draw_arrowed_line(on_image, pred_waypoint, pred_yaw, rgb_color)


def draw_reference_trajectory(on_image: np.ndarray, world_to_pixel: np.ndarray, positions: np.ndarray) -> None:
    """
    Draw a trajectory (as points) onto the image
    Args:
        on_image (np.ndarray): the RGB image to draw onto
        world_to_pixel (np.ndarray): 3x3 matrix from meters to ego pixel space
        positions (np.ndarray): positions as 2D absolute meters coordinates

    Returns: None

    """
    positions_in_pixel_space = transform_points(np.array(positions), world_to_pixel)
    #  we clip the positions to be within the image
    mask = np.all(positions_in_pixel_space > (0.0, 0.0), 1) * np.all(positions_in_pixel_space < on_image.shape[:2], 1)
    positions_in_pixel_space = positions_in_pixel_space[mask]
    for pos in positions_in_pixel_space:
        cv2.circle(on_image, tuple(np.floor(pos).astype(np.int32)), 1, REFERENCE_TRAJECTORY_POINT_COLOR, -1)
