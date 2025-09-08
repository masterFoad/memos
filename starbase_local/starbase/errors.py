class StarbaseError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, request_id: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.request_id = request_id


class AuthError(StarbaseError):
    pass


class NotFoundError(StarbaseError):
    pass


class ValidationError(StarbaseError):
    pass


class ServerError(StarbaseError):
    pass


class TimeoutError(StarbaseError):
    pass


