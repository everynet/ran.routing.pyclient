class DownstreamError(Exception):
    pass


class DownstreamConnectionClosed(DownstreamError):
    pass


class DownstreamConnectionClosedOk(DownstreamConnectionClosed):
    pass


class DownstreamConnectionClosedAbnormally(DownstreamConnectionClosed):
    pass
