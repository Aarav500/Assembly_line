import os
import sys
from redis import Redis
from dotenv import load_dotenv
load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
KEY_PREFIX = os.getenv("RL_REDIS_KEY_PREFIX", "rl")

r = Redis.from_url(REDIS_URL, decode_responses=False)

usage = """Usage:
  python admin.py ban <ip> [seconds]
  python admin.py unban <ip>
  python admin.py status <ip>
"""

def ban(ip: str, seconds: int):
    r.setex(f"{KEY_PREFIX}:ban:{ip}", seconds, b"1")
    print(f"Banned {ip} for {seconds} seconds")

def unban(ip: str):
    r.delete(f"{KEY_PREFIX}:ban:{ip}")
    print(f"Unbanned {ip}")

def status(ip: str):
    ttl = r.ttl(f"{KEY_PREFIX}:ban:{ip}")
    if ttl and ttl > 0:
        print(f"{ip} is banned. TTL: {ttl}s")
    else:
        print(f"{ip} is not banned")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(usage)
        sys.exit(1)
    cmd = sys.argv[1]
    ip = sys.argv[2]
    if cmd == "ban":
        seconds = int(sys.argv[3]) if len(sys.argv) > 3 else int(os.getenv("RL_BAN_DURATION", "900"))
        ban(ip, seconds)
    elif cmd == "unban":
        unban(ip)
    elif cmd == "status":
        status(ip)
    else:
        print(usage)
        sys.exit(1)

