import os
import numpy as np
import torch
from itertools import groupby
from datasets import load_dataset 
from PIL import Image, ImageDraw, ImageFont
from transformers import LayoutLMv2Processor
from model_setup import setup
from loguru import logger
from collections import defaultdict
import pickle

setup()
font = ImageFont.load_default()

# loads the imagein PIL format
def load_image(path):
    try:
        image = Image.open(path)
        logger.debug(f"Image loaded: {path} && {type(image)}")
        image = image.convert("RGB")
        return image
    except FileNotFoundError:
        logger.error("File not found")
        return []
    except Exception as e:
        logger.error(f"Error loading image: {e}")
        return []
    
def normalize_box(bbox, width, height):
    return [
        int((bbox[0] * 1000) / width),
        int((bbox[1] * 1000) / height),
        int((bbox[2] * 1000) / width),
        int((bbox[3] * 1000) / height),
    ]

# unnormlizes the bounding boxes to the original image size
def unnormalize_box(bbox, width, height): 
    return [
        int(width * (bbox[0] / 1000)),
        int(height * (bbox[1] / 1000)),
        int(width * (bbox[2] / 1000)),
        int(height * (bbox[3] / 1000)),
    ]

# perform forward pass and return the predictions
def old_extract(model, processor, images, ocr, label2id):
    id2label = {v:k for k,v in label2id.items()}
    words = [row[4] for row in ocr]
    width, height = images.size
    boxes = [normalize_box([row[0], row[1], row[0]+row[2], row[1]+row[3]], width, height) for row in ocr]
    logger.debug(f"Size of words and bboxes: {len(words)} && {len(boxes)}")
    encoded_inputs = processor(images, words, boxes=boxes, truncation=True, stride =0, 
         padding="max_length", max_length=512, return_overflowing_tokens=True, return_offsets_mapping=True)

    offset_mapping = encoded_inputs.pop('offset_mapping')
    overflow_to_sample_mapping = encoded_inputs.pop('overflow_to_sample_mapping')

    logger.debug(encoded_inputs.keys())
    offset_mapping = encoded_inputs.pop('offset_mapping')

    for k,v in encoded_inputs.items():
        encoded_inputs[k] = v.to("cpu")

    # forward pass
    outputs = model(**encoded_inputs)

    is_subword = np.array(offset_mapping.squeeze().tolist())[:,0] != 0
    predictions = outputs.logits.argmax(-1).squeeze().tolist()
    token_boxes = encoded_inputs.bbox.squeeze().tolist()

    pred_labels = [id2label[pred] for idx, pred in enumerate(predictions) if not is_subword[idx]]
    gt_bboxes = [unnormalize_box(box, width, height) for idx, box in enumerate(token_boxes) if not is_subword[idx]]

    gt_bboxes = gt_bboxes[1:-1] # remove CLS and SEP bbox tokens
    pred_labels = pred_labels[1:-1] # remove CLS and SEP tokens

    preds = []
    l_words = []
    bboxes = []
    ids = []
    logger.debug(f"pred_labels: {len(pred_labels)} && words: {len(words)} && gt_bboxes: {len(gt_bboxes)}")
    for i in range(min(len(pred_labels), len(words))):
        if pred_labels[i] != 'O':
            ids.append(i)
            preds.append(pred_labels[i])
            l_words.append(words[i])
            bboxes.append(gt_bboxes[i])

    return ids, bboxes, preds, l_words

def iob_to_label(label):
    label = label[2:]
    if not label:
        return 'other'
    return label

def visualize_image(final_bbox, final_preds, l_words, image):
    draw = ImageDraw.Draw(image)

    label2color = {'question':'blue', 'answer':'green', 'header':'orange', 'other':'violet'}
    l2l = {'question':'key', 'answer':'value', 'header':'title'}
    f_labels = {'question':'key', 'answer':'value', 'header':'title', 'other':'others'}

    json_df = []

    for ix, (prediction, box) in enumerate(zip(final_preds, final_bbox)):
        predicted_label = iob_to_label(prediction).lower()
        draw.rectangle(box, outline=label2color[predicted_label])
        draw.text((box[0] + 10, box[1] - 10), text=f_labels[predicted_label], fill=label2color[predicted_label], font=font)

        json_dict = {}
        json_dict['TEXT'] = l_words[ix]
        json_dict['LABEL'] = f_labels[predicted_label]
        
        json_df.append(json_dict)

    return image, json_df

