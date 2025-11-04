from dataclasses import dataclass

@dataclass
class BaseAgent:
    name: str
    role: str

    def info(self):
        return {"name": self.name, "role": self.role}

