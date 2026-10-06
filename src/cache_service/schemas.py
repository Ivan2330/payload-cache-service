"""Request and response models.

Validation lives here rather than in the handlers: a malformed request is
rejected before it reaches any business logic, and the generated OpenAPI
document tells a client exactly what is expected.
"""

from pydantic import BaseModel, Field, model_validator


class PayloadRequest(BaseModel):
    list_1: list[str] = Field(..., min_length=1, description="First list of strings")
    list_2: list[str] = Field(..., min_length=1, description="Second list of strings")

    @model_validator(mode="after")
    def lists_must_match(self) -> "PayloadRequest":
        if len(self.list_1) != len(self.list_2):
            raise ValueError(
                f"list_1 and list_2 must be the same length "
                f"({len(self.list_1)} != {len(self.list_2)})"
            )
        return self


class PayloadCreated(BaseModel):
    id: str = Field(..., description="Identifier of the generated payload")
    created: bool = Field(..., description="False when this payload already existed")
    message: str


class PayloadResponse(BaseModel):
    output: str
