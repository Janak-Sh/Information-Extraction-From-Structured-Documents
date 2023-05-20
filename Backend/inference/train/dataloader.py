from models.database.file_db import AnnotationFiles
from transformers import LayoutLMv2Processor
from datasets import Dataset, Features, Sequence, ClassLabel, Value, Array2D, Array3D
from torch.utils.data import DataLoader
from loguru import logger
from time import time
from PIL import Image

def normalize_box(bbox, width, height):
    return [
        min(max(int((bbox[0] * 1000) / width),0), 1000),
        min(max(int((bbox[1] * 1000) / height),0), 1000),
        min(max(int((bbox[2] * 1000) / width),0), 1000),
        min(max(int((bbox[3] * 1000) / height),0), 1000),
    ]

def generate_dataset(document_ids, model_info):
    logger.info(f"Starting dataset generation")
    for idx, doc_id in enumerate(document_ids):
        try:
            logger.debug(f"Fetching data for annotation file: {doc_id}")
            file = AnnotationFiles.objects(_id=document_ids[idx]).first()
            logger.debug(f"Yes, i have Fetched the data for annotation file: {doc_id}: file: {file._id}-{file.width}-{file.height}")
            annotation_map = {word: model_info.label_dict[f"B-{row['name'].upper()}"] if i==0 else model_info.label_dict[f"I-{row['name'].upper()}"] for row in file.annotation for i,word in enumerate(row["word_ids"])}
            logger.debug(annotation_map)
            data = {"id":[], "words":[], "bboxes": [], "ner_tags": [], "image_path": ""}
            logger.debug(f"Formatting annotation for document {doc_id}")
            for row in file.ocr:
                if row[4].strip()=="": continue
                data["id"].append(row[5])
                data["words"].append(row[4])
                if (annotation_map.get(row[5],0)!=0):
                    data["ner_tags"].append(annotation_map[row[5]])
                else:
                    data["ner_tags"].append(0)
                data["bboxes"].append(normalize_box([row[0],row[1], row[0]+row[2], row[1]+row[3]], file.width, file.height))
            logger.info(f"Document {doc_id} has {len(data['id'])} ids and {len(data['ner_tags'])} tags and {len(data['bboxes'])} bboxes and {len(data['words'])} words")
        except Exception as e:
            logger.error(f"Error in processing document {doc_id} with error: {e}")
            continue

        yield {"id": data["id"], "words": data["words"], "bboxes": data["bboxes"], "ner_tags": data["ner_tags"], "image_path": file.path}



def preprocess_data(examples):
    processor = LayoutLMv2Processor.from_pretrained("microsoft/layoutlmv2-base-uncased", revision="no_ocr")
    images = [Image.open(path).convert("RGB") for path in examples['image_path']]
    words = examples['words']
    boxes = examples['bboxes']
    word_labels = examples['ner_tags']

    encoded_inputs = processor(images, words, boxes=boxes, word_labels=word_labels,
                             truncation=True, stride =0, padding="max_length", 
                             max_length=512, return_overflowing_tokens=True, return_offsets_mapping=True)
    offset_mapping = encoded_inputs.pop('offset_mapping')

    overflow_to_sample_mapping = encoded_inputs.pop('overflow_to_sample_mapping')
    return encoded_inputs

def get_features(model_info):
    labels = list(model_info.label_dict.keys())
    return Features({
        'image': Array3D(dtype="int64", shape=(3, 224, 224)),
        'input_ids': Sequence(feature=Value(dtype='int64')),
        'attention_mask': Sequence(Value(dtype='int64')),
        'token_type_ids': Sequence(Value(dtype='int64')),
        'bbox': Array2D(dtype="int64", shape=(512, 4)),
        'labels': Sequence(ClassLabel(names=labels)),
    })

def create_dataloader(document_ids, model_info):
    train_size = int(len(document_ids) * model_info.train_split)
    logger.debug(f"Total documents found: {len(document_ids)} and train split: {model_info.train_split}")
    batch_size = model_info.batch
    features = get_features(model_info)
    try:
        start = time()
        logger.info(f"Creating train dataset from generator for size of {len(document_ids[:train_size])}")
        train_ds = Dataset.from_generator(generate_dataset, gen_kwargs={"document_ids": document_ids[:train_size], "model_info": model_info})
        end = time()
        logger.info(f"Time taken for train dataset creation: {end-start}")
    except Exception as e:
        
        logger.debug("Inside the function",e)
        raise e
    
    try:
        start = time()
        logger.info("Mapping train dataset to features")
        train_ds = train_ds.map(preprocess_data, batched=True, remove_columns=train_ds.column_names,
                                features=features)
        end = time()
        logger.info(f"Time taken for train dataset creation: {end-start}")
    except Exception as e:
        raise e
    
    try:
        start = time()
        logger.info(f"Creating test dataset from generator for size of {len(document_ids[train_size:])}")
        test_ds = Dataset.from_generator(generate_dataset, gen_kwargs={"document_ids": document_ids[train_size:], "model_info": model_info})
        end = time()
        logger.info(f"Time taken for test dataset mapping: {end-start}")
    except Exception as e:
        raise e
    try:
        start = time()
        logger.info("Mapping test dataset to features")
        test_ds = test_ds.map(preprocess_data, batched=True, remove_columns=test_ds.column_names,
                                features=features)
        end = time()
        logger.info(f"Time taken for test dataset mapping: {end-start}")
    except Exception as e:
        raise e
    
    train_ds.set_format(type="torch")
    test_ds.set_format(type="torch")

    try:
        logger.info("Creating train dataloader")
        train_dataloader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    except Exception as e:
        raise e
    try:
        logger.info("Creating test dataloader")
        test_dataloader = DataLoader(test_ds, batch_size=batch_size)
    except Exception as e:
        raise e
    return train_dataloader, test_dataloader
