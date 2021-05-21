import os
import argparse
import numpy as np
from seqeval.scheme import IOB1, IOB2, IOBES
from seqeval.metrics import classification_report

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-dv', '--device',
                        help='computation device for model (e.g. cpu, gpu:0, gpu:1)',
                        type=str, default='gpu:0')
    parser.add_argument('-sd', '--seeds',
                        help='comma-separated seeds for data shuffling and model initialization (e.g. 1,2,3 or 2,4,8)',
                        type=str, default='256')
    parser.add_argument('-ts', '--tag_schemes',
                        help='comma-separated tagging schemes to be considered (e.g. iob1,iob2,iobes)',
                        type=str, default='iobes')
    parser.add_argument('-st', '--splits',
                        help='comma-separated training splits to be considered, in percent (e.g. 80). test split will always be 10%% and the validation split will be 1/8 of the training split',
                        type=str, default='80')
    parser.add_argument('-ds', '--datasets',
                        help='comma-separated datasets to be considered (e.g. solid_state,doping)',
                        type=str, default='solid_state')
    parser.add_argument('-ml', '--models',
                        help='comma-separated models to be considered (e.g. matbert,scibert,bert)',
                        type=str, default='matbert')
    parser.add_argument('-sl', '--sentence_level',
                        help='switch for sentence-level learning instead of paragraph-level',
                        action='store_true')
    parser.add_argument('-bs', '--batch_size',
                        help='number of samples in each batch',
                        type=int, default=10)
    parser.add_argument('-on', '--optimizer_name',
                        help='name of optimizer',
                        type=str, default='adamw')
    parser.add_argument('-ne', '--n_epoch',
                        help='number of training epochs',
                        type=int, default=5)
    parser.add_argument('-eu', '--embedding_unfreeze',
                        help='epoch (index) at which bert embeddings are unfrozen',
                        type=int, default=1)
    parser.add_argument('-tu', '--transformer_unfreeze',
                        help='comma-separated number of transformers (encoders) to unfreeze at each epoch',
                        type=str, default='0,12')
    parser.add_argument('-el', '--embedding_learning_rate',
                        help='embedding learning rate',
                        type=float, default=5e-5)
    parser.add_argument('-tl', '--transformer_learning_rate',
                        help='transformer learning rate',
                        type=float, default=5e-5)
    parser.add_argument('-cl', '--classifier_learning_rate',
                        help='pooler/classifier learning rate',
                        type=float, default=5e-3)
    parser.add_argument('-sf', '--scheduling_function',
                        help='function for learning rate scheduler (linear, exponential, or cosine)',
                        type=str, default='linear')
    parser.add_argument('-km', '--keep_model',
                        help='switch for saving the best model parameters to disk',
                        action='store_true')
    args = parser.parse_args()
    return (args.device, args.seeds, args.tag_schemes, args.splits, args.datasets,
            args.models, args.sentence_level, args.batch_size, args.optimizer_name,
            args.n_epoch, args.embedding_unfreeze, args.transformer_unfreeze,
            args.embedding_learning_rate, args.transformer_learning_rate, args.classifier_learning_rate,
            args.scheduling_function, args.keep_model)


