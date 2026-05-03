from dataclasses import dataclass

from fastapi import HTTPException, Request

from ardhi.db.ardhi import ArdhiRepository
from ardhi.db.ecocrop import EcoCropRepository
from ardhi.db.hwsd import HwsdRepository


@dataclass
class Repositories:
    ardhi: ArdhiRepository
    hwsd: HwsdRepository
    ecocrop: EcoCropRepository


def get_repositories(request: Request) -> Repositories:
    repos = getattr(request.app.state, "repositories", None)
    if repos is None:
        raise HTTPException(status_code=503, detail="Database repositories are not initialized")
    return repos
