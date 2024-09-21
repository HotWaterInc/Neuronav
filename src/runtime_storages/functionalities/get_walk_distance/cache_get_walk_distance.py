from typing import TYPE_CHECKING
from typing import List, Dict
from src.navigation_core.algorithms import build_connections_hashmap, floyd_warshall_algorithm
from src.runtime_storages.cache_abstract import CacheAbstract
from src.runtime_storages.functionalities.functionalities_types import FunctionalityAlias
from src.runtime_storages.functions.cache_functions import cache_specialized_get
from src.runtime_storages.types import ConnectionNullData, ConnectionAuthenticData, ConnectionSyntheticData
from src import runtime_storages as runtime_storage

if TYPE_CHECKING:
    from src.runtime_storages.storage_struct import StorageStruct


class CacheGetWalkDistance(CacheAbstract):
    def __init__(self):
        self.distances: Dict = {}

    def read(self, start_node: str, end_node: str) -> float:
        return self.distances[start_node][end_node]


def on_create_connections(storage: 'StorageStruct',
                          new_connections: List[any]) -> None:
    invalidate_and_recalculate(storage)


def on_update_connections(storage: 'StorageStruct',
                          new_connections: List[ConnectionAuthenticData | ConnectionSyntheticData]) -> None:
    pass


def on_delete_connections(storage: 'StorageStruct',
                          deleted_connection: ConnectionAuthenticData | ConnectionSyntheticData) -> None:
    invalidate_and_recalculate(storage)


def on_create_nodes(storage: 'StorageStruct', new_nodes: List[any]) -> None:
    invalidate_and_recalculate(storage)


def on_update_nodes(storage: 'StorageStruct', new_nodes: List[any]) -> None:
    pass


def on_delete_nodes(storage: 'StorageStruct', deleted_node: any) -> None:
    invalidate_and_recalculate(storage)


def invalidate_and_recalculate(storage: 'StorageStruct') -> None:
    cache = cache_specialized_get(storage, FunctionalityAlias.WALK_DISTANCE_CACHE)
    if not isinstance(cache, CacheGetWalkDistance):
        raise ValueError("Cache not found")

    connections = runtime_storage.connections_all_get(
        self=storage,

    )
    connection_hashmap = build_connections_hashmap(connections, [])
    distances = floyd_warshall_algorithm(connection_hashmap)
    cache.distances = distances
