from datetime import datetime

def parse_infobip_datetime(value: str | None):
    if not value:
        return None
    base = value[:19] 
    return datetime.strptime(base, "%Y-%m-%dT%H:%M:%S")