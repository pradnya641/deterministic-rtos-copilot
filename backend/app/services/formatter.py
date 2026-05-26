def format_output(answer: str, status: str = "success") -> dict:
    """
    Formats the final response into a standard JSON structure.
    """
    return {
        "status": status,
        "response": answer
    }
