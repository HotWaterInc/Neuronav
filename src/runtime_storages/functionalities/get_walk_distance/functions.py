from src.runtime_storages.functionalities.functionalities_types import FunctionalityAlias
from src.runtime_storages.functionalities.get_walk_distance import CacheGetWalkDistance
from src.runtime_storages.functionalities.get_walk_distance.cache_get_walk_distance import \
    validate_cache_get_walk_distance
from src.runtime_storages.other import cache_specialized_get
from src.runtime_storages.storage_struct import StorageStruct


def get_walk_distance(storage: StorageStruct, start_node: str, end_node: str) -> float:
    cache = cache_specialized_get(storage, FunctionalityAlias.GET_WALK_DISTANCE)
    cache = validate_cache_get_walk_distance(cache)

    return cache.read(
        start_node=start_node,
        end_node=end_node,
    )
