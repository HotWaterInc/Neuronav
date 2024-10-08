from typing import Dict, List
from scipy.stats import norm
import torch
import numpy as np
import math
from src.runtime_storages.types import NodeAuthenticData, ConnectionAuthenticData, ConnectionSyntheticData
from src.utils.utils import get_device


def get_distance_coords_pair(coords1: any, coords2: any) -> float:
    x1, y1 = coords1
    x2, y2 = coords2
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def get_real_distance_between_datapoints(node1: NodeAuthenticData, datapoint2: NodeAuthenticData) -> float:
    coords1 = node1["params"]["x"], node1["params"]["y"]
    coords2 = datapoint2["params"]["x"], datapoint2["params"]["y"]
    return get_distance_coords_pair(coords1, coords2)


def get_direction_between_datapoints(datapoint1: Dict[str, any], datapoint2: Dict[str, any]) -> list:
    coords1 = datapoint1["params"]["x"], datapoint1["params"]["y"]
    coords2 = datapoint2["params"]["x"], datapoint2["params"]["y"]
    direction_vector = [coords2[0] - coords1[0], coords2[1] - coords1[1]]
    return direction_vector


def sample_n_elements(data: List[any], n: int) -> List[any]:
    if n >= len(data):
        return data

    return np.random.choice(data, n, replace=False)


def relative_difference(a, b):
    return abs(a - b) / ((a + b) / 2)


def normalize_direction(direction):
    direction = torch.tensor(direction, dtype=torch.float32, device=get_device())
    l2_direction = torch.norm(direction, p=2, dim=0, keepdim=True)
    direction = direction / l2_direction
    return direction


def calculate_coords_distance(coords1: list[float], coords2: list[float]) -> float:
    return math.sqrt((coords1[0] - coords2[0]) ** 2 + (coords1[1] - coords2[1]) ** 2)


def get_markings(distance_authenticity: bool, direction_authenticity: bool):
    distance_authenticity_str = "authentic" if distance_authenticity else "synthetic"
    direction_authenticity_str = "authentic" if direction_authenticity else "synthetic"

    markings = {
        "direction": direction_authenticity_str,
        "distance": distance_authenticity_str
    }

    return markings


def generate_connection(start, end, distance, direction, distance_authenticity,
                        direction_authenticity):
    markings = get_markings(distance_authenticity, direction_authenticity)
    connection = {
        "start": start,
        "end": end,
        "distance": distance,
        "direction": direction,
        "markings": markings
    }

    return connection


def flag_data_authenticity(new_connections: List[ConnectionAuthenticData]):
    """
    Flags whether data is synthetically generated or authentic
    """
    marked_connections = []
    for connection in new_connections:
        start = connection["start"]
        end = connection["end"]
        direction = connection["direction"]
        distance = connection["distance"]
        markings = {
            "direction": "authentic",
            "distance": "authentic"
        }
        if direction is None:
            markings["direction"] = "synthetic"
        if distance is None:
            markings["distance"] = "synthetic"

        connection[""] = markings
        marked_connections.append(connection)

    return marked_connections


def direction_to_degrees_atan(direction: list[float]) -> float:
    y = direction[1]
    x = direction[0]

    # Calculate the angle in radians using atan2
    angle_rad = math.atan2(x, y)

    # Convert radians to degrees
    angle_deg = math.degrees(angle_rad)

    # Normalize the angle to be between 0 and 360 degrees
    normalized_angle = (angle_deg + 360) % 360
    # account for weird representation
    normalized_angle = (360 - angle_deg) % 360

    return normalized_angle


def radians_to_degrees(radians):
    return radians * 180 / np.pi


def atan2_to_standard_radians(atan2):
    if atan2 < 0:
        atan2 = atan2 + 2 * np.pi

    atan2 = 2 * np.pi - atan2
    return atan2


def degrees_to_percent(angle_degrees):
    return angle_degrees / 360


def radians_to_percent(radians):
    return radians / (2 * np.pi)


_cache_distances = {}


def distance_thetas_to_distance_percent(thetas):
    length = len(thetas)
    step = 1 / length
    distance_result = 0
    for i in range(length):
        distance = i * step
        distance_result += distance * thetas[i]

    # the thetas arr should already be normalized but just in case
    l1_norm = torch.norm(thetas, p=1)
    distance_result /= l1_norm

    return distance_result


def distance_percent_to_distance_thetas(true_theta_percent, thetas_length):
    thetas = torch.zeros(thetas_length)
    if true_theta_percent >= 1:
        true_theta_percent = 0.99

    true_theta_index = true_theta_percent * thetas_length
    if true_theta_index in _cache_distances:
        return _cache_distances[true_theta_index]

    integer_index_left = int(true_theta_index)
    integer_index_right = integer_index_left + 1

    FILL_DISTANCE = 3
    SD = 1
    for i in range(FILL_DISTANCE):
        left_index = integer_index_left - i
        right_index = integer_index_right + i

        if left_index > 0:
            pdf_value = norm.pdf(left_index, loc=true_theta_index, scale=SD)
            thetas[left_index] = pdf_value

        if right_index < len(thetas):
            pdf_value = norm.pdf(right_index, loc=true_theta_index, scale=SD)
            thetas[right_index] = pdf_value

    l1_norm = torch.norm(thetas, p=1)
    thetas /= l1_norm
    _cache_distances[true_theta_index] = thetas
    return thetas


