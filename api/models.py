from pydantic import BaseModel


class OnboardingChoice(BaseModel):
    report: bool


class UserInput(BaseModel):
    user_id: str
    # add your fields here