class Model:
    """Dummy model v1 for demonstration.
    Behavior: reverse the input string and annotate with version.
    """

    def __init__(self):
        self.version = "v1"

    def predict(self, text: str):
        if text is None:
            raise ValueError("Input text is required")
        return {
            "version": self.version,
            "result": text[::-1],
        }

