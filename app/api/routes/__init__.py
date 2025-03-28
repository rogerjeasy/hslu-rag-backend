from app.api.routes.auth import router as auth_router
from app.api.routes.courses import router as courses_router
from app.api.routes.queries import router as queries_router
from app.api.routes.materials import router as materials_router
from app.api.routes.study_guides import router as study_guides_router
from app.api.routes.practice import router as practice_router
from app.api.routes.conversations import router as conversations_router
from app.api.routes.statistics import router as statistics_router
from app.api.routes.maintenance import router as maintenance_router
from app.api.routes.rag import router as rag_router

# Export the routers
auth = auth_router
courses = courses_router
queries = queries_router
materials = materials_router
study_guides = study_guides_router
practice = practice_router
conversations = conversations_router
statistics = statistics_router
maintenance = maintenance_router
rag = rag_router