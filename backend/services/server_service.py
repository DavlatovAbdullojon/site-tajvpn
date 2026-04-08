from schemas import ServerResponse


SERVERS = [
    ServerResponse(
        id="tr-istanbul-01",
        country="Турция",
        countryCode="TR",
        city="Стамбул",
        host="tr-istanbul-01.tajvpn.com",
        latencyMs=43,
        isOnline=True,
        isRecommended=True,
    ),
    ServerResponse(
        id="de-frankfurt-01",
        country="Германия",
        countryCode="DE",
        city="Франкфурт",
        host="de-frankfurt-01.tajvpn.com",
        latencyMs=58,
        isOnline=True,
    ),
    ServerResponse(
        id="nl-amsterdam-01",
        country="Нидерланды",
        countryCode="NL",
        city="Амстердам",
        host="nl-amsterdam-01.tajvpn.com",
        latencyMs=64,
        isOnline=True,
    ),
]


def get_servers() -> list[ServerResponse]:
    return SERVERS


def get_server_by_id(server_id: str) -> ServerResponse | None:
    for server in SERVERS:
        if server.id == server_id:
            return server
    return None
