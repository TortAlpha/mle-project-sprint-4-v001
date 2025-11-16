from fastapi import FastAPI
from contextlib import asynccontextmanager
import service
import controller

@asynccontextmanager
async def lifespan(app: FastAPI):
    service.load_data()
    yield

app = FastAPI(
    title="Music Recommendations API",
    lifespan=lifespan
)

app.include_router(controller.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)