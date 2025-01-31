import sys
import pygame
import torch
import argparse
import time
import numpy as np

from kohwctop.model import KoCtoP, ConvNet
from kohwctop.transform import Resize
from kohwctop.test import predict, predict_KoCtoP
from utils.plot import set_font
from utils.rich import console


def main(args):
    model, model_KoCtoP = load_model(args)
    mousepos = []
    detect_interval_sec = 2
    is_drawing = False
    show_graph = False
    result = None

    pygame.init()
    screen = pygame.display.set_mode((512, 512))

    start = time.time()
    while True:
        screen.fill((0, 0, 0))
    
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            
            elif event.type == pygame.MOUSEBUTTONDOWN:
                is_drawing = True
            elif event.type == pygame.MOUSEBUTTONUP:
                is_drawing = False
            elif is_drawing and event.type == pygame.MOUSEMOTION:
                mousepos.append(event.pos)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                elif event.key == pygame.K_SPACE:
                    mousepos.clear()
                elif event.key == pygame.K_v:
                    show_graph = True

        for pos in mousepos:
            pygame.draw.circle(screen, (255, 255, 255), pos, 5)
        
        if detect_interval_sec <= time.time() - start:
            start = time.time()
            result = detect(model, model_KoCtoP, screen, show_graph)
            console.print(result)
            show_graph = False

        if result is not None:
            text = myfont.render(list(result.keys())[0], True, (255, 255, 255))
            screen.blit(text, (512-120, 0))

        pygame.display.update()
        

def load_model(args):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    console.log("Using [green]{}[/green] device\n".format(device))

    model_KoCtoP = KoCtoP().to(device)
    model_KoCtoP.load_state_dict(torch.load(args.load_model_KoCtoP))

    if args.load_model is None:
        model = None
    else:
        model = ConvNet().to(device)
        model.load_state_dict(torch.load(args.load_model))

    console.log('모델 로드 완료!')

    return model, model_KoCtoP


def detect(model, model_KoCtoP, screen, show_graph):
    arr = pygame.surfarray.pixels2d(screen).T
    arr = np.where(arr!=0, 1.0, 0.0)
    arr = resize(arr.astype(np.float32))

    if model is None:
        pred = predict_KoCtoP(arr, t=None, model=model, plot=show_graph, plot_when_wrong=False)
    else:
        pred = predict(arr, t=None, model=model, model_KoCtoP=model_KoCtoP, plot=show_graph, plot_when_wrong=False)

    return pred


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--load-model-KoCtoP', type=str, dest='load_model_KoCtoP',
                            default='model_CtoP.pt',
                            help='불러올 모델 경로 (model weight path to load)')
    parser.add_argument('--load-model', type=str, dest='load_model',
                        default='model.pt',
                        help='불러올 모델 경로 (model weight path to load)')
    args = parser.parse_args()

    resize = Resize()
    pygame.init()
    pygame.display.set_caption("한글 손글씨 감지!")

    font_path = 'NanumGothicExtraBold.ttf'
    myfont = pygame.font.Font(font_path, 120)
    set_font(font_path)

    main(args)
    