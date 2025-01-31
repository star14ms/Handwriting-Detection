import torch
import os
import pandas as pd

from utils.rich import new_progress, console
from utils.utils import read_csv
from test import test


class Trainer:
    MODEL_NAME = 'model.pt'
    TRAINER_STATE_NAME = 'trainer_states.pt'
    TRAIN_STEP_RESULT_PATH = "train_step_result.csv"
    TRAIN_EPOCH_RESULT_PATH = "train_result.csv"
    train_step_result = {
        'n_learn': [], 'loss': [], 'acc': [], 
        'initial_acc': [], 'medial_acc': [], 'final_acc': [], 
    }
    train_epoch_result = {
        'loss': [], 'acc': []
    }

    def __init__(self, model, train_loader, test_loader, loss_fn, optimizer, device, print_every, save_dir, load_model_date_path=''):
        self.model = model
        self.train_loader = train_loader
        self.test_loader = test_loader
        self.loss_fn = loss_fn
        self.optimizer = optimizer
        self.device = device
        self.print_every = print_every
        self.save_dir = save_dir
        self.progress = new_progress()
        self.epoch = 0
        self.train_epoch = self.train_epoch_imf_loss if 'CtoP' in model.__class__.__name__ else self.train_epoch_basic
        self.init_local_info()

        if load_model_date_path:
            self.load_model()
            Trainer.train_step_result = read_csv(self.save_dir+Trainer.TRAIN_STEP_RESULT_PATH, return_dict=True)
            self.n_learn = Trainer.train_step_result['n_learn'][-1]
        else:
            self.n_learn = 0

        console.log("-" * 60)
        total_params = sum(p.numel() for p in model.parameters())
        console.log("num of parameter :", total_params)
        trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
        console.log("trainable params :", trainable_params)
        console.log("-" * 60)

    def train(self, epochs):
        console.log('Train Start!\n')
        self.progress.start()
        task_id = self.progress.add_task(f'epoch 1/{epochs}', total=epochs)
    
        for epoch in range(self.epoch+1, epochs+1):
            train_loss, train_acc = self.train_epoch(self.model)
            # test_loss, test_acc = test(self.model, self.test_loader, self.loss_fn, self.progress)

            self.progress.update(task_id, description=f'epoch {epoch}/{epochs}', advance=1)
            self.save_model()

            Trainer.save_epoch_result['loss'].append(train_loss)
            Trainer.save_epoch_result['acc'].append(train_acc)
            self.save_epoch_result()
        
        self.progress.stop()

    def train_epoch_imf_loss(self, model):
        model.train()
        start_iter = self.n_learn+self.train_loader.batch_size
        size = len(self.train_loader.dataset)

        task_id = self.progress.add_task(f'iter {start_iter}/{size}', total=size)
        
        train_loss, correct, current = 0, 0, 0
        i_correct, m_correct, f_correct = 0, 0, 0
        self.init_local_info()
    
        for iter, (x, t) in enumerate(self.train_loader):
            x = x.to(self.device)
            yi, ym, yf = model(x)
            yi, ym, yf = yi.cpu(), ym.cpu(), yf.cpu()
            
            ti, tm, tf = t.values()
            loss = self.loss_fn(yi, ti) + self.loss_fn(ym, tm) + self.loss_fn(yf, tf)
            self.optimizer.zero_grad()
            loss.backward()
            self.optimizer.step()
    
            ones = torch.ones([len(x)])
            mask_i = (yi.argmax(1) == ti)
            mask_m = (ym.argmax(1) == tm)
            mask_f = (yf.argmax(1) == tf)
            correct_batch = (ones * mask_i * mask_m * mask_f).sum().item()
            
            loss_batch = loss.item()
            i_correct_batch = mask_i.sum().item()
            m_correct_batch = mask_m.sum().item()
            f_correct_batch = mask_f.sum().item()

            train_loss += loss_batch
            correct += correct_batch
            i_correct += i_correct_batch
            m_correct += m_correct_batch
            f_correct += f_correct_batch
            current += len(x)
            self.update_local_info(loss_batch, correct_batch, i_correct_batch, m_correct_batch, f_correct_batch, len(x))
            self.n_learn += len(x)
    
            self.progress.update(task_id, description=f'iter {self.n_learn % size}/{size}', advance=len(x))
            
            if (iter+1) % self.print_every == 0:
                l = self.local_info
                avg_loss = l['train_loss'] / l['current']
                avg_acc = l['correct'] / l['current'] * 100
                avg_i_acc = l['i_correct'] / l['current'] * 100
                avg_m_acc = l['m_correct'] / l['current'] * 100
                avg_f_acc = l['f_correct'] / l['current'] * 100

                Trainer.train_step_result["n_learn"].append(self.n_learn)
                Trainer.train_step_result["loss"].append(f'{avg_loss:>6f}')
                Trainer.train_step_result["acc"].append(f'{avg_acc:>0.1f}')
                Trainer.train_step_result["initial_acc"].append(f'{avg_i_acc:>0.1f}')
                Trainer.train_step_result["medial_acc"].append(f'{avg_m_acc:>0.1f}')
                Trainer.train_step_result["final_acc"].append(f'{avg_f_acc:>0.1f}')

                self.progress.log(self.make_log(avg_loss, avg_acc, avg_i_acc, avg_m_acc, avg_f_acc))
                self.init_local_info()
                
            if current % 10000 == 0:
                avg_loss = train_loss / current
                avg_acc = correct / current * 100
                avg_i_acc = i_correct / current * 100
                avg_m_acc = m_correct / current * 100
                avg_f_acc = f_correct / current * 100
                self.save_step_result()
                self.save_model()
                
        self.progress.remove_task(task_id)
        train_loss /= current
        correct /= current
        return train_loss, correct * 100

    def train_epoch_basic(self, model):
        model.train()
        start_iter = self.n_learn+self.train_loader.batch_size
        size = len(self.train_loader.dataset)

        task_id = self.progress.add_task(f'iter {start_iter}/{size}', total=size)
        
        train_loss, correct, current = 0, 0, 0
        self.init_local_info()
    
        for iter, (x, t) in enumerate(self.train_loader):
            x = x.to(self.device)
            y = model(x).cpu()
            
            loss = self.loss_fn(y, t)
            self.optimizer.zero_grad()
            loss.backward()
            self.optimizer.step()
    
            ones = torch.ones([len(x)])
            correct_mask = (y.argmax(1) == t)
            correct_batch = (ones * correct_mask).sum().item()
            
            loss_batch = loss.item()

            train_loss += loss_batch
            correct += correct_batch
            current += len(x)
            self.update_local_info(loss_batch, correct_batch, 0, 0, 0, len(x))
            self.n_learn += len(x)
    
            self.progress.update(task_id, description=f'iter {self.n_learn % size}/{size}', advance=len(x))
            
            if (iter+1) % self.print_every == 0:
                l = self.local_info
                avg_loss = l['train_loss'] / l['current']
                avg_acc = l['correct'] / l['current'] * 100

                Trainer.train_step_result["n_learn"].append(self.n_learn)
                Trainer.train_step_result["loss"].append(f'{avg_loss:>6f}')
                Trainer.train_step_result["acc"].append(f'{avg_acc:>0.1f}')
                Trainer.train_step_result["initial_acc"].append(0)
                Trainer.train_step_result["medial_acc"].append(0)
                Trainer.train_step_result["final_acc"].append(0)

                self.progress.log(self.make_log(avg_loss, avg_acc, 0, 0, 0))
                self.init_local_info()
                
            if current % 10000 == 0:
                avg_loss = train_loss / current
                avg_acc = correct / current * 100
                self.save_step_result()
                self.save_model()
                
        self.progress.remove_task(task_id)
        train_loss /= current
        correct /= current
        return train_loss, correct * 100

    def init_local_info(self):
        self.local_info = {
            'train_loss': 0, 'current': 0, 'correct': 0,
            'i_correct': 0, 'm_correct': 0, 'f_correct': 0, 
        }

    def update_local_info(self, loss, correct_batch, i_correct_batch, m_correct_batch, f_correct_batch, len_x):
        self.local_info['train_loss'] += loss
        self.local_info['correct'] += correct_batch
        self.local_info['i_correct'] += i_correct_batch
        self.local_info['m_correct'] += m_correct_batch
        self.local_info['f_correct'] += f_correct_batch
        self.local_info['current'] += len_x
    
    def make_log(self, avg_loss, avg_acc, avg_i_acc, avg_m_acc, avg_f_acc):
        if self.train_epoch == self.train_epoch_basic:
            return 'loss: {:>6f} | acc: {:>0.1f}%'.format(
                avg_loss, avg_acc
            )
        
        return 'loss: {:>6f} | acc: {:>0.1f}% (초성 {:>0.1f}%) (중성 {:>0.1f}%) (종성 {:>0.1f}%)'.format(
            avg_loss, avg_acc, avg_i_acc, avg_m_acc, avg_f_acc
        )
        
    def save_model(self):
        os.makedirs(self.save_dir, exist_ok=True)
        torch.save(self.model.state_dict(), self.save_dir+Trainer.MODEL_NAME)

        trainer_states = {
            'optimizer_state_dict': self.optimizer.state_dict(),
            'train_loader': self.train_loader,
            'epoch': self.epoch,
        }
        torch.save(trainer_states, self.save_dir+Trainer.TRAINER_STATE_NAME)
        self.progress.log(f'Saved PyTorch Model State to {self.save_dir+Trainer.MODEL_NAME}')

    def load_model(self):
        self.model.load_state_dict(torch.load(self.save_dir+Trainer.MODEL_NAME))

        trainer_states = torch.load(self.save_dir+Trainer.TRAINER_STATE_NAME)
        self.optimizer.load_state_dict(trainer_states['optimizer_state_dict'])
        self.train_loader = trainer_states['train_loader']
        self.epoch = trainer_states['epoch']
        console.log('모델 로드 완료!')

    def save_step_result(self) -> None:
        os.makedirs(self.save_dir, exist_ok=True)
        file_name = Trainer.TRAIN_STEP_RESULT_PATH
        train_step_df = pd.DataFrame(Trainer.train_step_result)
        train_step_df.to_csv(self.save_dir+file_name, encoding="UTF-8", index=False)

    def save_epoch_result(self) -> None:
        os.makedirs(self.save_dir, exist_ok=True)
        file_name = Trainer.TRAIN_EPOCH_RESULT_PATH
        train_step_df = pd.DataFrame(Trainer.train_epoch_result)
        train_step_df.to_csv(self.save_dir+file_name, encoding="UTF-8", index=False)
