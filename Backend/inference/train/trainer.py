import os
import torch
import random
import numpy as np
from loguru import logger
from transformers import LayoutLMv2ForTokenClassification, AdamW
from seqeval.metrics import accuracy_score,precision_score,f1_score, recall_score ,classification_report


def validate_model(model, data_loader, id2label, generate_report=False, desc="Validating"):
    logger.info('Predicting labels for {:,} batches...'.format(len(data_loader)))
    # Put the model in evaluation mode--the dropout layers behave differently
    # during evaluation.
    model.eval()
    # Tracking variables 
    eval_loss, eval_accuracy = 0, 0
    y_true_list = []
    y_pred_list = []
    # Evaluate data for one epoch
    for batch in data_loader:
        # Add batch to GPU
        # batch = {k: v.to(device) for k, v in batch.items()}
        # Telling the model not to compute or store gradients, saving memory and
        # speeding up validation
        with torch.no_grad():        
            # Forward pass, calculate logit predictions.
            # token_type_ids is the same as the "segment ids", which 
            # differentiates sentence 1 and 2 in 2-sentence tasks.
            result = model(**batch)

            # Get the loss and "logits" output by the model. The "logits" are the 
            # output values prior to applying an activation function like the 
            # softmax.
            logits = result.logits
            loss = result.loss
            predictions = torch.argmax(logits, dim=2)
        
        # Accumulate the validation loss.
        eval_loss += loss.item()
        y_true_list.extend(batch["labels"]) 
        y_pred_list.extend(predictions)
        
    label_ids = torch.stack(y_true_list).cpu()
    prediction_ids = torch.stack(y_pred_list).cpu()
    predicted_labels = [
            [id2label[p.item()] for (p, l) in zip(prediction, label) if l != -100]
            for prediction, label in zip(prediction_ids, label_ids)
        ]
    true_labels = [
        [id2label[l.item()] for (p, l) in zip(prediction, label) if l != -100]
        for prediction, label in zip(prediction_ids, label_ids)
    ] 
    
    results = {
        'accuracy': accuracy_score(predicted_labels,true_labels),
        'precision': precision_score(true_labels,predicted_labels),
        'recall': recall_score(true_labels,predicted_labels),
        'f1-score': f1_score(true_labels,predicted_labels),
    }
    average_eval_loss = eval_loss / len(data_loader)
    metrics = None
    if generate_report:
        try:
            metrics = classification_report(true_labels, predicted_labels, output_dict=True)
        except Exception as e:
            logger.error(f"Error generating model metrics: {e}")
            raise e
    return average_eval_loss,results, metrics
    

def trainer(model_info, train_dataloader, test_dataloader):
    seed_val = 42
    random.seed(seed_val)
    np.random.seed(seed_val)
    torch.manual_seed(seed_val)
    torch.cuda.manual_seed_all(seed_val)
    id2label = {v: k for k, v in model_info.label_dict.items()}
    logger.info("Loading model huggingface hub")
    model = LayoutLMv2ForTokenClassification.from_pretrained('microsoft/layoutlmv2-base-uncased',
                                                            num_labels=len(model_info.label_dict))

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model.to(device)
    optimizer = AdamW(model.parameters(), lr=1e-4)

    num_train_epochs = model_info.epochs
    eval_loss, eval_accuracy = 0, 0
    metrics = {}

    # Magic
    # wandb.watch(model, log_freq=10)

    loss_values =[]
    #put the model in training mode
    logger.debug('Training started...')
    for epoch in range(num_train_epochs):
        logger.debug('======== Epoch {:} / {:} ========'.format(epoch + 1, num_train_epochs))
        model.train() 
        # Reset the total loss for this epoch.
        train_loss, train_accuracy,train_f1,train_precision = 0, 0 ,0,0
        for step,batch in enumerate(train_dataloader):
            # zero the parameter gradients
            optimizer.zero_grad()
            # forward + backward + optimize
            outputs = model(**batch) 
            logits = outputs.logits
            loss = outputs.loss
            prediction_ids = torch.argmax(logits,dim =-1).cpu().numpy()
            train_loss += loss.item()
            # Move logits and labels to CPU
            logits = logits.detach().cpu().numpy()
            label_ids = batch['labels'].cpu().numpy()
            predicted_labels = [
                [id2label[p.item()] for (p, l) in zip(prediction, label) if l != -100]
                for prediction, label in zip(prediction_ids, label_ids)
            ]
            true_labels = [
                [id2label[l.item()] for (p, l) in zip(prediction, label) if l != -100]
                for prediction, label in zip(prediction_ids, label_ids)
            ]
            #accumulate precision
            train_precision+= precision_score(true_labels,predicted_labels)
            #accumulate f1
            train_f1+= f1_score(true_labels,predicted_labels)
            # Accumulate the total accuracy.
            train_accuracy += accuracy_score(predicted_labels,true_labels)

            # Progress update every 10 batches.
            if step % 10 == 0:
                logger.debug(f"Step: {step} ===> Training batch loss: {loss}")
            loss.backward()

            # Clip the norm of the gradients to 1.0.
            # This is to help prevent the "exploding gradients" problem.
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
        # Report the final accuracy for this train run.
        avg_train_accuracy = train_accuracy / len(train_dataloader)
        logger.debug(f"Average Training Accuracy: {avg_train_accuracy}")

        # Report the final F1 for this train run.
        avg_train_f1 = train_f1 / len(train_dataloader)
        logger.debug("  Average Training f1: {0:.2f}".format(avg_train_f1))
        
        # Report the final precision for this train run.
        avg_train_precision = train_precision / len(train_dataloader)
        logger.debug("  Average Training Precision: {0:.2f}".format(avg_train_precision))

        # Calculate the average loss over the training data.
        avg_train_loss = train_loss / len(train_dataloader)            
        logger.debug("  Average Training Loss: {0:.2f}".format(avg_train_loss))
            
        # Store the loss value for plotting the learning curve.
        loss_values.append(avg_train_loss)
        logger.debug("Model Validation for epoch: {}".format(epoch))
        eval_loss, results, _= validate_model(model, test_dataloader, id2label, desc="Validating")

        logger.debug("  Average Validation Loss: {0:.2f}".format(eval_loss))
        metrics = results
        for key, value in results.items():
            logger.debug("  {}: {:.2f}".format(key,value))
        model_info.metrics = metrics
        model_info.trained_epochs = epoch+1
        model_info.save()
        
    logger.debug(f"Training complete for model: {model_info._id}")

    model_info.accuracy = metrics
    try:
        _, _, metrics = validate_model(model, test_dataloader, id2label, desc="Validating", generate_report=True)
        model_info.metrics = metrics
    except Exception as e:
        model_info.metrics = {}
        logger.error(f"Error generating model metrics: {e}")
    try:
        model_info.save()
    except Exception as e:
        logger.error(f"Error saving model information in database: {e}")
        model_info.metrics = {}
        model_info.save()
    logger.debug(f"Model Accuracy: {model_info.accuracy}")
    logger.debug(f"Model Metrics: {model_info.metrics}")
    os.makedirs(f"trained/{model_info.path}", exist_ok=True)
    try:
        logger.info(f"Saving model bin on disk: trained/{model_info.path}/model.pth")
        torch.save(model, f"trained/{model_info.path}/model.pth")
    except Exception as e:
        logger.error(f"Error saving model: {e}")
        model_info.status = "failed"
        model_info.accuracy = {}
        model_info.save()
    del model

