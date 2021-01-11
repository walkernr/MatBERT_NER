import json
import torch
from torch.utils.data import TensorDataset
from transformers import BertTokenizer, AutoConfig, get_linear_schedule_with_warmup


class NERModel():

	def __init__(self, model="allenai/scibert_scivocab_cased", classes = ["O"]):
		self.tokenizer = BertTokenizer.from_pretrained(model)
		self.classes = classes
		self.config = AutoConfig.from_pretrained(model)
	    self.config.num_labels = len(self.classes)

	def preprocess(self, datafile):

		data = []
		with open(datafile, 'r') as f:
			for l in f:
				data.append(json.loads(l))

		classes_raw = data[0]['labels']
		classes = ["O"]
		for c in classes_raw:
			classes.append("B-{}".format(c))
			classes.append("I-{}".format(c))

		data = [[(d['text'],d['annotation']) for d in s] for a in data for s in a['tokens']]

		input_examples = []
		max_sequence_length = 0
		for i, d in enumerate(data):
			labels = []
			text = []
			for t,l in d:

				#This causes issues with BERT for some reason
				if t in ['̄','̊']:
					continue	

				text.append(t)
				if l is None:
					label = "O"
				elif "PUT" in l or "PVL" in l:
					label = "O"
				else:
					if len(labels) > 0 and l in labels[-1]:
						label = "I-{}".format(l)
					else:
						label = "B-{}".format(l)
				labels.append(label)

			if len(text) > max_sequence_length:
				max_sequence_length = len(text)

			example = InputExample(i, text, labels)

			input_examples.append(example)

		features = self.convert_examples_to_features(
		        input_examples,
		        classes,
		        max_sequence_length,
		)

		all_input_ids = torch.tensor([f.input_ids for f in features], dtype=torch.long)
		all_input_mask = torch.tensor([f.input_mask for f in features], dtype=torch.long)
		all_valid_mask = torch.tensor([f.valid_mask for f in features], dtype=torch.long)
		all_segment_ids = torch.tensor([f.segment_ids for f in features], dtype=torch.long)
		all_label_ids = torch.tensor([f.label_ids for f in features], dtype=torch.long)

		dataset = TensorDataset(all_input_ids, all_input_mask, all_valid_mask, all_segment_ids, all_label_ids)

		return dataset

	def create_dataloaders():

	def train():

	def predict():

	def evaluate():

	def __convert_examples_to_features(
			self,
	        examples,
	        label_list,
	        max_seq_length,
	        tokenizer=self.tokenizer,
	        cls_token_at_end=False,
	        cls_token="[CLS]",
	        cls_token_segment_id=1,
	        sep_token="[SEP]",
	        sep_token_extra=False,
	        pad_on_left=False,
	        pad_token=0,
	        pad_token_segment_id=0,
	        pad_token_label_id=-100,
	        sequence_a_segment_id=0,
	        mask_padding_with_zero=True,
	):
	    """ Loads a data file into a list of `InputBatch`s
	        `cls_token_at_end` define the location of the CLS token:
	            - False (Default, BERT/XLM pattern): [CLS] + A + [SEP] + B + [SEP]
	            - True (XLNet/GPT pattern): A + [SEP] + B + [SEP] + [CLS]
	        `cls_token_segment_id` define the segment id associated to the CLS token (0 for BERT, 2 for XLNet)
	    """
	    label_map = {label: i for i, label in enumerate(label_list)}
	    span_labels = []
	    for label in label_list:
	        label = label.split('-')[-1]
	        if label not in span_labels:
	            span_labels.append(label)
	    span_map = {label: i for i, label in enumerate(span_labels)}
	    features = []
	    for (ex_index, example) in enumerate(examples):
	        if ex_index % 10000 == 0:
	            print("Writing example %d of %d"%(ex_index, len(examples)))

	        tokens = []
	        valid_mask = []
	        for word in example.words:
	            word_tokens = tokenizer.tokenize(word)
	            # bert-base-multilingual-cased sometimes output "nothing ([]) when calling tokenize with just a space.
	            for i, word_token in enumerate(word_tokens):
	                if i == 0:
	                    valid_mask.append(1)
	                else:
	                    valid_mask.append(0)
	                tokens.append(word_token)
	        label_ids = [label_map[label] for label in example.labels]
	        entities = get_entities(example.labels)
	        start_ids = [span_map['O']] * len(label_ids)
	        end_ids = [span_map['O']] * len(label_ids)
	        for entity in entities:
	            start_ids[entity[1]] = span_map[entity[0]]
	            end_ids[entity[-1]] = span_map[entity[0]]
	        # Account for [CLS] and [SEP] with "- 2" and with "- 3" for RoBERTa.
	        special_tokens_count = 3 if sep_token_extra else 2
	        if len(tokens) > max_seq_length - special_tokens_count:
	            tokens = tokens[: (max_seq_length - special_tokens_count)]
	            label_ids = label_ids[: (max_seq_length - special_tokens_count)]
	            valid_mask = valid_mask[: (max_seq_length - special_tokens_count)]
	            start_ids = start_ids[: (max_seq_length - special_tokens_count)]
	            end_ids = end_ids[: (max_seq_length - special_tokens_count)]

	        tokens += [sep_token]
	        label_ids += [pad_token_label_id]
	        start_ids += [pad_token_label_id]
	        end_ids += [pad_token_label_id]
	        valid_mask.append(1)
	        if sep_token_extra:
	            # roberta uses an extra separator b/w pairs of sentences
	            tokens += [sep_token]
	            label_ids += [pad_token_label_id]
	            start_ids += [pad_token_label_id]
	            end_ids += [pad_token_label_id]
	            valid_mask.append(1)
	        segment_ids = [sequence_a_segment_id] * len(tokens)

	        if cls_token_at_end:
	            tokens += [cls_token]
	            label_ids += [pad_token_label_id]
	            start_ids += [pad_token_label_id]
	            end_ids += [pad_token_label_id]
	            segment_ids += [cls_token_segment_id]
	            valid_mask.append(1)
	        else:
	            tokens = [cls_token] + tokens
	            label_ids = [pad_token_label_id] + label_ids
	            start_ids = [pad_token_label_id] + start_ids
	            end_ids = [pad_token_label_id] + end_ids
	            segment_ids = [cls_token_segment_id] + segment_ids
	            valid_mask.insert(0, 1)

	        input_ids = tokenizer.convert_tokens_to_ids(tokens)

	        # The mask has 1 for real tokens and 0 for padding tokens. Only real
	        # tokens are attended to.
	        input_mask = [1 if mask_padding_with_zero else 0] * len(input_ids)

	        # Zero-pad up to the sequence length.
	        padding_length = max_seq_length - len(input_ids)
	        if pad_on_left:
	            input_ids = ([pad_token] * padding_length) + input_ids
	            input_mask = ([0 if mask_padding_with_zero else 1] * padding_length) + input_mask
	            segment_ids = ([pad_token_segment_id] * padding_length) + segment_ids
	            label_ids = ([pad_token_label_id] * padding_length) + label_ids
	            start_ids = ([pad_token_label_id] * padding_length) + start_ids
	            end_ids = ([pad_token_label_id] * padding_length) + end_ids
	            valid_mask = ([0] * padding_length) + valid_mask
	        else:
	            input_ids += [pad_token] * padding_length
	            input_mask += [0 if mask_padding_with_zero else 1] * padding_length
	            segment_ids += [pad_token_segment_id] * padding_length
	            label_ids += [pad_token_label_id] * padding_length
	            start_ids += [pad_token_label_id] * padding_length
	            end_ids += [pad_token_label_id] * padding_length
	            valid_mask += [0] * padding_length
	        while (len(label_ids) < max_seq_length):
	            label_ids.append(pad_token_label_id)
	            start_ids.append(pad_token_label_id)
	            end_ids.append(pad_token_label_id)

	        assert len(input_ids) == max_seq_length
	        assert len(input_mask) == max_seq_length
	        assert len(segment_ids) == max_seq_length
	        try:
	            assert len(label_ids) == max_seq_length
	        except AssertionError:
	            print(label_ids)
	            print(len(label_ids), max_seq_length)
	        assert len(start_ids) == max_seq_length
	        assert len(end_ids) == max_seq_length
	        assert len(valid_mask) == max_seq_length

	        features.append(
	            InputFeatures(input_ids=input_ids,
	                          input_mask=input_mask,
	                          valid_mask=valid_mask,
	                          segment_ids=segment_ids,
	                          label_ids=label_ids,
	                          start_ids=start_ids,
	                          end_ids=end_ids)
	        )
	    return features


	def __end_of_chunk(self, prev_tag, tag, prev_type, type_):
	    """Checks if a chunk ended between the previous and current word.
	    Args:
	        prev_tag: previous chunk tag.
	        tag: current chunk tag.
	        prev_type: previous type.
	        type_: current type.
	    Returns:
	        chunk_end: boolean.
	    """
	    chunk_end = False

	    if prev_tag == 'E': chunk_end = True
	    if prev_tag == 'S': chunk_end = True

	    if prev_tag == 'B' and tag == 'B': chunk_end = True
	    if prev_tag == 'B' and tag == 'S': chunk_end = True
	    if prev_tag == 'B' and tag == 'O': chunk_end = True
	    if prev_tag == 'I' and tag == 'B': chunk_end = True
	    if prev_tag == 'I' and tag == 'S': chunk_end = True
	    if prev_tag == 'I' and tag == 'O': chunk_end = True

	    if prev_tag != 'O' and prev_tag != '.' and prev_type != type_:
	        chunk_end = True

	    return chunk_end


	def __start_of_chunk(self, prev_tag, tag, prev_type, type_):
	    """Checks if a chunk started between the previous and current word.
	    Args:
	        prev_tag: previous chunk tag.
	        tag: current chunk tag.
	        prev_type: previous type.
	        type_: current type.
	    Returns:
	        chunk_start: boolean.
	    """
	    chunk_start = False

	    if tag == 'B': chunk_start = True
	    if tag == 'S': chunk_start = True

	    if prev_tag == 'E' and tag == 'E': chunk_start = True
	    if prev_tag == 'E' and tag == 'I': chunk_start = True
	    if prev_tag == 'S' and tag == 'E': chunk_start = True
	    if prev_tag == 'S' and tag == 'I': chunk_start = True
	    if prev_tag == 'O' and tag == 'E': chunk_start = True
	    if prev_tag == 'O' and tag == 'I': chunk_start = True

	    if tag != 'O' and tag != '.' and prev_type != type_:
	        chunk_start = True

	    return chunk_start

	def __get_entities(self, seq):
	    """Gets entities from sequence.
	    note: BIO
	    Args:
	        seq (list): sequence of labels.
	    Returns:
	        list: list of (chunk_type, chunk_start, chunk_end).
	    Example:
	        seq = ['B-PER', 'I-PER', 'O', 'B-LOC', 'I-PER']
	        get_entity_bio(seq)
	        #output
	        [['PER', 0,1], ['LOC', 3, 3], ['PER', 4, 4]]
	    """
	    if any(isinstance(s, list) for s in seq):
	        seq = [item for sublist in seq for item in sublist + ['O']]

	    prev_tag = 'O'
	    prev_type = ''
	    begin_offset = 0
	    chunks = []
	    for i, chunk in enumerate(seq + ['O']):
	        tag = chunk[0]
	        type_ = chunk.split('-')[-1]

	        if end_of_chunk(prev_tag, tag, prev_type, type_):
	            chunks.append((prev_type, begin_offset, i - 1))
	        if start_of_chunk(prev_tag, tag, prev_type, type_):
	            begin_offset = i
	        prev_tag = tag
	        prev_type = type_

	    return set(chunks)

	def __collate_fn(self, batch):
	    """
	    batch should be a list of (sequence, target, length) tuples...
	    Returns a padded tensor of sequences sorted from longest to shortest,
	    """
	    batch_tuple = tuple(map(torch.stack, zip(*batch)))
	    batch_lens = torch.sum(batch_tuple[1], dim=-1, keepdim=False)
	    max_len = batch_lens.max().item()
	    results = ()
	    for item in batch_tuple:
	        if item.dim() >= 2:
	            results += (item[:, :max_len],)
	        else:
	            results += (item,)
	    return results

class InputFeatures(object):
    """A single set of features of data."""

    def __init__(self, input_ids, input_mask, valid_mask, segment_ids, label_ids, start_ids, end_ids):
        self.input_ids = input_ids
        self.input_mask = input_mask
        self.valid_mask = valid_mask
        self.segment_ids = segment_ids
        self.label_ids = label_ids
        self.start_ids = start_ids
        self.end_ids = end_ids

class InputExample(object):
    """A single training/test example for token classification."""

    def __init__(self, guid, words, labels):
        """Constructs a InputExample.
        Args:
            guid: Unique id for the example.
            words: list. The words of the sequence.
            labels: (Optional) list. The labels for each word of the sequence. This should be
            specified for train and dev examples, but not for test examples.
        """
        self.guid = guid
        self.words = words
        self.labels = labels
