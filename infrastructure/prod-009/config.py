import os
from datetime import timedelta

class Config:
    def __init__(self):
        self.JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
        self.ACCESS_TOKEN_EXPIRES = int(os.getenv("ACCESS_TOKEN_EXPIRES_MIN", "15"))  # minutes
        self.REFRESH_TOKEN_EXPIRES = int(os.getenv("REFRESH_TOKEN_EXPIRES_DAYS", "7"))  # days

        self.SESSION_ABSOLUTE_DAYS = int(os.getenv("SESSION_ABSOLUTE_DAYS", "30"))
        self.SESSION_IDLE_MIN = int(os.getenv("SESSION_IDLE_MIN", "1440")) # 24h default

        self.REDIS_URL = os.getenv("REDIS_URL")
        self.REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
        self.REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
        self.REDIS_DB = int(os.getenv("REDIS_DB", "0"))

        self.STRICT_UA_MATCH = os.getenv("STRICT_UA_MATCH", "0") == "1"

    @property
    def ACCESS_TOKEN_EXPIRES_SECONDS(self):
        return self.ACCESS_TOKEN_EXPIRES * 60

    @property
    def REFRESH_TOKEN_EXPIRES_SECONDS(self):
        return self.REFRESH_TOKEN_EXPIRES * 24 * 60 * 60

    @property
    def SESSION_ABSOLUTE_SECONDS(self):
        return self.SESSION_ABSOLUTE_DAYS * 24 * 60 * 60

    @property
    def SESSION_IDLE_SECONDS(self):
        return self.SESSION_IDLE_MIN * 60

