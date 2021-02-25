from torch.nn import CrossEntropyLoss
from transformers.models.bert.modeling_bert import BertModel
from transformers.models.bert.modeling_bert import BertPreTrainedModel
import torch.nn as nn
import torch
import torch.nn.functional as F
from typing import List, Optional
import numpy as np
from models.base_ner_model import NERModel
import torch.optim as optim
from transformers import get_linear_schedule_with_warmup, get_cosine_schedule_with_warmup, get_cosine_with_hard_restarts_schedule_with_warmup
import torchcrf


class BiLSTMNERModel(NERModel):


    def initialize_model(self):
        ner_model = BiLSTM(self.config, self.classes, self.device).to(self.device)
        return ner_model


    def create_optimizer(self, full_finetuning = True):
        optimizer = optim.AdamW(self.model.parameters(), lr=self.lr, eps=1e-8)
        return optimizer


    def create_scheduler(self, optimizer, n_epochs, train_dataloader):
        scheduler = get_cosine_schedule_with_warmup(optimizer,
                                                    num_warmup_steps=len(train_dataloader),
                                                    num_training_steps=n_epochs*len(train_dataloader),
                                                    num_cycles=n_epochs/10)
        # scheduler = get_linear_schedule_with_warmup(optimizer,
        #                                             num_warmup_steps=0,
        #                                             num_training_steps=n_epochs*len(train_dataloader))
        # scheduler = get_cosine_with_hard_restarts_schedule_with_warmup(optimizer,
        #                                                                num_warmup_steps=0,
        #                                                                num_training_steps=n_epochs*len(train_dataloader),
        #                                                                num_cycles=n_epochs/5)
        return scheduler


    def document_embeddings(self, **inputs):
        return self.model.document_embedding(**inputs)


class BiLSTM(nn.Module):
    def __init__(self, config, tag_names, device):
        super().__init__()
        self._device = device
        self.lstm_hidden_size = 64
        self.embedding = nn.Embedding(30522, config.hidden_size)
        self.dropout_b = nn.Dropout(config.hidden_dropout_prob)
        self.lstm = nn.LSTM(batch_first=True, input_size=config.hidden_size,
                            hidden_size=self.lstm_hidden_size, num_layers=4,
                            bidirectional=True, dropout=0.1)
        self.dropout_c = nn.Dropout(0.25)
        self.classifier = nn.Linear(2*self.lstm_hidden_size, config.num_labels)
        self.crf = CRF(tag_names=tag_names, batch_first=True)


    @property
    def device(self):
        return self._device
    

    @device.setter
    def device(self, device):
        self._device = device


    def forward(self, input_ids,
                attention_mask=None, token_type_ids=None,
                position_ids=None, head_mask=None,
                inputs_embeds=None, valid_mask=None,
                labels=None, decode=False):
        sequence_output = self.embedding(input_ids)
        # sequence_output = [outputs[2][i] for i in (-1, -2, -3, -4)]
        # sequence_output = torch.mean(torch.stack(sequence_output), dim=0)
        # sequence_output = outputs[0]
        # print(sequence_output.shape)
        sequence_output, _ = self.lstm(sequence_output)
        sequence_output, attention_mask = valid_sequence_output(input_ids, sequence_output, valid_mask, attention_mask, self.device)
        sequence_output = self.dropout_b(sequence_output)
        logits = self.classifier(sequence_output)     
        if decode:
            # tags = self.crf.decode(logits[:, 1:], mask=attention_mask[:, 1:])
            tags = self.crf.decode(logits, mask=attention_mask)
            outputs = (tags,)
        else:
            outputs = (logits,)
        if labels is not None:
            labels = torch.where(labels >= 0, labels, torch.zeros_like(labels))
            # loss = -self.crf(logits[:, 1:], labels[:, 1:], mask=attention_mask[:, 1:])
            loss = -self.crf(logits, labels, mask=attention_mask)
            outputs = (loss,) + outputs
        return outputs  # loss, scores


    def document_embedding(self, input_ids,
                           attention_mask=None, token_type_ids=None,
                           position_ids=None, head_mask=None,
                           inputs_embeds=None):
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask,
                            token_type_ids=token_type_ids, position_ids=position_ids,
                            head_mask=head_mask, inputs_embeds=inputs_embeds,
                            output_hidden_states=True)
        sequence_output = [outputs[2][i] for i in (-1, -2, -3, -4)]
        sequence_output = torch.mean(torch.mean(torch.stack(sequence_output), dim=0), dim=1)
        return sequence_output


def valid_sequence_output(input_ids, sequence_output, valid_mask, attention_mask, device):
    batch_size, max_len, feat_dim = sequence_output.shape
    valid_output = torch.zeros(batch_size, max_len, feat_dim, dtype=torch.float32, device=device)
    valid_attention_mask = torch.zeros(batch_size, max_len, dtype=torch.bool, device=device)
    for i in range(batch_size):
        jj = -1
        for j in range(max_len):
            if valid_mask[i][j].item() == 1:
                jj += 1
                valid_output[i][jj] = sequence_output[i][j]
                # if input_ids[i][j] not in (2, 3):
                valid_attention_mask[i][jj] = attention_mask[i][j]
    return valid_output, valid_attention_mask


