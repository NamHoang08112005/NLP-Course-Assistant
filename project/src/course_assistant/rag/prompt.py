"""Build a grounded prompt from the question and retrieved course context."""

from course_assistant.contracts import RetrievedChunk


def build_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    raise NotImplementedError("Group B: construct context and answer instructions.")
