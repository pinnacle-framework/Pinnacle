from backend.ai.artifacts import load_ai_artifacts
from backend.ai.components import install_ai_components
from backend.config import settings
from backend.documents.routes import documents_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient

from pinnacledb import pinnacle

origins = [
    'https://staging.djjaum0vi81ax.amplifyapp.com/',
    'https://www.qtd.pinnacledb.com/',
]


def create_app() -> FastAPI:
    app = FastAPI(title='Question the Docs')

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )

    @app.on_event('startup')
    def startup_db_client():
        app.mongodb_client = MongoClient(settings.mongo_uri)
        app.mongodb = app.mongodb_client[settings.mongo_db_name]

        # We wrap our MongoDB to make it a SuperDuperDB!
        app.pinnacledb = pinnacle(app.mongodb)

        # An Artifact is information that has been pre-processed
        # for use with AI models.
        load_ai_artifacts(app.pinnacledb)

        # A Component is an AI Model. Each Component can process
        # one or more types of Artifact.
        install_ai_components(app.pinnacledb)

    @app.on_event('shutdown')
    def shutdown_db_client():
        app.mongodb_client.close()

    app.include_router(documents_router)
    return app
