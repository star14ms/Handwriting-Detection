from data import KoSyllableDataset
from model import KoCtoP

import torch
from torch import nn
from torch.utils.data import DataLoader
import random
import argparse

from utils.unicode import join_jamos
from utils.rich import new_progress, console
from utils.plot import show_img_and_scores, set_font, ys_plot_kwargs
from tools import to_chr


parser = argparse.ArgumentParser()
parser.add_argument('--load-model', type=str, dest='load_model',
                        default='save/KoCtoP-acc_0.1159-loss_0.104213-380000.pth',
                        help='model weight path to load')
parser.add_argument('--batch-size', type=int, dest='batch_size',
                        default=50,
                        help='batch size')
args = parser.parse_args()


set_font(family='BM JUA_TTF')


def test(model, test_loader, loss_fn, progress):
    model.eval()
    batch_size = test_loader.batch_size
    size = len(test_loader.dataset)
    task_id = progress.add_task(f'iter {batch_size}/{size}', total=size)

    test_loss, correct, current = 0, 0, 0
    
    with torch.no_grad():
        for iter, (x, t) in enumerate(test_loader):
            x = x.to(device)
            yi, ym, yf = model(x)
            yi, ym, yf = yi.cpu(), ym.cpu(), yf.cpu()
            
            ti, tm, tf = t.values()
            loss = loss_fn(yi, ti) + loss_fn(ym, tm) + loss_fn(yf, tf)
            test_loss += loss.item()
            
            ones = torch.ones([len(x)])
            mask_i = (yi.argmax(1) == ti)
            mask_m = (ym.argmax(1) == tm)
            mask_f = (yf.argmax(1) == tf)
            correct += (ones * mask_i * mask_m * mask_f).sum().item()
    
            current += len(x)
            progress.update(task_id, description=f'iter {current}/{size}', advance=len(x))

            if iter % 10 == 0:
                progress.log(f"loss: {loss.item():>6f} acc: {correct/current*100:>0.3f}%")

    test_loss /= current
    correct /= current * 100
    progress.log(f"Test Error: \n Accuracy: {(correct):>0.3f}%, Avg loss: {test_loss:>6f} \n")
    progress.remove_task(task_id)

    return test_loss, correct


def predict(dataset, idx, model, device, plot=True):
    model.eval()
    x, t = dataset[idx]
    x = x.unsqueeze(0).to(device)
    
    yi, ym, yf = model(x)
    ti, tm, tf = t.values()
    pi, pm, pf = yi.argmax(1).cpu(), \
            ym.argmax(1).cpu(), \
            yf.argmax(1).cpu()

    chr_yi = to_chr['i'][pi.item()]
    chr_ym = to_chr['m'][pm.item()]
    chr_yf = to_chr['f'][pf.item()]
    char = join_jamos(chr_yi + chr_ym + chr_yf)
    
    if t is not None:
        label_yi = to_chr['i'][t['initial']]
        label_ym = to_chr['m'][t['medial']]
        label_yf = to_chr['f'][t['final']]
        correct = (pi==ti and pm==tm and pf==tf)
    
        text = 'test data {} - 예측: {} 정답: {}'.format(idx, char, join_jamos(label_yi + label_ym + label_yf))
    else:
        text = 'test data {} - 예측: {}'.format(idx, char)
    
    if plot:
        show_img_and_scores(x.cpu(), yi.cpu(), ym.cpu(), yf.cpu(), title=text)
    else:
        console.log(text)
        input()
    
    if t is not None:
        return char, correct
    else:
        return char


def test_sample(test_set, model, device, random_sample=True):
    model.eval()
    with torch.no_grad():
        idx = random.randint(0, len(test_set)-1) if random_sample else 0
        while True:
            predict(test_set, idx, model, device)
            if random_sample:
                idx = random.randint(0, len(test_set)-1) 
            else:
                try: 
                    idx = int(input('data idx: '))
                except ValueError:
                    idx += 1


if __name__ == '__main__':
    device = "cuda" if torch.cuda.is_available() else "cpu"
    console.log("Using [green]{}[/green] device\n".format(device))
    
    batch_size = args.batch_size
    test_set = KoSyllableDataset(train=False)
    test_loader = DataLoader(test_set, batch_size, shuffle=False)
    
    model = KoCtoP().to(device)
    model.load_state_dict(torch.load(args.load_model))
    
    console.log('모델 로드 완료!')

    test_sample(test_set, model, device, random_sample=False)
    
    # loss_fn = nn.CrossEntropyLoss()
    # with new_progress() as progress:
    #     test(model, test_loader, loss_fn, progress)