def process_form(json_df):
    labels = [x['LABEL'] for x in json_df]
    texts = [x['TEXT'] for x in json_df]
    cmb_list = []
    for i, j in enumerate(labels):
        cmb_list.append([labels[i], texts[i]])
        
    grouper = lambda l: [[k] + sum((v[1::] for v in vs), []) for k, vs in groupby(l, lambda x: x[0])]
    
    list_final = grouper(cmb_list)
    lst_final = []
    for x in list_final:
        json_dict = {}
        json_dict[x[0]] = (' ').join(x[1:])
        lst_final.append(json_dict)
    
    return lst_final

def load_model(model_info):
    processor = LayoutLMv2Processor.from_pretrained("microsoft/layoutlmv2-base-uncased", revision="no_ocr")
    if os.path.exists(os.path.join("trained",model_info.path,"model.pth")):
        try:
            model = torch.load(os.path.join("trained",model_info.path,"model.pth"),map_location=torch.device('cpu')).to('cpu')
        except Exception as e:
            logger.error(e)
            model = torch.load('/tmp/model.pth',map_location=torch.device('cpu')).to('cpu')
    else:
        model = torch.load('/tmp/model.pth',map_location=torch.device('cpu')).to('cpu')
    model.to('cpu')
    return model, processor

def postprocess_predictions(idxs, bboxes, labels, texts, label2id):
    id2label = {v:k for k,v in label2id.items()}
    annotation = {}
    for i, (idx, label, box, text) in enumerate(zip(idxs, labels, bboxes, texts)):
        predicted_label = iob_to_label(label.lower())#id2label[label].lower()
        if (predicted_label != "other") or (predicted_label != "o"):
            if predicted_label not in annotation:
                annotation[predicted_label] = []
            annotation[predicted_label].append({"id":idx, "box":box, "text":text})
    return annotation

def old_predict(model_info, image_path, ocr):
    label2id = model_info.label_dict
    labels = list(label2id.keys())
    id2label = {v:k for k,v in label2id.items()}

    logger.info("Loading model")
    model, processor = load_model(model_info)
    logger.info(f"Loading image from {image_path}")
    image = load_image(image_path)
    if not image:
        logger.error(f"Unable to load image from {image_path}")
        return None, None
    logger.debug(f"Image size: {image.size}")
    logger.info(f"Extracting information from the image with targeted bboxes, labels and texts")
    idxs, bboxes, labels, texts = extract(model, processor, image, ocr, label2id)
    logger.info(f"Postprocessing the predictions")
    result = postprocess_predictions(idxs, bboxes, labels, texts, label2id)
    combined = {}
    for label, values in result.items():
        combined[label] = {
            "text": " ".join([x["text"] for x in values]),
            "box": [min([x["box"][0] for x in values]), min([x["box"][1] for x in values]), max([x["box"][2] for x in values]), max([x["box"][3] for x in values])]
        }
    logger.debug(f"Result: {result}")

    logger.debug(f"Combined: {combined}")
    return result, combined


