"""Call the configured OpenAI chat model for the LLM RAG option."""

from course_assistant.rag.config import load_config, load_environment


def generate(prompt: str) -> str:
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import PromptTemplate
    from langchain_openai import ChatOpenAI

    config = load_config()
    if config["provider"] != "openai":
        raise ValueError(f"Unsupported RAG provider: {config['provider']!r}")

    load_environment()
    model = ChatOpenAI(
        model=config["model"],
        max_completion_tokens=config["max_completion_tokens"],
        temperature=config["temperature"],
    )
    prompt_template = PromptTemplate.from_template("{prompt}")
    chain = prompt_template | model | StrOutputParser()
    answer = chain.invoke({"prompt": prompt})
    if not answer.strip():
        raise RuntimeError("The configured chat model returned an empty answer.")
    return answer
