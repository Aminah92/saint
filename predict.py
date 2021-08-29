import argparse

from src.config import args as default_args
from models.model_generator import get_model
from src.train import setup_experiment
from src.dataloader import generate_dataloader
from utils.utils import parse_arguments, dotdict

import torch
import torch.nn as nn
import pytorch_lightning as pl
from pytorch_lightning import seed_everything
from pytorch_lightning.callbacks import ModelCheckpoint

import pandas as pd

from src.trainer import SaintSemiSupLightningModule, SaintSupLightningModule
from src.config import args
import copy

    
def main(args):
    """function to make automatic predition from held-out dataset for example in kaggle test set"""
    
    if args.pretrained_checkpoint is None:
        print('Pretrained checkpoint path missing in config')
        return
    
    transformer, embedding = get_model(args.model, args.num_heads,
                                       args.embed_dim, args.num_layers, 
                                       args.d_ff, args.dropout, 
                                       args.dropout_ff, args.no_num, 
                                       args.no_cat, args.cats)
    
    test_df = pd.read_csv(args.submit_csv_path)
    
    # Change 'ID' to sample unique identifier
    test_df = test_df[['ID']]
    test_df['target'] = -1
    
    _, _, test_loader = generate_dataloader(
        args.experiment, args.seed, args)
    
    fc = nn.Linear(args.embed_dim, args.num_output)
    conf_dict = dict(
        transformer=transformer, embedding=embedding,
        fc=fc, optim=args.optim,
        lr=args.learning_rate,
        weight_decay=args.weight_decay,
        task=args.task, num_output=args.num_output,
        cls_token_idx=args.cls_token_idx,
        freeze_encoder=args.freeze_encoder
    )
    
    model = SaintSupLightningModule(**conf_dict)
    model.load_from_checkpoint(args.pretrained_checkpoint, **conf_dict)
    model.eval()
    model.freeze()
    
    preds = []
    
    with torch.no_grad():
        for x, _ in test_loader:
            output = model(x)
            if args.num_output == 1 or args.num_output == None:
                pred = torch.sigmoid(output)
                pred = (pred > 0.5).long()
            else:
                pred = nn.functional.softmax(output, dim=1)
                pred = torch.argmax(pred, dim=1)
            preds.append(pred)
        preds = torch.cat(preds, dim=0).squeeze()
        preds = preds.numpy()
    
    assert len(preds) == len(test_df)
    test_df['target'] = preds
    
    test_df.to_csv(args.pred_sav_path, index=False)
    
    print(f'Prediction finished,  csv saved at {args.pred_sav_path}')
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    args = parse_arguments(parser, default_args)
    args = dotdict(args)
    
    main(args)
