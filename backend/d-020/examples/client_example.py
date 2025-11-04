from logger_client import TokenCostLoggerClient

if __name__ == "__main__":
    client = TokenCostLoggerClient(base_url="http://localhost:5000")

    # Example with explicit tokens
    resp = client.log_event(
        workflow_id="data-pipeline-ingest",
        provider="openai",
        model="gpt-4o-mini",
        prompt_tokens=123,
        completion_tokens=456,
        metadata={"step": "summarize", "env": "dev"}
    )
    print("Logged:", resp)

    # Example with text (tokens estimated on server)
    resp = client.log_event(
        workflow_id="data-pipeline-ingest",
        provider="openai",
        model="gpt-3.5-turbo",
        prompt_text="Explain quantum entanglement in simple terms.",
        completion_text="Quantum entanglement is a phenomenon...",
        metadata={"step": "explain"}
    )
    print("Logged:", resp)

