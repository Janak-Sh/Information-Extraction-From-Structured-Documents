from transformers import LayoutLMv2ForTokenClassification, TrainingArguments, Trainer
from datasets import load_metric
import numpy as np
from loguru import logger

def trainer(model_info, train_dataloader, test_dataloader, test_ds):
    label2id = model_info.label_dict
    logger.info("Loading huggingface model")
    model = LayoutLMv2ForTokenClassification.from_pretrained('microsoft/layoutlmv2-base-uncased',
                                                                      num_labels=len(label2id))

    # Set id2label and label2id 
    id2label = {v:k for k,v in label2id.items()}
    model.config.id2label = id2label
    model.config.label2id = label2id

    # Metrics
    metric = load_metric("seqeval")
    return_entity_level_metrics = True

    def compute_metrics(p):
        predictions, labels = p
        predictions = np.argmax(predictions, axis=2)

        # Remove ignored index (special tokens)
        true_predictions = [
            [id2label[p] for (p, l) in zip(prediction, label) if l != -100]
            for prediction, label in zip(predictions, labels)
        ]
        true_labels = [
            [id2label[l] for (p, l) in zip(prediction, label) if l != -100]
            for prediction, label in zip(predictions, labels)
        ]

        results = metric.compute(predictions=true_predictions, references=true_labels)
        if return_entity_level_metrics:
            # Unpack nested dictionaries
            final_results = {}
            for key, value in results.items():
                if isinstance(value, dict):
                    for n, v in value.items():
                        final_results[f"{key}_{n}"] = v
                else:
                    final_results[key] = value
            return final_results
        else:
            return {
                "precision": results["overall_precision"],
                "recall": results["overall_recall"],
                "f1": results["overall_f1"],
                "accuracy": results["overall_accuracy"],
            }

    class FunsdTrainer(Trainer):
        def get_train_dataloader(self):
            return train_dataloader

        def get_test_dataloader(self):
            return test_dataloader
        
        def get_eval_dataloader(self):
            return test_dataloader

    logger.info("Creating arguments for training")
    args = TrainingArguments(
        output_dir="trained/test",#model_info.path, # name of directory to store the checkpoints
        max_steps=10,
        warmup_ratio=0.1, # we warmup a bit
    )

    logger.info("Creating trainer")
    # Initialize our Trainer
    try:
        trainer = FunsdTrainer(
            model=model,
            args=args,
            compute_metrics=compute_metrics,
        )
    except Exception as e:
        logger.error("Error in creating trainer")
        raise e

    try:
        logger.info("Starting training")
        trainer.train()
    except Exception as e:
        logger.error("Error in training")
        raise e
    try:
        logger.info("Starting evaluation")
        predictions, labels, metrics = trainer.predict(test_ds)
    except Exception as e:
        logger.error("Error in evaluation")
        raise e
    try:
        logger.info("Saving model accuracy")
        model_info.add_accuracy(metrics)
    except Exception as e:
        logger.error("Error in saving model accuracy")
        raise e
    return metrics