class CRF(nn.Module):
    def __init__(self, tag_names, batch_first):
        super().__init__()
        penalties = False
        # tag names
        self.tag_names = tag_names
        # initialize CRF
        self.crf = torchcrf.CRF(num_tags=len(self.tag_names), batch_first=batch_first)
        # initialize weights
        self.crf.reset_parameters()
        if penalties:
            # construct definitions of invalid transitions
            self.define_invalid_crf_transitions()
            # initialize transitions
            self.init_crf_transitions()
            print(self.tag_names)
            print(self.crf.start_transitions)
            print(self.crf.end_transitions)
            print(self.crf.transitions)
    

    def define_invalid_crf_transitions(self):
        ''' function for establishing valid tagging transitions, assumes BIO or BILUO tagging '''
        self.prefixes = set([tag_name.split('-')[0] for tag_name in self.tag_names])
        if self.prefixes == set(['B', 'I', 'O']):
            # (B)eginning (I)nside (O)utside
            # sentence must begin with [CLS] (O)
            self.invalid_begin = ('B', 'I')
            # sentence must end with [SEP] (O)
            self.invalid_end = ('B', 'I')
            # prevent O (outside) going to I (inside) - O must be followed by B or O
            self.invalid_transitions_position = {'O': 'I'}
            # prevent B (beginning) going to I (inside) of a different type
            # prevent I (inside) going to I (inside) of a different type
            self.invalid_transitions_tags = {'B': 'I',
                                             'I': 'I'}
        if self.prefixes == set(['B', 'I', 'L', 'U', 'O']):
            # (B)eginning (I)nside (L)ast (U)nit (O)utside
            # sentence must begin with [CLS] (O)
            self.invalid_begin = ('B', 'I', 'L', 'U')
            # sentence must end with [SEP] (O)
            self.invalid_end = ('B', 'I', 'L', 'U')
            # prevent B (beginning) going to B (beginning), O (outside), U (unit), or P - B must be followed by I or L
            # prevent I (inside) going to B (beginning), O (outside), U (unit), or P - I must be followed by I or L
            # prevent L (last) going to I (inside) or L(last) - U must be followed by B, O, U, or P
            # prevent U (unit) going to I (inside) or L(last) - U must be followed by B, O, U, or P
            # prevent O (outside) going to I (inside) or L (last) - O must be followed by B, O, U, or P
            self.invalid_transitions_position = {'B': 'BOU',
                                                 'I': 'BOU',
                                                 'L': 'IL',
                                                 'U': 'IL',
                                                 'O': 'IL'}
            # prevent B (beginning) from going to I (inside) or L (last) of a different type
            # prevent I (inside) from going to I (inside) or L (last) of a different tpye
            self.invalid_transitions_tags = {'B': 'IL',
                                             'I': 'IL'}
        if self.prefixes == set(['B', 'I', 'E', 'S', 'O']):
            # (B)eginning (I)nside (E)nd (S)ingle (O)utside
            # sentence must begin with [CLS] (O)
            self.invalid_begin = ('B', 'I', 'E', 'S')
            # sentence must end with [SEP] (O)
            self.invalid_end = ('B', 'I', 'E', 'S')
            # prevent B (beginning) going to B (beginning), O (outside), S (single), or P - B must be followed by I or E
            # prevent I (inside) going to B (beginning), O (outside), S (single), or P - I must be followed by I or E
            # prevent E (end) going to I (inside) or E (end) - U must be followed by B, O, U, or P
            # prevent S (single) going to I (inside) or E (end) - U must be followed by B, O, U, or P
            # prevent O (outside) going to I (inside) or E (end) - O must be followed by B, O, U, or P
            self.invalid_transitions_position = {'B': 'BOS',
                                                 'I': 'BOS',
                                                 'E': 'IE',
                                                 'S': 'IE',
                                                 'O': 'IE'}
            # prevent B (beginning) from going to I (inside) or E (end) of a different type
            # prevent I (inside) from going to I (inside) or E (end) of a different tpye
            self.invalid_transitions_tags = {'B': 'IE',
                                             'I': 'IE'}
    

    def init_crf_transitions(self, imp_value=-100):
        num_tags = len(self.tag_names)
        # penalize bad beginnings and endings
        for i in range(num_tags):
            tag_name = self.tag_names[i]
            if tag_name.split('-')[0] in self.invalid_begin:
                torch.nn.init.constant_(self.crf.start_transitions[i], imp_value)
            if tag_name.split('-')[0] in self.invalid_end:
                torch.nn.init.constant_(self.crf.end_transitions[i], imp_value)
        # build tag type dictionary
        tag_is = {}
        for tag_position in self.prefixes:
            tag_is[tag_position] = [i for i, tag in enumerate(self.tag_names) if tag.split('-')[0] == tag_position]
        # penalties for invalid consecutive tags by position
        for from_tag, to_tag_list in self.invalid_transitions_position.items():
            to_tags = list(to_tag_list)
            for from_tag_i in tag_is[from_tag]:
                for to_tag in to_tags:
                    for to_tag_i in tag_is[to_tag]:
                        torch.nn.init.constant_(self.crf.transitions[from_tag_i, to_tag_i], imp_value)
        # penalties for invalid consecutive tags by tag
        for from_tag, to_tag_list in self.invalid_transitions_tags.items():
            to_tags = list(to_tag_list)
            for from_tag_i in tag_is[from_tag]:
                for to_tag in to_tags:
                    for to_tag_i in tag_is[to_tag]:
                        if self.tag_names[from_tag_i].split('-')[1] != self.tag_names[to_tag_i].split('-')[1]:
                            torch.nn.init.constant_(self.crf.transitions[from_tag_i, to_tag_i], imp_value)
    

    def decode(self, emissions, mask):
        crf_out = self.crf.decode(emissions, mask=mask)
        return crf_out


    def forward(self, emissions, tags, mask, reduction='sum'):
        crf_loss = self.crf(emissions, tags=tags, mask=mask, reduction=reduction)
        return crf_loss
