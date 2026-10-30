def test(**kwargs):
    from .grammar_generator import generate
    from .parser_semantic import process_sentences

    grammar_result = generate(
        grammar_path=kwargs.get("grammar_path"),
        data_dir=kwargs.get("data_dir"),
        output_dir=kwargs.get("output_dir"),
        max_sentences=kwargs.get("max_sentences", 10000),
    )
    parser_result = process_sentences(
        grammar_path=grammar_result["grammar_path"],
        input_dir=kwargs.get("input_dir"),
        output_dir=kwargs.get("output_dir"),
        data_dir=kwargs.get("data_dir"),
    )
    return {"grammar": grammar_result, "parser": parser_result}
