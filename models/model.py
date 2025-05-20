import json
import torch
import os
from tqdm import tqdm
from transformers import RobertaConfig, RobertaModel, AutoTokenizer, Trainer
import torch.nn as nn
from transformers import PreTrainedModel, AutoModel
from torch.nn import BCEWithLogitsLoss, CrossEntropyLoss, MSELoss
from transformers.modeling_outputs import SequenceClassifierOutput
from dotenv import load_dotenv
import os

load_dotenv()
hf_token = os.getenv("hf_token")

class CustomCodeClassifier(nn.Module):
    def __init__(self, encoder_model, config):
        super().__init__()
        self.num_labels = config.num_labels
        self.config = config

        self.unixcoder = encoder_model

        hidden_size = config.hidden_size
        self.classifier = nn.Sequential(
            nn.Linear(hidden_size, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(512, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, config.num_labels)
        )

    def forward(
        self,
        input_ids=None,
        attention_mask=None,
        token_type_ids=None,
        position_ids=None,
        head_mask=None,
        inputs_embeds=None,
        labels=None,
        output_attentions=None,
        output_hidden_states=None,
        return_dict=None,
    ):
        return_dict = return_dict if return_dict is not None else self.config.use_return_dict

        outputs = self.unixcoder(
            input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
            position_ids=position_ids,
            head_mask=head_mask,
            inputs_embeds=inputs_embeds,
            output_attentions=output_attentions,
            output_hidden_states=output_hidden_states,
            return_dict=return_dict,
        )

        pooled_output = outputs[1] if not return_dict else outputs.pooler_output
        logits = self.classifier(pooled_output)

        loss = None
        if labels is not None:
            if self.num_labels == 1:
                loss_fct = MSELoss()
                loss = loss_fct(logits.squeeze(), labels.squeeze())
            elif labels.dim() == 1:
                loss_fct = CrossEntropyLoss()
                loss = loss_fct(logits.view(-1, self.num_labels), labels.view(-1))
            else:
                loss_fct = BCEWithLogitsLoss()
                loss = loss_fct(logits, labels.float())

        if not return_dict:
            output = (logits,) + outputs[2:]
            return ((loss,) + output) if loss is not None else output

        return SequenceClassifierOutput(
            loss=loss,
            logits=logits,
            hidden_states=outputs.hidden_states if output_hidden_states else None,
            attentions=outputs.attentions if output_attentions else None
        )
    

class WeightedLossTrainer(Trainer):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.class_weights = torch.tensor([1.0, 1.0])

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        if "labels" in inputs:
            labels = inputs["labels"].detach().clone()
        else:
            labels = None

        outputs = model(**inputs)

        if not isinstance(outputs, dict):
            if isinstance(outputs, tuple):
                if len(outputs) > 0:
                    logits = outputs[0]
                    outputs = {"logits": logits}
                else:
                    outputs = {"logits": None}
            else:
                outputs = {"logits": outputs}

        logits = outputs.get("logits")

        if logits is None and labels is not None:
            if labels.dim() == 1:
                logits = torch.zeros((labels.size(0), 2), device=labels.device)


        loss = None
        if labels is not None and logits is not None:
            weights = self.class_weights.to(logits.device)
            loss_fct = nn.CrossEntropyLoss(weight=weights)
            loss = loss_fct(logits.view(-1, 2), labels.view(-1))  

        return (loss, outputs) if return_outputs else loss

    def prediction_step(self, model, inputs, prediction_loss_only, ignore_keys=None):


        loss, logits, labels = super().prediction_step(
            model, inputs, prediction_loss_only, ignore_keys=ignore_keys
        )
        if logits is None and labels is not None:
            batch_size = labels.size(0)
            num_labels = 2
            logits = torch.zeros((batch_size, num_labels), device=labels.device)

        return loss, logits, labels
    
class CodeClassifier:
    def __init__(self, checkpoint_dir, model_pt_path=None):
        self.tokenizer = AutoTokenizer.from_pretrained(checkpoint_dir, use_fast=True)
        
        self.config = RobertaConfig.from_pretrained("microsoft/unixcoder-base")
        self.config.num_labels = 2
        
        print("Đang tạo UnixCoder encoder model...")
        encoder_model = RobertaModel.from_pretrained(
            "microsoft/unixcoder-base",
            config=self.config,
            add_pooling_layer=True,
            revision="main",
            cache_dir="/tmp/unixcoder_cache",
        )
        
        self.model = CustomCodeClassifier(encoder_model, self.config)

        self._load_model_weights(checkpoint_dir, model_pt_path)

        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model.to(self.device)
        self.model.eval()
        print(f"Model {self.device}")
    
    def _load_model_weights(self, checkpoint_dir, model_pt_path):
        if model_pt_path and os.path.exists(model_pt_path):
            print(f"Đang tải model từ {model_pt_path}")
            try:
                checkpoint = torch.load(model_pt_path, map_location="cpu")
                if 'model_state_dict' in checkpoint:
                    self.model.load_state_dict(checkpoint['model_state_dict'])
                else:
                    self.model.load_state_dict(checkpoint)
            except Exception as e:
                print(f"Download pt model{model_pt_path}: {str(e)}")
                bin_path = os.path.join(checkpoint_dir, "pytorch_model.bin")
                if os.path.exists(bin_path):
                    state_dict = torch.load(bin_path, map_location="cpu")
                    self.model.load_state_dict(state_dict)
        else:
            bin_path = os.path.join(checkpoint_dir, "pytorch_model.bin")
            if os.path.exists(bin_path):
                print(f"Đang tải model từ {bin_path}")
                state_dict = torch.load(bin_path, map_location="cpu")
                self.model.load_state_dict(state_dict)
            else:
                print(f"Cannot find model weights")
    
    def predict_text(self, text):
        if not text:
            return 0, None

        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)

        logits = outputs.logits if hasattr(outputs, 'logits') else outputs
        if isinstance(logits, torch.Tensor):
            if len(logits.shape) == 2:
                pred_class = torch.argmax(logits, dim=1).item()
            else:
                pred_class = torch.argmax(logits).item()
        else:
            pred_class = 0  

        return pred_class, logits