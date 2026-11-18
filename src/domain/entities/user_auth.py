from dataclasses import dataclass 
from datetime import date   

@dataclass
class UserAuth:
    id: int
    username: str
    password: str
    is_active: bool
