# Error Handling (`backend`)

> Unified exception handling standards.

---

## Conventions

1. **Domain Exceptions**: Subclass `DomainException` located in `app.exceptions.base`.
2. **HTTP Mapping**: Raise `DomainException` with a clear message and status code, caught by `domain_exception_handler` in `app.exceptions.handlers` which transforms it into standard JSON format:
   ```json
   {
     "code": "ERROR_CODE",
     "message": "Human readable detail"
   }
   ```
3. **No Bare Except**: Never use bare `except:`; specify the concrete Exception type and log unexpected exceptions before re-raising or returning a 500 error.
4. **Validation**: Rely on Pydantic `ValidationError` for bad input payloads (FastAPI handles this automatically with 422).
