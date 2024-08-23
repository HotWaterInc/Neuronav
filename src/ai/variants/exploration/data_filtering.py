from src.ai.variants.exploration.algorithms import build_connections_hashmap, \
    find_minimum_distance_between_datapoints_on_graph_bfs
from src.ai.variants.exploration.exploration_evaluations import evaluate_distance_metric
from src.ai.runtime_data_storage.storage_superset2 import *
from src.ai.variants.exploration.metric_builders import build_find_adjacency_heursitic_adjacency_network, \
    build_find_adjacency_heursitic_raw_data
from src.utils import get_device


def filtering_metric_djakstra(storage: StorageSuperset2, datapoint: str) -> any:
    """
    Filtering datapoints by checking if they add any additional pathways between any of their neighbors in the topological graph
    """
    connection_hashmap = build_connections_hashmap(storage, [datapoint])
    connections_neighbors = storage.get_datapoint_adjacent_connections(datapoint)
    neighbors_count = len(connections_neighbors)

    is_redundant = True
    for idx in range(neighbors_count):
        for jdx in range(idx + 1, neighbors_count):
            start_neighbor = connections_neighbors[idx]["end"]
            end_neighbor = connections_neighbors[jdx]["end"]
            distance_to_start = connections_neighbors[idx]["distance"]
            distance_to_end = connections_neighbors[jdx]["distance"]

            distance_without_datapoint = find_minimum_distance_between_datapoints_on_graph_bfs(start_neighbor,
                                                                                               end_neighbor,
                                                                                               connection_hashmap)
            distance_with_datapoint = distance_to_start + distance_to_end
            if distance_without_datapoint > distance_with_datapoint * 1.25:
                print("Looks like is not redundant")
                print("Distances ", distance_without_datapoint, distance_with_datapoint)
                is_redundant = False

    return is_redundant


def filtering_redundancy_djakstra_based(storage: StorageSuperset2, datapoints: List[str]):
    count_redundant = 0
    count_not_redundant = 0

    for idx, datapoint in enumerate(datapoints):
        is_redundant = filtering_metric_djakstra(storage, datapoint)
        print("Processing", idx, "out of", len(datapoints))

        if is_redundant:
            count_redundant += 1
        else:
            count_not_redundant += 1

    print("Count not redundant", count_not_redundant)
    print("Count redundant", count_redundant)


def filtering_redundancy_neighbors_based(storage: StorageSuperset2, datapoints: List[str]):
    pass


def data_filtering_redundancies(storage: StorageSuperset2):
    """
    Filter redundant datapoints which don't add any value to the topological graph
    or enhance the neural networks in any way
    """

    datapoints = storage.get_all_datapoints()
    # filtering_redundancy_djakstra_based(storage, datapoints)
    # filtering_redundancy_neighbors_based()
