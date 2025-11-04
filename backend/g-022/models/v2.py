class Model:
    """Dummy model v2 for demonstration.
    Behavior: uppercase the input string and annotate with version.
    """

    def __init__(self):
        self.version = "v2"

    def predict(self, text: str):
        if text is None:
            raise ValueError("Input text is required")
        return {
            "version": self.version,
            "result": text.upper(),
        }