# perform forward pass and return the predictions
def extract(model, processor, images, ocr, label2id):
    id2label = {v:k for k,v in label2id.items()}
    words = [row[4] for row in ocr]
    width, height = images.size
    boxes = [normalize_box([row[0], row[1], row[0]+row[2], row[1]+row[3]], width, height) for row in ocr]
    logger.debug(f"Size of words and bboxes: {len(words)} && {len(boxes)}")
    encoding = processor(images, words, boxes=boxes, truncation=True, stride =128, 
         padding="max_length", max_length=512, return_overflowing_tokens=True, return_offsets_mapping=True)

    offset_mapping = encoding.pop('offset_mapping')
    overflow_to_sample_mapping = encoding.pop('overflow_to_sample_mapping')
    
    for k,v in encoding.items():
        encoding[k] = torch.tensor(v)

    logger.debug(encoding.keys())

    for k,v in encoding.items():
        logger.debug(f"Encoding {k} shape: {v.shape}")
        # encoding[k] = v.to("cpu")

    with open("input_dict.pkl", "wb") as f:
        pickle.dump(encoding, f)


    # forward pass
    outputs = model(**encoding)
    logits = outputs.logits

    predictions = logits.argmax(-1).squeeze().tolist()
    token_boxes = encoding.bbox.squeeze().tolist()

    if (len(token_boxes) == 512):
        predictions = [predictions]
        token_boxes = [token_boxes]
    result = defaultdict(dict)
    checks = [defaultdict(dict)]*len(token_boxes)
    def unnormalize_bbox(bbox, size):
        return [
            int(bbox[0]* size[0]/1000),
            int(bbox[1]* size[1]/1000),
            int(bbox[2]* size[0]/1000),
            int(bbox[3]* size[1]/1000),
        ]
    for i in range(0, len(token_boxes)):
        for j in range(0, len(token_boxes[i])):
            if int(predictions[i][j])!=0:
                if "token_boxes" not in checks[i][iob_to_label(id2label[int(predictions[i][j])])].keys():
                    checks[i][iob_to_label(id2label[int(predictions[i][j])])]["token_boxes"] = []
                    checks[i][iob_to_label(id2label[int(predictions[i][j])])]["input_ids"] = []

                checks[i][iob_to_label(id2label[int(predictions[i][j])])]["token_boxes"].append(unnormalize_bbox(token_boxes[i][j], images.size))
                checks[i][iob_to_label(id2label[int(predictions[i][j])])]["input_ids"].append(encoding["input_ids"][i][j])

    for i in range(len(token_boxes)):
        for k, v in checks[i].items():
            checks[i][k]["input_ids"] = [int(inp_id) for inp_id in checks[i][k]["input_ids"]]
    postprocess_result = postprocess_data(ocr, checks)
    combined ={}
    for label,value in postprocess_result.items():
        combined["text"] = " ".join([x for x in value["text"]])
        combined["bbox"] = ([min([x[0] for x in value["bbox"]]),min([x[1] for x in value["bbox"]]),max([x[2] for x in value["bbox"]]),max([x[3] for x in value["bbox"]])], images.size)

    return postprocess_result, combined


def predict(model_info, image_path, ocr):
    label2id = model_info.label_dict
    labels = list(label2id.keys())
    id2label = {v:k for k,v in label2id.items()}

    logger.info("Loading model")
    model, processor = load_model(model_info)
    logger.info(f"Loading image from {image_path}")
    image = load_image(image_path)
    if not image:
        logger.error(f"Unable to load image from {image_path}")
        return None, None
    logger.debug(f"Image size: {image.size}")
    logger.info(f"Extracting information from the image with targeted bboxes, labels and texts")
    return extract(model, processor, image, ocr, label2id)

def iou(ocr, result):
    xA = max(ocr[0], result[0])
    yA = max(ocr[1], result[1])
    xB = min(ocr[0] + ocr[2], result[2])
    yB = min(ocr[1] + ocr[3], result[3])

    if xB < xA or yB < yA:
        return 0
    interArea = max(0, xB - xA) * max(0, yB - yA)
    boxAArea = ocr[2] * ocr[3]
    boxBArea = (result[2] - result[0]) * (result[3] -result[1])
    iou = interArea / float(boxAArea + boxBArea - interArea+0.0005)
    return iou
    

def postprocess_data(ocr, result):
    postprocess_result = defaultdict(dict)
    for row in ocr:
        for i in range(len(result)):
            for label, values in result[i].items():
                for word in result[i][label]["token_boxes"]:
                    if iou(row[:4], word) > 0.2:
                        if "ids" not in postprocess_result[label]:
                            postprocess_result[label]["ids"] = []
                            postprocess_result[label]["bbox"] = []
                            postprocess_result[label]["text"] = []
                        
                        if row[5] not in postprocess_result[label]["ids"]:
                            postprocess_result[label]["ids"].append(row[5])
                            postprocess_result[label]["bbox"].append([row[0], row[1], row[0]+row[2], row[1]+row[3]])
                            postprocess_result[label]["text"].append(row[4])

    return postprocess_result


