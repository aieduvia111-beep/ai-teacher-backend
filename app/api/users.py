from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/me")
def get_me():
    return {"message": "Profil użytkownika - wkrótce!"}