_cache_thetas = {}


def angle_radians_to_percent(angle_radians):
    return angle_radians / (2 * np.pi)


def angle_percent_to_radians(angle_percent):
    return angle_percent * 2 * np.pi


def angle_percent_to_thetas_normalized_cached(true_theta_percent: float, thetas_length: int) -> torch.Tensor:
    thetas = torch.zeros(thetas_length)
    if true_theta_percent == 1:
        true_theta_percent = 0

    if true_theta_percent in _cache_thetas:
        return _cache_thetas[true_theta_percent]

    true_theta_index = true_theta_percent * thetas_length
    integer_index_left = int(true_theta_index)
    integer_index_right = integer_index_left + 1

    FILL_DISTANCE = 5
    SD = 1.5
    for i in range(FILL_DISTANCE):
        left_index = integer_index_left - i
        right_index = integer_index_right + i

        pdf_value = norm.pdf(left_index, loc=true_theta_index, scale=SD)
        if left_index < 0:
            left_index = len(thetas) + left_index

        thetas[left_index] = pdf_value

        pdf_value = norm.pdf(right_index, loc=true_theta_index, scale=SD)
        if right_index >= len(thetas):
            right_index = right_index - len(thetas)
        thetas[right_index] = pdf_value

    l1_norm = torch.norm(thetas, p=1)
    thetas /= l1_norm

    _cache_thetas[true_theta_percent] = thetas
    return thetas


def deg_to_rad(degrees):
    return degrees * math.pi / 180


def direction_thetas_to_radians(thetas):
    # theta is cos x + i sin x
    lng = len(thetas)
    step = 360 / lng
    real_arr = []
    imag_arr = []
    for i in range(lng):
        degree = i * step
        radians = deg_to_rad(degree)

        real = math.cos(radians)
        imag = math.sin(radians)

        real_arr.append(real)
        imag_arr.append(imag)

    real_sum = 0
    imag_sum = 0
    for i in range(lng):
        real_sum += real_arr[i] * thetas[i]
        imag_sum += imag_arr[i] * thetas[i]

    real_sum /= lng
    imag_sum /= lng

    angle = math.atan2(imag_sum, real_sum)
    if angle < 0:
        angle += 2 * math.pi

    return angle


def find_thetas_null_indexes(thetas):
    null_indexes = []
    for i in range(len(thetas)):
        if thetas[i] <= 0:
            null_indexes.append(i)

    return null_indexes


def get_angle_percent_from_thetas_index(index, thetas_length):
    return index / thetas_length


def generate_dxdy(direction: float, distance: float) -> tuple[float, float]:
    # direction in radians
    dx = -distance * math.sin(direction)
    dy = distance * math.cos(direction)

    return dx, dy


def check_connection_already_existing(connections_arr: List[ConnectionAuthenticData | ConnectionSyntheticData],
                                      start: str, end: str):
    """
    Check if the connection already exists
    """
    for connection in connections_arr:
        if connection["start"] == start and connection["end"] == end:
            return True
        if connection["start"] == end and connection["end"] == start:
            return True
    return False


def calculate_manifold_distances(manifold1: torch.Tensor, manifold2: torch.Tensor) -> float:
    return torch.norm(manifold1 - manifold2, p=2, dim=0).item()


def calculate_angle(x_vector, y_vector):
    dot_product = x_vector[0] * y_vector[0] + x_vector[1] * y_vector[1]
    determinant = x_vector[0] * y_vector[1] - x_vector[1] * y_vector[0]
    angle = math.atan2(determinant, dot_product)
    return angle


def degrees_to_radians(degrees: float) -> float:
    return degrees * math.pi / 180


def build_connection_name(start: str, end: str) -> str:
    return f"{start}_{end}"


def connection_reverse_order(
        connection: ConnectionAuthenticData | ConnectionSyntheticData) -> ConnectionSyntheticData:
    new_connection = ConnectionSyntheticData(
        name=connection["name"],
        start=connection["end"],
        end=connection["start"],
        distance=connection["distance"],
        direction=[-x for x in connection["direction"]],
    )
    return new_connection


def direction_radians_to_xy(radians: float, distance: float) -> List[float]:
    x = distance * math.cos(radians)
    y = distance * math.sin(radians)
    return [x, y]


def xy_direction_to_xy_webots(x, y):
    """
    Counterclockwise rotation of 90 degrees. Webots is just weird.
    """
    rotation_matrix = np.array([[0, -1],
                                [1, 0]])
    coordinates = np.array([x, y])
    rotated_coordinates = np.dot(rotation_matrix, coordinates)
    return [rotated_coordinates[0], rotated_coordinates[1]]


def direction_to_xy_webots(radians: float, distance: float) -> List[float]:
    x = distance * math.cos(radians)
    y = distance * math.sin(radians)
    return xy_direction_to_xy_webots(x, y)
