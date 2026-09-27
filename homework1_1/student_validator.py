from pydantic import BaseModel, EmailStr, Field

class StudentValidator(BaseModel):
    nume: str = Field(min_length=2, max_length=30) #nume cuprins intre 2 caractere si 50 de caractere
    varsta: int = Field(gt=0) # varsta trebuie sa fie numar intreg mai mare ca 0
    email: EmailStr
