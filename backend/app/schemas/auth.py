from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    registration_code: str
    email: str
    password: str = Field(min_length=8, max_length=32)
    username: str = Field(min_length=3, max_length=20)
    real_name: str = ""
    student_id: str = ""
    major: str = ""
    grade: str = ""
    guidance_level: str = "L2"
    captcha_token: str
    captcha_code: str


class LoginRequest(BaseModel):
    email: str
    password: str
    captcha_token: str
    captcha_code: str
