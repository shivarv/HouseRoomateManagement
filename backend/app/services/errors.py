class ServiceError(Exception):
    """Raised by services; translated to an HTTP error response in app.main."""

    status_code = 400

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class BadRequest(ServiceError):
    status_code = 400


class Forbidden(ServiceError):
    status_code = 403


class NotFound(ServiceError):
    status_code = 404


class Conflict(ServiceError):
    status_code = 409


class Unavailable(ServiceError):
    """Something we depend on (e.g. the voice service) didn't answer; try again later."""

    status_code = 503
