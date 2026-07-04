from fastapi import APIRouter
from app.services.platform_checker import PLATFORMS, DOMAIN_TLDS

router = APIRouter()


@router.get("")
async def list_platforms():
    """Return all supported platforms + domain TLDs grouped by category."""
    grouped: dict[str, list] = {}
    for p in PLATFORMS:
        cat = p["category"]
        grouped.setdefault(cat, []).append({
            "name": p["name"],
            "icon": p["icon"],
            "category": cat,
        })
    grouped["domain"] = [{"name": tld, "icon": "🌐", "category": "domain"} for tld in DOMAIN_TLDS]

    total = len(PLATFORMS) + len(DOMAIN_TLDS)
    return {
        "total": total,
        "categories": list(grouped.keys()),
        "platforms": grouped,
    }