if __name__ == '__main__':
    (device, seeds, tag_schemes, splits, datasets,
     models, sentence_level, batch_size, optimizer_name,
     n_epoch, embedding_unfreeze, transformer_unfreeze,
     elr, tlr, clr, scheduling_function, keep_model) = parse_args()
    if 'gpu' in device:
        gpu = True
        try:
            d, n = device.split(':')
        except:
            print('ValueError: Improper device format in command-line argument')
        device = 'cuda'
    else:
        gpu = False
    if gpu:
        os.environ['CUDA_VISIBLE_DEVICES'] = str(n)
    import torch
    from utils.data import NERData
    from models.bert_model import BERTNER
    from models.model_trainer import NERTrainer
    
    torch.device('cuda' if gpu else 'cpu')
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    use_cache = False

    seeds = [int(seed) for seed in seeds.split(',')]
    schemes = [str(tag_scheme).upper() for tag_scheme in tag_schemes.split(',')]
    splits = [int(split) for split in splits.split(',')]
    datasets = [str(dataset) for dataset in datasets.split(',')]
    models = [str(model) for model in models.split(',')]
    encoder_schedule = [int(num) for num in transformer_unfreeze.split(',')]
    if len(encoder_schedule) > n_epoch:
        encoder_schedule = encoder_schedule[:n_epoch]
        print('Provided with encoder schedule longer than number of epochs, truncating')
    elif len(encoder_schedule) < n_epoch:
        encoder_schedule = encoder_schedule+((n_epoch-len(encoder_schedule))*[0])
    if np.sum(encoder_schedule) > 12:
        encoder_schedule = embedding_unfreeze*[0]+[12]
        print('Provided invalid encoder schedule (too many layers), all encoders will be unlocked with the BERT embeddings')


    data_files = {'solid_state': 'data/solid_state.json',
                  'doping': 'data/doping.json',
                  'aunp2': 'data/aunp_2lab.json',
                  'aunp11': 'data/aunp_11lab.json'}
    model_files = {'bert': 'bert-base-uncased',
                   'scibert': 'allenai/scibert_scivocab_uncased',
                #    'matbert': '/home/amalie/MatBERT_NER/matbert_ner/matbert-base-uncased',
                   'matbert': '../../matbert-base-uncased'}
    dschemes = {'IOB1': IOB1, 'IOB2': IOB2, 'IOBES': IOBES}

    for seed in seeds:
        for scheme in schemes:
            for split in splits:
                for dataset in datasets:
                    for model in models:
                        params = (model, dataset, 'sentence' if sentence_level else 'paragraph', scheme.lower(),
                                  batch_size, optimizer_name, n_epoch, embedding_unfreeze, transformer_unfreeze.replace(',', ''),
                                  elr, tlr, clr, scheduling_function, seed, split)
                        alias = '{}_{}_{}_{}_crf_{}_{}_{}_{}_{}_{:.0e}_{:.0e}_{:.0e}_{}_{}_{}'.format(*params)
                        save_dir = os.getcwd()+'/{}/'.format(alias)
                        print('Calculating results for {}'.format(alias))

                        ner_data = NERData(model_files[model], scheme=scheme)

                        if split == 100:
                            split_dict = {'train': split/100}
                        else:
                            split_dict = {'test': 0.1, 'valid': 0.00125*split, 'train': 0.01*split}
                        if split == 100:
                            ner_data.dataloaders['valid'] = None
                            ner_data.dataloaders['test'] = None

                        ner_data.preprocess(data_files[dataset], split_dict, is_file=True, sentence_level=False, shuffle=True, seed=seed)
                        ner_data.create_dataloaders(batch_size=batch_size, shuffle=True, seed=seed)
                        bert_ner = BERTNER(model_file=model_files[model], classes=ner_data.classes, scheme=scheme, seed=seed)
                        bert_ner_trainer = NERTrainer(bert_ner, device)

                        print('Classes: {}'.format(' '.join(ner_data.classes)))

                        if os.path.exists(save_dir+'test.pt'):
                            print('Already trained {}'.format(alias))
                        else:
                            if not os.path.exists(save_dir):
                                os.mkdir(save_dir)
                            
                            bert_ner_trainer.init_optimizer(optimizer_name=optimizer_name, elr=elr, tlr=tlr, clr=clr)
                            bert_ner_trainer.train(n_epoch=n_epoch, train_iter=ner_data.dataloaders['train'], valid_iter=ner_data.dataloaders['valid'],
                                                   embedding_unfreeze=embedding_unfreeze, encoder_schedule=encoder_schedule, scheduling_function=scheduling_function,
                                                   save_dir=save_dir, use_cache=use_cache)
                            bert_ner_trainer.save_history(history_path=save_dir+'history.pt')  
                            if use_cache and keep_model:
                                bert_ner_trainer.save_state(state_path=save_dir+'best.pt')
                            elif not use_cache and not keep_model:
                                os.remove(save_dir+'best.pt')
                                                      
                        if ner_data.dataloaders['test'] is not None:
                            metrics, test_results = bert_ner_trainer.test(ner_data.dataloaders['test'], test_path=save_dir+'test.pt', state_path=save_dir+'best.pt')
                            print(classification_report(test_results['labels'], test_results['predictions'], mode='strict', scheme=dschemes[scheme]))
                            annotations = bert_ner_trainer.predict(ner_data.dataloaders['test'], predict_path=save_dir+'predict.pt', state_path=save_dir+'best.pt')
                            with open(save_dir+'predictions.txt', 'w') as f:
                                for entry in annotations:
                                    f.write(80*'='+'\n')
                                    for sentence in entry:
                                        f.write(80*'-'+'\n')
                                        for word in sentence:
                                            f.write('{:<40}{:<40}\n'.format(word['text'], word['annotation']))
                                        f.write(80*'-'+'\n')
                                    f.write(80*'='+'\n')
