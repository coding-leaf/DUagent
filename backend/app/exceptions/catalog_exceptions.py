from fastapi import status
from app.exceptions.base import DomainException

class CatalogNotFoundError(DomainException):
    def __init__(self):
        super().__init__(
            message="课程资源库不存在",
            code=40400,
            status_code=status.HTTP_404_NOT_FOUND
        )
