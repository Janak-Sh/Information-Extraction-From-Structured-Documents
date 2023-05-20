import os
from dotenv import load_dotenv
from loguru import logger
import gdown

def setup():
    load_dotenv()
    if(not os.path.isdir('/tmp')):
        os.mkdir('/tmp')

    if(not os.path.isfile('/tmp/model.pth')):
        logger.debug(f"Downloading model: {os.environ.get('MODEL_ID')}")
        gdown.download(id=os.environ.get("MODEL_ID"),output="/tmp/model.pth",quiet=False)
