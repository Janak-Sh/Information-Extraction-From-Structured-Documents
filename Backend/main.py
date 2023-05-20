import uvicorn
from loguru import logger
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from routes.drive import drive
from routes.user import user_router
from routes.train import train_router
from routes.predict import predict_router
from routes.annotate import annotate_router
from routes.doc_type import doc_type_router
from routes.annotation import annotation_router
from routes.get_documents import get_documents_router

app = FastAPI()

app.include_router(user_router, prefix="/user")
app.include_router(annotation_router, prefix="/annotation")
# app.include_router(drive,prefix="/drive")
app.include_router(predict_router, prefix="/predict")
app.include_router(train_router, prefix="/train")
app.include_router(doc_type_router, prefix="/doc_type")

app.include_router(get_documents_router, prefix="/get_documents")
app.include_router(annotate_router, prefix="/annotate")

app.mount("/", StaticFiles(directory="build", html=True), name="build")

uvicorn.config.LOGGING_CONFIG["formatters"]["default"][
    "fmt"] = "%(asctime)s %(levelprefix)s %(message)s"

origins = ["http://localhost:"+str(i) for i in range(3000, 4500)]
origins.extend(["http://data-extraction.tech"])
origins.extend(["http://127.0.0.1:"+str(i) for i in range(3000, 4500)])
origins.extend(["http://0.0.0.0:"+str(i) for i in range(3000, 4500)])


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    # allow_methods=["GET", "POST", "OPTIONS"],
    # allow_headers=["*"],
    allow_headers=["Content-Type", "Set-Cookie"],
)


if __name__ == "__main__":
    try:
        uvicorn.run("main:app", host="0.0.0.0", port=8000,
                    workers=1, log_config="./log.ini", reload=True)
    except Exception as e:
        logger.error(e)
        logger.error(
            "Port 8000 is occupied use command 'killport 8000' to free the port and try again.")