'''
Created on 25/09/2013

@author: Du
'''

import pygame
from pygame import Rect, Surface
import pickle

BGCOLOR = (15, 15, 20)
BLOCKSIZE = 30
BORDERWIDTH = 10
MATRIS_OFFSET = 20

WIDTH = 700
HEIGHT = 20*BLOCKSIZE + BORDERWIDTH*2 + MATRIS_OFFSET*2
MATRIX_WIDTH = 10
MATRIX_HEIGHT = 22
VISIBLE_MATRIX_HEIGHT = MATRIX_HEIGHT - 2

def pickleLoader(pklFile):
    try:
        while True:
            yield pickle.load(pklFile)
    except EOFError:
        pass
    
def create_surface(log,number=0):
    size = {'width': MATRIX_WIDTH, 'height': MATRIX_HEIGHT}
    surface = Surface((size['width']  * BLOCKSIZE,(size['height']-2) * BLOCKSIZE))
    for y in range(size['height']):
            for x in range(size['width']):
                block_location = Rect(x*BLOCKSIZE, (y*BLOCKSIZE - 2*BLOCKSIZE), BLOCKSIZE, BLOCKSIZE)
                if log[number]['matrix'][(y,x)] is None:
                    surface.fill(BGCOLOR, block_location)
                else:
                    surface.fill(log[number]['matrix'][(y,x)][1], block_location)
    return surface

if __name__ == '__main__':
    db = open('log.pickle','rb')
    log = []
    with open('log.pickle', 'rb') as f:
        for event in pickleLoader(f):
            log.append(event)
    
    #create window
    pygame.init()
    screen = pygame.display.set_mode((WIDTH,HEIGHT))
    pygame.display.set_caption('Replay viewer')
    #number of the log history
    number = 0
    surface = create_surface(log,number)
    
    
    running = 1
    clock = pygame.time.Clock()
    while running:
        clock.tick(20)
        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN:
                if event.key is pygame.K_ESCAPE:
                    print 'escape'
                    pygame.quit()
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            if number-1 <0:
                number = 0
            else:
                number = number - 1
            surface = create_surface(log,number)
            
        elif keys[pygame.K_RIGHT]:
            if number+1 > len(log)-1:
                number = len(log) -1
            else:
                number = number + 1
            surface = create_surface(log,number)
        
        screen.blit(surface,(0,0))
        pygame.display.flip()
    