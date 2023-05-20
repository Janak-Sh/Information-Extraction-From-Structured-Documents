from inference.train.trainer import trainer
from inference.train.dataloader import create_dataloader
from loguru import logger 

def train(model_info, document_ids):
    logger.info("Starting preparation of training")
    try:
        train_dataloader, test_dataloader = create_dataloader(document_ids, model_info)
    except Exception as e:
        logger.error("Error in creating dataloader")
        logger.error(e)
        return None
    try:
        trainer(model_info, train_dataloader, test_dataloader)
        del train_dataloader
        del test_dataloader
    except Exception as e:
        logger.error("Error in training model")
        logger.error(e)