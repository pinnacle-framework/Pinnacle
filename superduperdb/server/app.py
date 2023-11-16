import sys
from functools import cached_property

import uvicorn
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from pinnacledb.base.build import build_datalayer
from pinnacledb.base.datalayer import Datalayer
from pinnacledb.base.logger import logger

app = FastAPI()


class SuperDuperApp:
    '''
    This is a wrapper class which helps to create a fastapi application
    in the realm of pinnacledb.

    This class prepares a basic api setup and only endpoint implementation
    are need to be added into the app
    '''

    def __init__(self, service='vector_search', port=8000):
        self.service = service
        self.port = port

        self.app_host = '0.0.0.0'

        self.router = APIRouter(prefix='/' + self.service)
        self._user_startup = False
        self._user_shutdown = False

        @self.router.get('/health')
        def health():
            return {'status': 200}

    @cached_property
    def db(self):
        return app.state.pool

    def add(self, *args, method='post', **kwargs):
        '''
        Register an endpoint with this method.
        '''

        def decorator(function):
            self.router.add_api_route(
                *args, **kwargs, endpoint=function, methods=[method]
            )
            return

        return decorator

    @cached_property
    def app(self):
        app.include_router(self.router)
        return app

    def start(self):
        '''
        This method is used to start the application server
        '''
        if not self._user_startup:
            self.startup()

        if not self._user_shutdown:
            self.shutdown()
        assert self.app
        uvicorn.run(
            app,
            host=self.app_host,
            port=self.port,
            reload=False,
        )

    def startup(self, function=None):
        '''
        This method is used to register a startup function
        '''
        self._user_startup = True

        @app.on_event('startup')
        def startup_db_client():
            sys.path.append('./')
            db = build_datalayer()
            db.server_mode = True
            if function:
                function(db=db)
            app.state.pool = db

        return

    def shutdown(self, function=None):
        '''
        This method is used to register a shutdown function
        '''
        self._user_shutdown = True

        @app.on_event('shutdown')
        def shutdown_db_client():
            try:
                if function:
                    function(db=app.state.pool)
                app.state.pool.close()
            except AttributeError:
                raise Exception('Could not close the database properly')

        return


def database(request: Request) -> Datalayer:
    return request.app.state.pool


def DatalayerDependency():
    '''
    A helper method to be used for injecting datalayer instance
    into endpoint implementation
    '''
    return Depends(database)


# --------------- Create exception handler middleware-----------------


class ExceptionHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as e:
            logger.exception(f'Error while serving {request} :: {e}')
            return JSONResponse(
                status_code=500,
                content={'error': e.__class__.__name__, 'messages': e.args},
            )


app.add_middleware(ExceptionHandlerMiddleware)
