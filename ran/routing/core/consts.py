from enum import Enum, auto


class RanRoutingApiService(Enum):
    ROUTING = auto()
    MULTICAST = auto()
    UPSTREAM = auto()
    DOWNSTREAM = auto()


API_PATH_MAP = {
    RanRoutingApiService.ROUTING: "/",
    RanRoutingApiService.MULTICAST: "/multicast/",
    RanRoutingApiService.UPSTREAM: "/stream/upstream/",
    RanRoutingApiService.DOWNSTREAM: "/stream/downstream/",
}
API_SCHEMA_MAP = {
    RanRoutingApiService.ROUTING: "https",
    RanRoutingApiService.MULTICAST: "https",
    RanRoutingApiService.UPSTREAM: "wss",
    RanRoutingApiService.DOWNSTREAM: "wss",
}
