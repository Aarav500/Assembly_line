def pre_mutation(context):
    if context.filename == "tests/test_app.py" or context.filename == "tests\\test_app.py":
        context.skip = True
