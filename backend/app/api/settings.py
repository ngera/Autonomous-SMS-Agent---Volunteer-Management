from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import select

from app.core.dependencies import CurrentTenant, CurrentUser, DbSession, OwnerUser
from app.models.system_setting import SystemSetting
from app.prompts.conversation import PROMPT_KEYS
from app.prompts.screener import SCREENER_SYSTEM_PROMPT
from app.schemas.settings import SystemSettingResponse, SystemSettingsUpdate

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


@router.get("", response_model=list[SystemSettingResponse])
async def get_settings(db: DbSession, current_user: CurrentUser, tenant: CurrentTenant):
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.tenant_id == tenant.id).order_by(SystemSetting.key)
    )
    return result.scalars().all()


@router.get("/prompts")
async def get_prompts(db: DbSession, current_user: OwnerUser, tenant: CurrentTenant):
    """Return all prompt keys with both the effective value and the factory default.

    The admin UI uses ``default_value`` to power the "Reset to Default" button
    (so it actually resets to the latest shipped default, not the last-loaded
    value) and to show a "Modified" indicator when the saved override has
    drifted from the code default.
    """
    defaults = {**PROMPT_KEYS}
    defaults["prompt_screener_system"] = SCREENER_SYSTEM_PROMPT

    result = await db.execute(
        select(SystemSetting).where(
            SystemSetting.tenant_id == tenant.id,
            SystemSetting.key.in_(defaults.keys()),
        )
    )
    overrides = {s.key: s.value for s in result.scalars().all()}

    return [
        {
            "key": key,
            "value": overrides.get(key, default),
            "default_value": default,
            "is_default": key not in overrides,
        }
        for key, default in defaults.items()
    ]


@router.put("")
async def update_settings(
    body: SystemSettingsUpdate, db: DbSession, current_user: OwnerUser, tenant: CurrentTenant
):
    now = datetime.now(timezone.utc)
    for key, value in body.settings.items():
        result = await db.execute(
            select(SystemSetting).where(
                SystemSetting.tenant_id == tenant.id,
                SystemSetting.key == key,
            )
        )
        setting = result.scalar_one_or_none()

        if setting:
            setting.value = value
            setting.updated_at = now
            setting.updated_by_admin_id = current_user.id
        else:
            setting = SystemSetting(
                tenant_id=tenant.id,
                key=key,
                value=value,
                updated_by_admin_id=current_user.id,
            )
            db.add(setting)

    await db.flush()
    return {"message": "Settings updated"}
