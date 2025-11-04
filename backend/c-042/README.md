# Mutation Testing Flask Project

## Setup
```bash
pip install -r requirements.txt
```

## Run Tests
```bash
pytest tests/
```

## Run Mutation Testing
```bash
mutmut run
mutmut results
mutmut show
```

## Suggested Fixes for Common Uncovered Mutants

1. **Boundary Conditions**: Add tests for edge cases (empty lists, negative indices)
2. **Return Value Checks**: Verify exact error messages and status codes
3. **Operator Mutations**: Test conditions like `<` vs `<=`, `>` vs `>=`
4. **String Mutations**: Test with empty strings, None values
5. **Number Mutations**: Test with 0, negative numbers, large numbers

## Example Improvements

- Test negative index in delete_item
- Test boundary at len(data_store)
- Test all error messages explicitly
- Test with None instead of missing keys

