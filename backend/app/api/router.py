from fastapi import APIRouter, Depends

from app.api.deps import require_same_site_mutation
from app.api.routes.account import router as account_router
from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.interviews import router as interviews_router
from app.api.routes.jobs import companies_router, jobs_router, recommendations_router, saved_router
from app.api.routes.passport import router as passport_router
from app.api.routes.resumes import router as resumes_router
from app.api.routes.review import router as review_router
from app.api.routes.social_auth import router as social_auth_router

api_router = APIRouter(dependencies=[Depends(require_same_site_mutation)])
api_router.include_router(health_router, tags=["system"])
api_router.include_router(auth_router, tags=["authentication"])
api_router.include_router(account_router, tags=["account-security"])
api_router.include_router(social_auth_router, tags=["social-authentication"])
api_router.include_router(passport_router, tags=["career-passport"])
api_router.include_router(resumes_router, tags=["resumes"])
api_router.include_router(review_router, tags=["resume-review"])
api_router.include_router(interviews_router, tags=["interviews"])
api_router.include_router(jobs_router, tags=["jobs"])
api_router.include_router(saved_router, tags=["saved-jobs"])
api_router.include_router(companies_router, tags=["companies"])
api_router.include_router(recommendations_router, tags=["recommendations"])
