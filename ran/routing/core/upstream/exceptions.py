class UpstreamError(Exception):
    pass


class UpstreamConnectionClosed(UpstreamError):
    pass


class UpstreamConnectionClosedOk(UpstreamConnectionClosed):
    pass


class UpstreamConnectionClosedAbnormally(UpstreamConnectionClosed):
    pass
