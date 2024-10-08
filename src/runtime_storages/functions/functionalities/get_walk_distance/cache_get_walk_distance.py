from typing import TYPE_CHECKING
from typing import List, Dict
from src.navigation_core.to_refactor.algorithms import build_connections_hashmap, floyd_warshall_algorithm
from ...basic_functions import connections_all_get

from src.runtime_storages.cache_abstract import CacheAbstract
from src.runtime_storages.functions.functionalities.functionalities_types import FunctionalityAlias
from src.runtime_storages.other import cache_specialized_get

if TYPE_CHECKING:
    from src.runtime_storages.storage_struct import StorageStruct
    from src.runtime_storages.types import ConnectionAuthenticData, ConnectionSyntheticData


class CacheGetWalkDistance(CacheAbstract):
    def __init__(self):
        self.distances: Dict = {}

    def read(self, start_node: str, end_node: str) -> float:
        return self.distances[start_node][end_node]


def on_create_connections(storage: 'StorageStruct',
                          new_connections: 'List[any]') -> None:
    invalidate_and_recalculate(storage)


def on_update_connections(storage: 'StorageStruct',
                          new_connections: 'List[ConnectionAuthenticData | ConnectionSyntheticData]') -> None:
    pass


def on_delete_connections(storage: 'StorageStruct',
                          deleted_connection: 'ConnectionAuthenticData | ConnectionSyntheticData') -> None:
    invalidate_and_recalculate(storage)


def on_create_nodes(storage: 'StorageStruct', new_nodes: 'List[any]') -> None:
    invalidate_and_recalculate(storage)


def on_update_nodes(storage: 'StorageStruct', old_nodes: List[any], new_nodes: List[any]) -> None:
    pass


def on_delete_nodes(storage: 'StorageStruct', deleted_node: any) -> None:
    invalidate_and_recalculate(storage)


def invalidate_and_recalculate(storage: 'StorageStruct') -> None:
    cache = cache_specialized_get(storage, FunctionalityAlias.GET_WALK_DISTANCE)
    cache = validate_cache_get_walk_distance(cache)
    connections = connections_all_get(storage)
    connection_hashmap = build_connections_hashmap(connections, [])
    distances = floyd_warshall_algorithm(connection_hashmap)
    cache.distances = distances


def validate_cache_get_walk_distance(cache: CacheAbstract) -> CacheGetWalkDistance:
    if not isinstance(cache, CacheGetWalkDistance):
        raise ValueError(f"Expected CacheGetWalkDistance, got {type(cache)}")
    return cache
