from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    shop_ids: list[int] = []
    permissions: list[str] = []

    class Config:
        from_attributes = True
