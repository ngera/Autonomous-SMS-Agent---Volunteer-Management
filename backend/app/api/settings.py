from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import select

from app.core.dependencies import CurrentUser, DbSession, OwnerUser
from app.models.system_setting import SystemSetting
from app.schemas.settings import SystemSettingResponse, SystemSettingsUpdate

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


@router.get("", response_model=list[SystemSettingResponse])
async def get_settings(db: DbSession, current_user: CurrentUser):
    result = await db.execute(
        select(SystemSetting).order_by(SystemSetting.key)
    )
    return result.scalars().all()


@router.put("")
async def update_settings(
    body: SystemSettingsUpdate, db: DbSession, current_user: OwnerUser
):
    now = datetime.now(timezone.utc)
    for key, value in body.settings.items():
        result = await db.execute(
            select(SystemSetting).where(SystemSetting.key == key)
        )
        setting = result.scalar_one_or_none()

        if setting:
            setting.value = value
            setting.updated_at = now
            setting.updated_by_admin_id = current_user.id
        else:
            setting = SystemSetting(
                key=key,
                value=value,
                updated_by_admin_id=current_user.id,
            )
            db.add(setting)

    await db.flush()
    return {"message": "Settings updated"}
