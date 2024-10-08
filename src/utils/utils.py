import numpy as np
from rich import print
from rich.console import Console
from rich.table import Table
import torch
import json
import time
import os
import sys

from src.agent_communication import CommunicationController
from src.utils.configs_loader import load_config_ini


def string_to_json(data):
    try:
        return json.loads(data)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return None


def json_to_string(data):
    try:
        return json.dumps(data)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return None


def save_ai(name, network):
    current_time = time.time()
    torch.save(network.state_dict(), name + ' - ' + str(current_time) + '.pth')


def get_project_root() -> str:
    """Return the absolute path to the project root."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    while current_dir != os.path.dirname(current_dir):  # Root has the same parent directory
        if '.root' in os.listdir(current_dir):
            return current_dir
        current_dir = os.path.dirname(current_dir)
    return current_dir


def prefix_path_with_root(path):
    root_path = get_project_root()
    return root_path + "/" + path


def tensor_to_dtype(data) -> torch.Tensor:
    data = data.to(torch.float32)
    return data


def array_to_tensor(data):
    return torch.tensor(data, dtype=torch.float32)


def perror(*args, **kwargs):
    print("ERROR: ", *args, file=sys.stderr, **kwargs)


def get_instance():
    return CommunicationController.get_instance()


def get_console() -> Console:
    global console
    if not console:
        console = Console(force_terminal=True)
    return console


def get_device():
    global device
    if not device:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return device


def get_debug():
    global DEBUG
    if not DEBUG:
        DEBUG = load_config_ini()

    return DEBUG


def get_testing():
    global TESTING
    return TESTING


def set_testing(value):
    global TESTING
    TESTING = value


TESTING = False
DEBUG = None
device = None
console = None
