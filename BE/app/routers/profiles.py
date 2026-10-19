from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from BE.app.database import get_db
from BE.app.schemas.profile import (
    ActiveProfileRead,
    ProfileCreate,
    ProfileList,
    ProfileRead,
    ProfileUpdate,
)
from BE.app.services import profiles as service

router = APIRouter(prefix="/v1/profiles", tags=["profiles"])


@router.get("", response_model=ProfileList)
def list_profiles(session: Session = Depends(get_db)):
    items, active_profile_id = service.list_profiles(session)
    return {"items": items, "active_profile_id": active_profile_id}


@router.post("", response_model=ProfileRead, status_code=status.HTTP_201_CREATED)
def create_profile(command: ProfileCreate, session: Session = Depends(get_db)):
    return service.create_profile(session, command)


@router.get("/{profile_id}", response_model=ProfileRead)
def get_profile(profile_id: str, session: Session = Depends(get_db)):
    return service.get_profile(session, profile_id)


@router.patch("/{profile_id}", response_model=ProfileRead)
def update_profile(
    profile_id: str, command: ProfileUpdate, session: Session = Depends(get_db)
):
    return service.update_profile(session, profile_id, command)


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(
    profile_id: str,
    version: int = Query(ge=1),
    confirm: bool = False,
    session: Session = Depends(get_db),
):
    service.delete_profile(session, profile_id, version, confirm)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{profile_id}/active", response_model=ActiveProfileRead)
def set_active_profile(profile_id: str, session: Session = Depends(get_db)):
    return {"active_profile_id": service.set_active_profile(session, profile_id)}
