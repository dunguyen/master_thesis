import copy
import ctypes
import math
import pickle
import random
import socket
import struct
import sys
import threading
import time
import struct

from pygame import Rect, Surface
import pygame

import numpy as np
import scipy
import scipy.signal

import kezmenu
from scores import load_score, write_score
from tetrominoes import list_of_tetrominoes, rotate


class BrokenMatrixException(Exception):
    pass

#TODO: delete this!
#ctypes.windll.inpout32.Out32(0x378,data)
#ctypes.windll.inpout32.Inp32(port)



BGCOLOR = (15, 15, 20)#(40,40,40)
BORDERCOLOR = (140, 140, 140)

BLOCKSIZE = 30
BORDERWIDTH = 10

MATRIS_OFFSET = 20

WIDTH = 700
HEIGHT = 20*BLOCKSIZE + BORDERWIDTH*2 + MATRIS_OFFSET*2

MATRIX_WIDTH = 10
MATRIX_HEIGHT = 22
VISIBLE_MATRIX_HEIGHT = MATRIX_HEIGHT - 2

FPS = 60 # default was 45

PROGRESSIVE_DIFFICULTY = False #true = difficulty gets harder with each level

DISABLE_HARD_DROP = True #Removes the ability to do a hard drop (space)
DISABLE_DOWN = True #Removes the ability to hurry a tetromino (down)

EASY_SPEED = 0.4 #drop speed in s
MEDIUM_SPEED = 0.2 #drop speed in s
HARD_SPEED = 0.07 #drop speed in s
SPEED_LEVELS = 8 # eight levels between each difficulty level
SPEED_INTERVALS = 25 #in ms between each speed level

#Trigger codes
TRIGGER_REMOVE_1_LINE = 1
TRIGGER_REMOVE_2_LINES = 2
TRIGGER_REMOVE_3_LINES = 3
TRIGGER_REMOVE_4_LINES = 4
#TRIGGER_HARD_DROP = 5
TRIGGER_ROTATE = 5
TRIGGER_MOVE = 6
TRIGGER_PLACE_BLOCK = 7
TRIGGER_GAME_OVER = 8
TRIGGER_GAME_START = 9
TRIGGER_VALENCE = 10 # start value for valence, the actual valence is added on
TRIGGER_AROUSAL = 20 # start value for arousal, the actual arousal is added on
TRIGGER_PAUSE = 30
TRIGGER_RELAX = 31
TRIGGER_RESUME = 32
TRIGGER_SELF_ASSESSMENT = 33
TRIGGER_BEGIN_EXPERIMENT = 34 #used to indicate start of 5-minute blocks


# Timeinterval between each selfreport in seconds
SELF_REPORT_INTERVAL = 300
SELF_DIFFICULTY_ASSESSMENT_INTERVAL = 1
DIFFICULTY_CHANGE_INTERVAL = 0.5
DDA_DIFFICULTY_CHANGE_INTERVAL = 5
RELAX_INTERVAL = 5 
EXPERIMENT_1_SEQUENCES = 3 # easy,  medium,  hard (3 recommended)s


#network stuff
PORT = 778 #this should be random and unassigned enough!
HOST = '169.254.191.24' #IP of other computer


#Threading stuff
speed_lock = threading.RLock()
game_state_lock = threading.RLock()
SPEED_THRESHOLD = 0.7 #when the absolute value of speed_change is above 0.7 initiate a change in speed
speed_change = 0.0 #should only range from -1.0 to 1.0
game_state = None

#sloppy coding
last_fun = -1
last_valence = 10
last_arousal = -1
optimal_speed = -1

db = open('log.pickle', 'wb')

continuous_game = True #Game over starts a new game instantly

#dll
#inpout32lib = ctypes.WinDLL('inpout32.dll')
PARALLEL_PORT = 0xD900

def log(trigger_code, matrix=None):
    '''
    Logging function
    '''
    #ctypes.windll.inpout32.Out32(PARALLEL_PORT, trigger_code)
    pygame.time.wait(16)
    if matrix is not None and trigger_code not in [5,6]:
        #start = time.time()
        global db
        if db.closed:
            print 'Something went horribly wrong! Why is db not open?'
            db = open('log.pickle', 'wb')
            pickle.dump({'time' : time.time(),'matrix': strip_surfaces(matrix), 'trigger' : str(trigger_code)},db)
        else:
            pickle.dump({'time' : time.time(),'matrix': strip_surfaces(matrix), 'trigger' : str(trigger_code)},db)
        #stop = time.time()
        
        #print 'dumped to pickle, time: '+ str(stop-start)
    
    #ctypes.windll.inpout32.Out32(PARALLEL_PORT, 0)
    

class DifficultyAssessment(object):
    
    def __init__(self,Game, low_to_high=True):
        self.low_to_high = low_to_high
        self.changed_direction = False
        self.difficulties = [x/1000.0 for x in range(25,625,SPEED_INTERVALS)]
        self.low_difficulty = 0
        self.high_difficulty = len(self.difficulties)-1
        if self.low_to_high:
            self.current_difficulty = self.low_difficulty
        else:
            self.current_difficulty = self.high_difficulty
    
    def get_speed(self):
        if self.low_to_high:
            return self.difficulties[self.low_difficulty]
        else:
            return self.difficulties[self.high_difficulty]

    def change_direction(self):
        if self.changed_direction:
            #code here for calculating final score
            difference = math.fabs(self.low_difficulty-self.high_difficulty)
            if self.low_difficulty <= self.high_difficulty:
                global optimal_speed
                optimal_speed = self.difficulties[(self.low_difficulty+int(math.floor(difference/2)))]
            else:
                global optimal_speed
                optimal_speed = self.difficulties[(self.high_difficulty+math.floor(difference/2))]
        else:
            self.changed_direction = True
            self.low_to_high = not self.low_to_high
            
    def increase_speed(self):
        if self.low_to_high:
            if self.low_difficulty == (len(self.difficulties)-1):
                #force change direction
                self.change_direction()
            else:
                self.low_difficulty = self.low_difficulty+1
        else:
            if self.high_difficulty == 0:
                #force change direction
                self.change_direction()
            else:
                self.high_difficulty = self.high_difficulty-1

class SelfReportMenu(object):
    
    
    
    def __init__(self, screen, Game, mode='selfreport'):
        self.Game = Game
        self.surface = pygame.Surface((WIDTH, HEIGHT))
        self.valence = pygame.image.load("resources/valence.png")
        self.arousal = pygame.image.load("resources/arousal.png")
        log(TRIGGER_SELF_ASSESSMENT,Game.matris.matrix)
        self.change_direction = False
        self.mode=mode
        #for controlling menu
        self.menu_choices = ('1','2','3','4','5','6','7','8','9')
        self.selected_option = '1'
        self.current_questionaire = 'valence'

        self.surface.fill((255,255,255,255))
        screen.blit(self.surface, (0,0))
        if self.current_questionaire is 'valence':
            font = pygame.font.Font(None,36)
            text = font.render('Valence',1,(0,0,0))
            screen.blit(text,(300, 24))
            screen.blit(self.valence, (50,100))
        elif self.current_questionaire is 'arousal':
            font = pygame.font.Font(None,36)
            text = font.render('Arousal',1,(0,0,0))
            screen.blit(text,(300, 24))
            screen.blit(self.arousal, (50,100))
        elif self.current_questionaire is 'fun':
            font = pygame.font.Font(None,36)
            text = font.render('Fun',1,(0,0,0))
            screen.blit(text,(300, 24))
            screen.blit(font.render('No fun',1,(0,0,0)), (50,100))
            screen.blit(font.render('A lot of fun',1,(0,0,0)), (50,100))
            
        pygame.display.update()
        
    def update(self,screen):
        #self.menu.update(events)
        #self.menu.draw(screen)
        screen.blit(self.surface, (0,0))
        if self.current_questionaire is 'valence':
            font = pygame.font.Font(None,36)
            text = font.render('Valence',1,(0,0,0))
            screen.blit(text,(300, 24))
            screen.blit(self.valence, (50,100))
        elif self.current_questionaire is 'arousal':
            font = pygame.font.Font(None,36)
            text = font.render('Arousal',1,(0,0,0))
            screen.blit(text,(300, 24))
            screen.blit(self.arousal, (50,100))
        elif self.current_questionaire is 'fun':
            font = pygame.font.Font(None,36)
            text = font.render('Fun',1,(0,0,0))
            screen.blit(text,(300, 24))
            screen.blit(font.render('No fun',1,(0,0,0)), (50,100))
            screen.blit(font.render('A lot of fun',1,(0,0,0)), (50,100))
            
        if pygame.font:
            fontSize = 36
            fontSpace = 24
            font = pygame.font.Font(None,fontSize)
            menuWidth = len(self.menu_choices)*(fontSize+fontSpace)
            menuHeight = 100+131+fontSpace #from 100 plus image height
            startX = 50
            listOfTextPositions=list()
            for menuEntry in self.menu_choices:
                if menuEntry is self.selected_option:
                    text = font.render(menuEntry,1,(255,0,0))
                else:
                    text = font.render(menuEntry,1,(0,0,0))
                textpos = text.get_rect(centerx=startX+fontSize+fontSpace,centery=menuHeight)
                listOfTextPositions.append(textpos)
                startX=startX+fontSize+fontSpace
                screen.blit(text,textpos)
                
        for event in pygame.event.get():
            keys = pygame.key.get_pressed()
            if keys[pygame.K_LEFT]:
                if self.selected_option is '1':
                    pass
                else:
                    self.selected_option = str(int(self.selected_option)-1)
            elif keys[pygame.K_RIGHT]:
                if self.selected_option is '9':
                    pass
                else:
                    self.selected_option = str(int(self.selected_option)+1)
            elif keys[pygame.K_RETURN]:
                #save and log
                if self.current_questionaire is 'valence':
                    log(TRIGGER_VALENCE+int(self.selected_option), self.Game.matris.matrix)
                    #switch to arousal
                    self.current_questionaire = 'arousal'
                    
                    
                    if self.mode=='difficulty_assessment':
                        global last_valence
                        if last_valence < int(self.selected_option):
                            #change difficulty direction after arousal
                            self.change_direction = True
                            
                        last_valence = int(self.selected_option)
                        
                    global last_valence
                    last_valence = int(self.selected_option)
                elif self.current_questionaire is 'arousal':
                    log(TRIGGER_AROUSAL+int(self.selected_option), self.Game.matris.matrix)
                    global last_arousal
                    last_arousal = int(self.selected_option)
                    #continue game
                    if self.mode=='difficulty_assessment':
                        if self.change_direction:
                            self.Game.difficulty_assessment_obj.change_direction()
                            global last_arousal
                            global last_valence
                            global last_fun
                            last_arousal = -1
                            last_valence = 10 # really low valence
                            last_fun = -1
                            
                        if self.Game.difficulty_assessment:
                            self.Game.difficulty_assessment_obj.increase_speed()
    
                    #make keys unstuck
                    self.Game.matris.unstuck_keys()
                    self.Game.selfreport = not self.Game.selfreport
                    self.Game.switch_sequence = True
                elif self.current_questionaire is 'fun':
                    #continue game
                    if self.mode=='difficulty_assessment':
                        global last_fun
                        if last_fun >int(self.selected_option):
                            #change difficulty direction
                            self.Game.difficulty_assessment_obj.change_direction()
                            global last_arousal
                            global last_valence
                            global last_fun
                            last_arousal = -1
                            last_valence = -1
                            last_fun = -1
                            
                            
                        last_fun = int(self.selected_option)
                        if self.Game.difficulty_assessment:
                            self.Game.difficulty_assessment_obj.increase_speed()
    
                    #make keys unstuck
                    self.Game.matris.unstuck_keys()
                    self.Game.selfreport = not self.Game.selfreport
                    self.Game.switch_sequence = True
                    
        pygame.display.flip()
        
class RelaxationScreen():
    
    def __init__(self,screen):
        self.surface = pygame.Surface((WIDTH, HEIGHT))
        self.surface.fill((255,255,255,255))
        screen.blit(self.surface, (0,0))
        pygame.display.update()
    
    def update(self,time,screen):
        screen.blit(self.surface, (0,0))
        font = pygame.font.Font(None,48)
        text = font.render('Relax',1,(0,0,0))
        textpos = text.get_rect(centerx=screen.get_width()/2, centery=screen.get_height()/2)
        screen.blit(text,textpos)
        text = font.render('Time until start: {0}'.format(int(RELAX_INTERVAL-math.floor(time))),1,(0,0,0))
        textpos = text.get_rect(centerx=screen.get_width()/2, centery=screen.get_height()/2+48+6)
        screen.blit(text,textpos)
        pygame.display.flip()
        
def strip_surfaces(matrix):
    '''
    remove surface objects from a matrix
    '''
    if matrix is not None:
        copy = {}
        for key,value in matrix.iteritems():
            if value is None:
                copy[key] = value
            else:
                copy[key] = (value[0],value[1].get_at((10,10)))
        return copy
    return None

class Matris(object):
    screen = None
    def __init__(self, size=(MATRIX_WIDTH, MATRIX_HEIGHT), blocksize=BLOCKSIZE):
        self.size = {'width': size[0], 'height': size[1]}
        self.blocksize = blocksize
        self.surface = Surface((self.size['width']  * self.blocksize,
                                (self.size['height']-2) * self.blocksize))


        self.matrix = dict()
        for y in range(self.size['height']):
            for x in range(self.size['width']):
                self.matrix[(y,x)] = None


        self.next_tetromino = random.choice(list_of_tetrominoes)
        self.set_tetrominoes()
        self.tetromino_rotation = 0
        self.downwards_timer = 0
        self.base_downwards_speed = 0.4 # Move down every 400 ms

        self.movement_keys = {'left': 0, 'right': 0}
        self.movement_keys_speed = 0.05
        self.movement_keys_timer = (-self.movement_keys_speed)*2

        self.level = 1
        self.score = 0
        self.lines = 0

        self.combo = 1 # Combo will increase when you clear lines with several tetrominos in a row
        
        self.paused = False
        self.gameover = False

        self.highscore = load_score()
        self.played_highscorebeaten_sound = False

        self.levelup_sound = pygame.mixer.Sound("resources/levelup.wav")
        self.linescleared_sound = pygame.mixer.Sound("resources/linecleared.wav")
        self.gameover_sound = pygame.mixer.Sound("resources/gameover.wav")
        self.highscorebeaten_sound = pygame.mixer.Sound("resources/highscorebeaten.wav")


    def set_tetrominoes(self):
        self.current_tetromino = self.next_tetromino
        self.next_tetromino = random.choice(list_of_tetrominoes)
        self.surface_of_next_tetromino = self.construct_surface_of_next_tetromino()
        self.tetromino_position = (0,4) if len(self.current_tetromino.shape) == 2 else (0, 3)
        self.tetromino_rotation = 0
        self.tetromino_block = self.block(self.current_tetromino.color)
        self.shadow_block = self.block(self.current_tetromino.color, shadow=True)

    
    def hard_drop(self):
        amount = 0
        #log(TRIGGER_HARD_DROP, self.matrix)
        while self.request_movement('down'):
            amount += 1

        self.lock_tetromino()
        self.score += 10*amount

    def update(self, timepassed):
        #print "Frame time " + str(timepassed)
        pressed = lambda key: event.type == pygame.KEYDOWN and event.key == key
        unpressed = lambda key: event.type == pygame.KEYUP and event.key == key

        events = pygame.event.get()
        
        for event in events:
            if pressed(pygame.K_p):
                self.surface.fill((0,0,0))
                self.paused = not self.paused
                log(TRIGGER_PAUSE,self.matrix)
            elif event.type == pygame.QUIT:
                self.prepare_and_execute_gameover(playsound=False)
                exit()
            elif pressed(pygame.K_ESCAPE):
                #escape always results in actually exciting the game
                global continuous_game
                continuous_game = False
                self.prepare_and_execute_gameover(playsound=False)
                

        if self.paused:
            #print 'this is paused'
            return
        
        for event in events:
            if pressed(pygame.K_SPACE) and not DISABLE_HARD_DROP:
                self.hard_drop()
            elif pressed(pygame.K_UP) or pressed(pygame.K_w):
                self.request_rotation()

            elif pressed(pygame.K_LEFT) or pressed(pygame.K_a):
                self.request_movement('left')
                self.movement_keys['left'] = 1
            elif pressed(pygame.K_RIGHT) or pressed(pygame.K_d):
                self.request_movement('right')
                self.movement_keys['right'] = 1

            elif unpressed(pygame.K_LEFT) or unpressed(pygame.K_a):
                self.movement_keys['left'] = 0
                self.movement_keys_timer = (-self.movement_keys_speed)*2
            elif unpressed(pygame.K_RIGHT) or unpressed(pygame.K_d):
                self.movement_keys['right'] = 0
                self.movement_keys_timer = (-self.movement_keys_speed)*2

        if PROGRESSIVE_DIFFICULTY:
            self.downwards_speed = self.base_downwards_speed ** (1 + self.level/10.)
        else:
            self.downwards_speed = self.base_downwards_speed

        self.downwards_timer += timepassed
        if not DISABLE_DOWN:    
            downwards_speed = self.downwards_speed*0.10 if any([pygame.key.get_pressed()[pygame.K_DOWN],
                                                            pygame.key.get_pressed()[pygame.K_s]])   else self.downwards_speed
        else:
            downwards_speed = self.downwards_speed
                            
        if self.downwards_timer > downwards_speed:
            #print 'move down', self.downwards_timer
            if not self.request_movement('down'):
                self.lock_tetromino()
            self.downwards_timer %= downwards_speed


        if any(self.movement_keys.values()):
            self.movement_keys_timer += timepassed
        if self.movement_keys_timer > self.movement_keys_speed:
            result = self.request_movement('right' if self.movement_keys['right'] else 'left')
            self.movement_keys_timer %= self.movement_keys_speed
            log(TRIGGER_MOVE,self.matrix)

        with_shadow = self.place_shadow()

        try:
            with_tetromino = self.blend(self.rotated(), allow_failure=False, matrix=with_shadow)
        except BrokenMatrixException:
            self.prepare_and_execute_gameover()
            return

        for y in range(self.size['height']):
            for x in range(self.size['width']):

                #                                       I hide the 2 first rows by drawing them outside of the surface
                block_location = Rect(x*self.blocksize, (y*self.blocksize - 2*self.blocksize), self.blocksize, self.blocksize)
                if with_tetromino[(y,x)] is None:
                    self.surface.fill(BGCOLOR, block_location)
                else:
                    if with_tetromino[(y,x)][0] == 'shadow':
                        self.surface.fill(BGCOLOR, block_location)
                    
                    self.surface.blit(with_tetromino[(y,x)][1], block_location)
                    
    def prepare_and_execute_gameover(self, playsound=True):
        if playsound:
            self.gameover_sound.play()
        write_score(self.score)
        self.gameover = True
        log(TRIGGER_GAME_OVER, self.matrix)
        if not continuous_game:
            #Only close when the game exits to menu
            db.close()

    def place_shadow(self):
        posY, posX = self.tetromino_position
        while self.blend(position=(posY, posX)):
            posY += 1

        position = (posY-1, posX)

        return self.blend(position=position, block=self.shadow_block, shadow=True) or self.matrix
        # If the blend isn't successful just return the old matrix. The blend will fail later in self.update, it's game over.

    def fits_in_matrix(self, shape, position):
        posY, posX = position
        for x in range(posX, posX+len(shape)):
            for y in range(posY, posY+len(shape)):
                if self.matrix.get((y, x), False) is False and shape[y-posY][x-posX]: # outside matrix
                    return False

        return position
                    

    def request_rotation(self):
        rotation = (self.tetromino_rotation + 1) % 4
        shape = self.rotated(rotation)

        y, x = self.tetromino_position

        position = (self.fits_in_matrix(shape, (y, x)) or
                    self.fits_in_matrix(shape, (y, x+1)) or
                    self.fits_in_matrix(shape, (y, x-1)) or
                    self.fits_in_matrix(shape, (y, x+2)) or
                    self.fits_in_matrix(shape, (y, x-2)))
        # ^ Thats how wall-kick is implemented
        
        log(TRIGGER_ROTATE,self.matrix)

        if position and self.blend(shape, position):
            self.tetromino_rotation = rotation
            self.tetromino_position = position
            return self.tetromino_rotation
        else:
            return False
            
    def request_movement(self, direction):
        posY, posX = self.tetromino_position
        if direction == 'left' and self.blend(position=(posY, posX-1)):
            self.tetromino_position = (posY, posX-1)
            return self.tetromino_position
        elif direction == 'right' and self.blend(position=(posY, posX+1)):
            self.tetromino_position = (posY, posX+1)
            return self.tetromino_position
        elif direction == 'up' and self.blend(position=(posY-1, posX)):
            self.tetromino_position = (posY-1, posX)
            return self.tetromino_position
        elif direction == 'down' and self.blend(position=(posY+1, posX)):
            self.tetromino_position = (posY+1, posX)
            return self.tetromino_position
        else:
            return False

    def rotated(self, rotation=None):
        if rotation is None:
            rotation = self.tetromino_rotation
        return rotate(self.current_tetromino.shape, rotation)

    def block(self, color, shadow=False):
        colors = {'blue':   (27, 34, 224),
                  'yellow': (225, 242, 41),
                  'pink':   (242, 41, 195),
                  'green':  (22, 181, 64),
                  'red':    (204, 22, 22),
                  'orange': (245, 144, 12),
                  'cyan':   (10, 255, 226)}


        if shadow:
            end = [40] # end is the alpha value
        else:
            end = [] # Adding this to the end will not change the array, thus no alpha value

        border = Surface((self.blocksize, self.blocksize), pygame.SRCALPHA, 32)
        border.fill(map(lambda c: c*0.5, colors[color]) + end)

        borderwidth = 2

        box = Surface((self.blocksize-borderwidth*2, self.blocksize-borderwidth*2), pygame.SRCALPHA, 32)
        boxarr = pygame.PixelArray(box)
        for x in range(len(boxarr)):
            for y in range(len(boxarr)):
                boxarr[x][y] = tuple(map(lambda c: min(255, int(c*random.uniform(0.8, 1.2))), colors[color]) + end) 

        del boxarr # deleting boxarr or else the box surface will be 'locked' or something like that and won't blit.
        border.blit(box, Rect(borderwidth, borderwidth, 0, 0))


        return border

    def lock_tetromino(self):
        self.matrix = self.blend()
        log(TRIGGER_PLACE_BLOCK, self.matrix)
        
        lines_cleared = self.remove_lines()
        self.lines += lines_cleared

        if lines_cleared:
            if lines_cleared >= 4:
                log(TRIGGER_REMOVE_4_LINES, self.matrix)
                self.linescleared_sound.play()
            else:
                log(lines_cleared-1, self.matrix)
                self.linescleared_sound.play()
            self.score += 100 * (lines_cleared**2) * self.combo

            if not self.played_highscorebeaten_sound and self.score > self.highscore:
                if self.highscore != 0:
                    self.highscorebeaten_sound.play()
                self.played_highscorebeaten_sound = True

        if self.lines >= self.level*10:
            self.levelup_sound.play()
            self.level += 1

        self.combo = self.combo + 1 if lines_cleared else 1

        self.set_tetrominoes()
        
        #write to game_state
        global game_state_lock
        game_state_lock.acquire()
        #print 'speed:', str(self.matris.base_downwards_speed)
        try:
            global game_state
            #print 'game speed_change', str(speed_change)
            game_state = copy.deepcopy(self.matrix)
        except:
            print "Unexpected error:", sys.exc_info()[0]
            raise
        finally:
            game_state_lock.release()

    def remove_lines(self):
        lines = []
        for y in range(self.size['height']):
            line = (y, [])
            for x in range(self.size['width']):
                if self.matrix[(y,x)]:
                    line[1].append(x)
            if len(line[1]) == self.size['width']:
                lines.append(y)

        for line in sorted(lines):
            for x in range(self.size['width']):
                self.matrix[(line,x)] = None
            for y in range(0, line+1)[::-1]:
                for x in range(self.size['width']):
                    self.matrix[(y,x)] = self.matrix.get((y-1,x), None)

        return len(lines)

    def blend(self, shape=None, position=None, matrix=None, block=None, allow_failure=True, shadow=False):
        if shape is None:
            shape = self.rotated()
        if position is None:
            position = self.tetromino_position

        copy = dict(self.matrix if matrix is None else matrix)
        posY, posX = position
        for x in range(posX, posX+len(shape)):
            for y in range(posY, posY+len(shape)):
                if (copy.get((y, x), False) is False and shape[y-posY][x-posX] # shape is outside the matrix
                    or # coordinate is occupied by something else which isn't a shadow
                    copy.get((y,x)) and shape[y-posY][x-posX] and copy[(y,x)][0] != 'shadow'): 
                    if allow_failure:
                        return False
                    else:
                        raise BrokenMatrixException("Tried to blend a broken matrix. This should mean game over, if you see this it is certainly a bug. (or you are developing)")
                elif shape[y-posY][x-posX] and not shadow:
                    copy[(y,x)] = ('block', self.tetromino_block if block is None else block)
                elif shape[y-posY][x-posX] and shadow:
                    copy[(y,x)] = ('shadow', block)

        return copy

    def construct_surface_of_next_tetromino(self):
        shape = self.next_tetromino.shape
        surf = Surface((len(shape)*self.blocksize, len(shape)*self.blocksize), pygame.SRCALPHA, 32)

        for y in range(len(shape)):
            for x in range(len(shape)):
                if shape[y][x]:
                    surf.blit(self.block(self.next_tetromino.color), (x*self.blocksize, y*self.blocksize))
        return surf

    def unstuck_keys(self):
        #methods for releasing keys
        self.movement_keys['left'] = 0
        self.movement_keys['right'] = 0
        self.movement_keys_timer = (-self.movement_keys_speed)*2

class Game(object):

    def __init__(self,screen,base_downwards_speed,difficulty_assessment, difficulty_assessment_obj=None,time_passed=0, relaxation=False, dda=False):
        self.clock = pygame.time.Clock()
        self.time_passed_since_last_self_report = time_passed #the actual time passed since start in seconds
        self.time_passed_since_last_difficulty_check = time_passed
        self.time_passed_relaxation = time_passed
        self.background = Surface(screen.get_size())
        self.relaxation = relaxation
        self.relaxation_screen = RelaxationScreen(screen)
        self.switch_sequence = False
        self.dda = dda

        self.background.blit(construct_nightmare(self.background.get_size()), (0,0))
        self.selfreport = False
        self.matris = Matris()
        self.matris_border = Surface((MATRIX_WIDTH*BLOCKSIZE+BORDERWIDTH*2, VISIBLE_MATRIX_HEIGHT*BLOCKSIZE+BORDERWIDTH*2))
        self.matris_border.fill(BORDERCOLOR)
        self.matris.screen = screen
        self.difficulty_assessment = difficulty_assessment
        self.difficulty_assessment_obj = difficulty_assessment_obj
        
        log(TRIGGER_RELAX, self.matris.matrix)
        #set base_downwards_speed
        self.matris.base_downwards_speed = base_downwards_speed
        if difficulty_assessment and hasattr(self.difficulty_assessment_obj, 'get_speed()'):
            self.matris.base_downwards_speed = self.difficulty_assessment_obj.get_speed()
        global db
        if db.closed:
            db = open('log.pickle', 'wb')
        log(TRIGGER_GAME_START, self.matris.matrix)

    def main(self, screen,base_downwards_speed = 0.4,difficulty_assessment = False, difficulty_assessment_obj=None,relaxation = False,experiment1=False, dda=False):
        if experiment1:
            #setup test sequence
            self.test_sequence = ['easy','medium','hard']*EXPERIMENT_1_SEQUENCES
            random.shuffle(self.test_sequence)
            self.switch_sequence = False
        self.dda=dda
        self.__init__(screen,base_downwards_speed,difficulty_assessment, difficulty_assessment_obj, self.relaxation,dda=self.dda)
        #this is a hack! WHY IS THE ABOVE FUNCTION ALWAYS SETTING RELAXATION TO ITS DEFAULT VALUE
        self.relaxation = relaxation
        self.paused = False
        
        while 1:
            #FPS
            dt = self.clock.tick(FPS)
            
            if self.paused:
                self.surface = pygame.Surface((WIDTH, HEIGHT))
                self.surface.fill((255,255,255,255))
                screen.blit(self.surface, (0,0)) 
                font = pygame.font.Font(None,48)
                text = font.render('Pause',1,(0,0,0))
                textpos = text.get_rect(centerx=screen.get_width()/2, centery=screen.get_height()/2)
                screen.blit(text,textpos)
                text = font.render('Press p to unpause',1,(0,0,0))
                textpos = text.get_rect(centerx=screen.get_width()/2, centery=screen.get_height()/2+48+6)
                screen.blit(text,textpos)
                pygame.display.update()
                pygame.display.flip()
                for event in pygame.event.get():
                    keys = pygame.key.get_pressed()
                    if keys[pygame.K_p]:
                        self.paused = False
                    elif event.type == pygame.QUIT:
                        pygame.quit()
                  
            elif not self.selfreport and not self.relaxation:
                self.time_passed_since_last_self_report = self.time_passed_since_last_self_report + ((dt / 1000.) if not self.matris.paused else 0)
                self.time_passed_since_last_difficulty_check = self.time_passed_since_last_difficulty_check + ((dt / 1000.) if not self.matris.paused else 0)
                
                #print "time_passed_since_last_self_report " + str(self.time_passed_since_last_self_report)
                
                self.matris.update((dt / 1000.) if not self.matris.paused else 0)
                if self.matris.gameover and not continuous_game:
                    return
                elif self.matris.gameover and continuous_game:
                    if not experiment1:
                        #reset all!
                        
                        self.__init__(screen, base_downwards_speed,difficulty_assessment, self.difficulty_assessment_obj,time_passed=self.time_passed_since_last_self_report, dda=self.dda)
                    else:
                        if hasattr(self, 'current_speed'):
                            if self.current_speed == 'easy':
                                self.__init__(screen, self.easy_speed , difficulty_assessment=False, difficulty_assessment_obj=None, time_passed=self.time_passed_since_last_self_report, relaxation=True)
                            elif self.current_speed == 'medium':
                                self.__init__(screen, self.medium_speed , difficulty_assessment=False, difficulty_assessment_obj=None, time_passed=self.time_passed_since_last_self_report, relaxation=True)
                            elif self.current_speed == 'hard':
                                self.__init__(screen, self.hard_speed, difficulty_assessment=False, difficulty_assessment_obj=None, time_passed=self.time_passed_since_last_self_report, relaxation=True)
                        else:
                            self.__init__(screen, self.matris.base_downwards_speed,self.difficulty_assessment, self.difficulty_assessment_obj,time_passed=self.time_passed_since_last_self_report)
                if self.switch_sequence and not self.difficulty_assessment and experiment1:
                    if len(self.test_sequence)%EXPERIMENT_1_SEQUENCES==0:
                        #pause
                        print 'set pause', len(self.test_sequence)
                        self.paused = True
                    if len(self.test_sequence)>0:
                        self.current_speed = self.test_sequence.pop()
                    else:
                        return
                    if len(self.test_sequence)+1%EXPERIMENT_1_SEQUENCES==0:
                        #pause
                        print 'set pause', len(self.test_sequence)
                        self.paused = True
        
                    if self.current_speed == 'easy':
                        self.__init__(screen, self.easy_speed , difficulty_assessment=False, difficulty_assessment_obj=None, time_passed=0, relaxation=True)
                    elif self.current_speed == 'medium':
                        self.__init__(screen, self.medium_speed , difficulty_assessment=False, difficulty_assessment_obj=None, time_passed=0, relaxation=True)
                    elif self.current_speed == 'hard':
                        self.__init__(screen, self.hard_speed, difficulty_assessment=False, difficulty_assessment_obj=None, time_passed=0, relaxation=True)
                    self.switch_sequence = False
    
                self.tricky_centerx = WIDTH-(WIDTH-(MATRIS_OFFSET+BLOCKSIZE*MATRIX_WIDTH+BORDERWIDTH*2))/2
    
                self.background.blit(self.matris_border, (MATRIS_OFFSET,MATRIS_OFFSET))
                self.background.blit(self.matris.surface, (MATRIS_OFFSET+BORDERWIDTH, MATRIS_OFFSET+BORDERWIDTH))
    
                self.nextts = self.next_tetromino_surf(self.matris.surface_of_next_tetromino)
                self.background.blit(self.nextts, self.nextts.get_rect(top=MATRIS_OFFSET, centerx=self.tricky_centerx))
    
                self.infos = self.info_surf()
                self.background.blit(self.infos, self.infos.get_rect(bottom=HEIGHT-MATRIS_OFFSET, centerx=self.tricky_centerx))
    
    
                screen.blit(self.background, (0, 0))
    
                pygame.display.flip()
            elif self.relaxation:
                self.relaxation_screen.update(self.time_passed_relaxation,screen)
                self.time_passed_relaxation = self.time_passed_relaxation + (dt / 1000.) if not self.matris.paused else 0
            else:
                #selfreport
                self.selfreportmenu.update(screen)
                
            if self.relaxation and self.time_passed_relaxation > RELAX_INTERVAL:
                #exit relaxation
                self.relaxation = False
                log(TRIGGER_RESUME, self.matris.matrix)
                
            if self.time_passed_since_last_difficulty_check > DDA_DIFFICULTY_CHANGE_INTERVAL and self.dda and not self.difficulty_assessment:
                #playing normally with dda
                global speed_lock
                speed_lock.acquire()
                #print 'speed:', str(self.matris.base_downwards_speed)
                try:
                    global speed_change
                    print 'game speed_change', str(speed_change)
                    #if abs(speed_change) > SPEED_THRESHOLD:
                    #change speed
                    if speed_change < 0:
                        #negative speed_change = decrease speed
                        if (self.matris.base_downwards_speed - speed_change) < 0.400:
                            self.matris.base_downwards_speed = self.matris.base_downwards_speed - speed_change
                            print 'slower!', str(self.matris.base_downwards_speed)
                    elif speed_change > 0:
                        #postive speed_change = increase speed
                        if (self.matris.base_downwards_speed - speed_change) > 0.1:
                            #sanity check
                            self.matris.base_downwards_speed = self.matris.base_downwards_speed - speed_change
                            print 'faster!', str(self.matris.base_downwards_speed)
                    else:
                        print 'speed', str(self.matris.base_downwards_speed)
                    #reset speed_change
                    speed_change = 0.0
                except:
                    print "Unexpected error:", sys.exc_info()[0]
                    raise
                finally:
                    speed_lock.release()
                #print 'speed:', str(self.matris.base_downwards_speed)
                
            if self.time_passed_since_last_difficulty_check > DIFFICULTY_CHANGE_INTERVAL and self.difficulty_assessment:
                self.matris.base_downwards_speed = self.difficulty_assessment_obj.get_speed()
                global optimal_speed
                if optimal_speed != -1:
                    #optimal speed is set so continue experiment 1:
                    self.medium_speed = optimal_speed
                    self.easy_speed = optimal_speed+SPEED_LEVELS*(SPEED_INTERVALS/1000.0)
                    self.hard_speed = optimal_speed-SPEED_LEVELS*(SPEED_INTERVALS/1000.0)
                    #print self.easy_speed, self.medium_speed, self.hard_speed
                    if self.hard_speed <0.025:
                        self.hard_speed = 0.025
                    current_speed = self.test_sequence.pop()
                    #print current_speed
                    if current_speed == 'easy':
                        self.__init__(screen, self.easy_speed , difficulty_assessment=False, difficulty_assessment_obj=None, time_passed=0, relaxation=True)
                    elif current_speed == 'medium':
                        self.__init__(screen, self.medium_speed , difficulty_assessment=False, difficulty_assessment_obj=None, time_passed=0, relaxation=True)
                    elif current_speed == 'hard':
                        self.__init__(screen, self.hard_speed, difficulty_assessment=False, difficulty_assessment_obj=None, time_passed=0, relaxation=True)
                    self.paused = True
                    log(TRIGGER_BEGIN_EXPERIMENT, self.matris.matrix)
                self.time_passed_since_last_difficulty_check = 0
                
            if self.time_passed_since_last_self_report > SELF_REPORT_INTERVAL and not self.difficulty_assessment:
                #initalize menu
                #print 'selfreport'
                self.selfreportmenu = SelfReportMenu(screen,self,'selfreport')
                self.selfreportmenu.update(screen)
        
                self.selfreport = not self.selfreport
                #reset time
                self.time_passed_since_last_self_report = 0
            elif self.time_passed_since_last_self_report > SELF_DIFFICULTY_ASSESSMENT_INTERVAL and self.difficulty_assessment:
                #initalize menu
                #print 'difficulty assessment'
                self.selfreportmenu = SelfReportMenu(screen,self,'difficulty_assessment')
                self.selfreportmenu.update(screen)
        
                self.selfreport = not self.selfreport

                #reset time
                self.time_passed_since_last_self_report = 0
           
                
    def info_surf(self):

        textcolor = (255, 255, 255)
        font = pygame.font.Font(None, 30)
        width = (WIDTH-(MATRIS_OFFSET+BLOCKSIZE*MATRIX_WIDTH+BORDERWIDTH*2)) - MATRIS_OFFSET*2

        def renderpair(text, val):
            text = font.render(text, True, textcolor)
            val = font.render(str(val), True, textcolor)

            surf = Surface((width, text.get_rect().height + BORDERWIDTH*2), pygame.SRCALPHA, 32)

            surf.blit(text, text.get_rect(top=BORDERWIDTH+10, left=BORDERWIDTH+10))
            surf.blit(val, val.get_rect(top=BORDERWIDTH+10, right=width-(BORDERWIDTH+10)))
            return surf

        scoresurf = renderpair("Score", self.matris.score)
        levelsurf = renderpair("Level", self.matris.level)
        linessurf = renderpair("Lines", self.matris.lines)
        combosurf = renderpair("Combo", "x{}".format(self.matris.combo))

        height = 20 + (levelsurf.get_rect().height + 
                       scoresurf.get_rect().height +
                       linessurf.get_rect().height + 
                       combosurf.get_rect().height )

        area = Surface((width, height))
        area.fill(BORDERCOLOR)
        area.fill(BGCOLOR, Rect(BORDERWIDTH, BORDERWIDTH, width-BORDERWIDTH*2, height-BORDERWIDTH*2))

        area.blit(levelsurf, (0,0))
        area.blit(scoresurf, (0, levelsurf.get_rect().height))
        area.blit(linessurf, (0, levelsurf.get_rect().height + scoresurf.get_rect().height))
        area.blit(combosurf, (0, levelsurf.get_rect().height + scoresurf.get_rect().height + linessurf.get_rect().height))

        return area

    def next_tetromino_surf(self, tetromino_surf):
        area = Surface((BLOCKSIZE*5, BLOCKSIZE*5))
        area.fill(BORDERCOLOR)
        area.fill(BGCOLOR, Rect(BORDERWIDTH, BORDERWIDTH, BLOCKSIZE*5-BORDERWIDTH*2, BLOCKSIZE*5-BORDERWIDTH*2))

        areasize = area.get_size()[0]
        tetromino_surf_size = tetromino_surf.get_size()[0]
        # ^^ I'm assuming width and height are the same

        center = areasize/2 - tetromino_surf_size/2
        area.blit(tetromino_surf, (center, center))

        return area

class Menu(object):
    running = True
    changed_menu = False
  

    def main(self, screen):
        clock = pygame.time.Clock()
        
        def shut_down():
            if not db.closed:
                db.close()
            self.running = False
            
        def start_game(screen,speed, difficulty_assessment=False,experiment_1=False,dda=False):
            if difficulty_assessment:
                self.difficulty_assessment_obj = DifficultyAssessment(self, bool(random.getrandbits(1)))
                Game(screen,speed,difficulty_assessment,self.difficulty_assessment_obj,relaxation = True).main(screen, speed,difficulty_assessment,self.difficulty_assessment_obj,relaxation = True,experiment1=experiment_1)
            else:
                Game(screen,speed,difficulty_assessment,None,dda=dda).main(screen, speed,difficulty_assessment,None,dda=dda)
    
        global optimal_speed
        menu = kezmenu.KezMenu(
            ['Play! ({0}ms)'.format(MEDIUM_SPEED*1000), lambda: start_game(screen, MEDIUM_SPEED)],
            ['DDA version', lambda: start_game(screen,MEDIUM_SPEED,dda=True)],
            ['Experiment 1', lambda: start_game(screen, MEDIUM_SPEED, True,True)],
            ['Difficulty assessment', lambda:start_game(screen,MEDIUM_SPEED,True)],
            ['Quit', lambda: shut_down()],
        )
            
        menu.position = (50, 50)
        menu.enableEffect('enlarge-font-on-focus', font=None, size=60, enlarge_factor=1.2, enlarge_time=0.3)
        menu.color = (255,255,255)
        menu.focus_color = (40, 200, 40)

        nightmare = construct_nightmare(screen.get_size())
        highscoresurf = self.construct_highscoresurf()

        timepassed = clock.tick(30) / 1000.
        

        while self.running:
            events = pygame.event.get()

            for event in events:
                if event.type == pygame.QUIT:
                    #close file 
                    db.close()
                    print 'file closed'
                    exit()

            menu.update(events, timepassed)

            timepassed = clock.tick(30) / 1000.

            if timepassed > 1: # A game has most likely been played 
                highscoresurf = self.construct_highscoresurf()

            screen.blit(nightmare, (0,0))
            screen.blit(highscoresurf, highscoresurf.get_rect(right=WIDTH-50, bottom=HEIGHT-50))
            menu.draw(screen)
            pygame.display.flip()

    def construct_highscoresurf(self):
        font = pygame.font.Font(None, 50)
        highscore = load_score()
        text = "Highscore: {}".format(highscore)
        return font.render(text, True, (255,255,255))

def construct_nightmare(size):
    surf = Surface(size)

    boxsize = 8
    bordersize = 1
    vals = '1235' # only the lower values, for darker colors and greater fear
    arr = pygame.PixelArray(surf)
    for x in xrange(0, len(arr), boxsize):
        for y in xrange(0, len(arr[x]), boxsize):

            color = int(''.join([random.choice(vals) + random.choice(vals) for _ in range(3)]), 16)

            for LX in xrange(x, x+(boxsize - bordersize)):
                for LY in xrange(y, y+(boxsize - bordersize)):
                    if LX < len(arr) and LY < len(arr[x]):
                        arr[LX][LY] = color
    del arr
    return surf

def analyse_game_state(game_state, last_game_state, speed_change):
    '''
    Analyses game state in comparison to the last game state
    '''
    
    #game states
    last_state = convert_game_state_to_array(last_game_state)
    current_state = convert_game_state_to_array(game_state)
    if game_state != None and last_game_state != None:
        #game heights
        last_height = get_max_height(last_state)
        current_height = get_max_height(current_state)
        delta_height = last_height-current_height
        print last_height,current_height, delta_height
        
        if delta_height < 0 and current_height > 10:
            speed_change = -0.05
        elif delta_height > 0 and current_height < 7:
            speed_change = 0.025
        elif delta_height > 2:
            speed_change = 0.025
        print speed_change
    return speed_change

def get_max_height(game_state):
    '''
    Returns stats
    '''
    height = 0
    for i in reversed(range(22)):
        if any(game_state[i]):
            height = 22-i
    return height

def convert_game_state_to_array(game_state):
    '''
    Convert game state to multidimensional array. Game state is a dict with (x,y) tuple as key
    '''
    tetris_array = [None] * 22
    if game_state != None:
        for i in range(len(tetris_array)):
            tetris_array[i] = [None]*10
        for key,value in game_state.iteritems():
            if value is None:
                tetris_array[key[0]][key[1]] = False
            else:
                tetris_array[key[0]][key[1]] = True
    return tetris_array

def calculate_heart_rate(data,time):
    '''
    Will calculate heart rate from an array of numbers and timestamps for each number. Based on r-r interval
    '''
    data = scipy.signal.detrend(data)
    
    
    #calculates ALL peaks and finds average from the peaks
    if len(data) != len(time):
        print 'something is clearly wrong. The data should be same size as the time (in calculate_heart_rate)'
    peaks = []
    
    #peak detection
    res = 5
    for i in range(res, len(data)-res):
        if data[i]>data[i-res]+.1 and data[i]>data[i+res]+.1:  
            if data[i]>data[i-1] and data[i]>data[i+1]:  
                peaks.append((data[i],time[i],i)) #(value,time,index)
    
    
    
    r_peaks = []
    #having all peaks now - the filtering begins! All r-peaks have a corresponding t-peak
    for i in range(0,len(peaks),2):
        if (i+1)<len(peaks):
            if peaks[i][0] > peaks[i+1][0]:
                r_peaks.append(peaks[i])
            else:
                r_peaks.append(peaks[i+1])
    
    
    #r_peaks found, calculating heart rate between peaks
    heart_rates = []
    for i in range(0,len(r_peaks)):
        if (i+1)<len(r_peaks):
            #within bounds
            try:
                heart_rate = (1.0/(r_peaks[i+1][1]-r_peaks[i][1]))*60
                if heart_rate < 200 and heart_rate >50:
                    heart_rates.append((heart_rate,r_peaks[i][1],r_peaks[i][2]))
            except:
                print 'division by zero'
    #fill array with heart rates
    heart_rate = []
    if heart_rates == []:
        heart_rate.append(0.0)
    else:
        current_hr = heart_rates[0][0]
        for i in range(len(time)):
            for hr in heart_rates:
                if i==hr[2]:
                    current_hr = hr[0]
                    break
            heart_rate.append(current_hr)
    '''
    #plot hr
    plt.subplot(2,1,1)
    plt.plot(time,data)
    peak_x = [t for (peak,t,index) in r_peaks]
    peak_y = [peak for (peak,t,index) in r_peaks]
    plt.plot(peak_x,peak_y,'rx')
    plt.ylabel('uV')
    plt.subplot(2,1,2)

    plt.plot(time,heart_rate)
    plt.ylabel('bpm')
    plt.show()
    '''
    return heart_rate

class dda(threading.Thread):
    def __init__(self,conn, perf_dda = True):
        '''
        Constructor for dda.
        conn is a tcp connection
        perf_dda is True if performance based DDA is to be used, False assumes conn to not be None and emotion based DDA to be used
        '''
        super(dda,self).__init__()
        self.conn = conn
        self.data = ""
        self.time_start = time.time()
        self.perf_dda = perf_dda
        self.speed_change = 0.0 # in s
        self.channels_in_array = 16
        self.tcp_samples = 1
        self.bytes_in_array = self.channels_in_array*self.tcp_samples
        self.signals = [] #!list of samples! one entry = one sample and NOT a signal. Convert to numpy array later to take a column
        self.last_game_state = None
        self.init_stepsize = 0.05
        self.stepsize_multiplier = 1
        self.last_direction_raise = True # if true then last direction was raising speed
        self.baseline = 0.0 #heart rate baseline
        self.upper_limit = 5.0 #heart rate over baseline - for being aroused to too aroused
        self.lower_limit = 3.0 #heart rate over baseline - for being too little aroused (coming from high arousal)
        
        if not perf_dda:
            # record baseline
            self.time = int(time.time()-self.time_start)
            self.samples = []
            while self.time < 60: #get 1 minute of measurements for heart rate baseline
                self.data = self.conn.recv(self.channels_in_array*self.tcp_samples*3)
                self.samples.append(struct.unpack('<i', self.data[39:42] +('\0' if self.data[42] < '\x80' else '\xff'))) #bvp
                self.signals.append(self.samples)
                self.samples = []
                self.time = int(time.time()-self.time_start)
            signal = [sample[0] for sample in self.signals]
            t = [1.0/128.0*i for i in range(len(signal))]
            self.baseline = calculate_heart_rate(signal, t)
            
        
    def run(self):
        self.time = int(time.time()-self.time_start)
        self.samples = []
        while True:
            if self.perf_dda:
                time.sleep(1)
                
                #read matrix state
                global game_state_lock
                game_state_lock.acquire()
                
                try:
                    global game_state
                    self.speed_change = analyse_game_state(game_state, self.last_game_state, self.speed_change)
                    self.last_game_state = game_state
                except:
                    print "Unexpected error:", sys.exc_info()[0]
                    raise
                finally:
                    game_state_lock.release()
            else:
                self.data = self.conn.recv(self.channels_in_array*self.tcp_samples*3) #data is a string!
                #print ord(self.data[42]), len(self.data), type(self.data)
                #print struct.unpack('<i', self.data[39:42] +('\0' if self.data[42] < '\x80' else '\xff'))
                #self.samples.append(struct.unpack('<i', self.data[0:3] +('\0' if self.data[3] < '\x80' else '\xff'))) #emg1
                #self.samples.append(struct.unpack('<i', self.data[3:6] +('\0' if self.data[6] < '\x80' else '\xff'))) #emg2
                #self.samples.append(struct.unpack('<i', self.data[6:9] +('\0' if self.data[9] < '\x80' else '\xff'))) #emg3
                #self.samples.append(struct.unpack('<i', self.data[9:12] +('\0' if self.data[12] < '\x80' else '\xff'))) #emg4
                #self.samples.append(struct.unpack('<i', self.data[24:27] +('\0' if self.data[27] < '\x80' else '\xff'))) #gsr
                self.samples.append(struct.unpack('<i', self.data[39:42] +('\0' if self.data[42] < '\x80' else '\xff'))) #bvp
                self.signals.append(self.samples)
                self.samples = []
                    
                    
            
            #timekeeping
            self.time = int(time.time()-self.time_start)
            
            
            
            if self.time > 1 and self.perf_dda:
                if not self.perf_dda:
                    #Start analysing 5 second signal:
                    signal = [sample[0] for sample in self.signals]
                    t = [1.0/128.0*i for i in range(len(signal))]
                    hr = calculate_heart_rate(signal, t)
                    average_hr = np.average(hr)
                    if average_hr < self.baseline:
                        #raise speed
                        if self.last_direction_raise:
                            self.stepsize_multiplier = self.stepsize_multiplier+1
                            self.speed_change = self.init_stepsize*self.stepsize_multiplier
                        else:
                            self.stepsize_multiplier = 1 #reset
                            self.speed_change = -self.init_stepsize*self.stepsize_multiplier
                            
                    elif average_hr > self.baseline and average_hr < (self.baseline+self.lower_limit):
                        #raise speed
                        if self.last_direction_raise:
                            self.stepsize_multiplier = self.stepsize_multiplier+1
                            self.speed_change = self.init_stepsize*self.stepsize_multiplier
                        else:
                            self.stepsize_multiplier = 1 #reset
                            self.speed_change = -self.init_stepsize*self.stepsize_multiplier
                    elif average_hr > (self.baseline+self.upper_limit):
                        #lower speed
                        if not self.last_direction_raise:
                            self.stepsize_multiplier = self.stepsize_multiplier+1
                            self.speed_change = -self.init_stepsize*self.stepsize_multiplier
                        else:
                            self.stepsize_multiplier = 1 #reset
                            self.speed_change = self.init_stepsize*self.stepsize_multiplier
                    else:
                        #maintain speed
                        self.speed_change = 0.0
                        
                    self.signals = []
                global speed_lock
                speed_lock.acquire()
                try:
                    global speed_change
                    speed_change = self.speed_change
                    self.speed_change = 0.0
                    print 'changed speed_change', str(speed_change)
                except:
                    print "Unexpected error:", sys.exc_info()[0]
                    raise
                finally:
                    speed_lock.release()
                self.time= 0.0
                self.time_start = time.time()
            
            if self.time > 5 and not self.perf_dda:
                if not self.perf_dda:
                        #Start analysing 5 second signal:
                        signal = [sample[0] for sample in self.signals]
                        t = [1.0/128.0*i for i in range(len(signal))]
                        hr = calculate_heart_rate(signal, t)
                        average_hr = np.average(hr)
                        if average_hr < self.baseline:
                            #raise speed
                            if self.last_direction_raise:
                                self.stepsize_multiplier = self.stepsize_multiplier+1
                                self.speed_change = self.init_stepsize*self.stepsize_multiplier
                            else:
                                self.stepsize_multiplier = 1 #reset
                                self.speed_change = -self.init_stepsize*self.stepsize_multiplier
                                
                        elif average_hr > self.baseline and average_hr < (self.baseline+self.lower_limit):
                            #raise speed
                            if self.last_direction_raise:
                                self.stepsize_multiplier = self.stepsize_multiplier+1
                                self.speed_change = self.init_stepsize*self.stepsize_multiplier
                            else:
                                self.stepsize_multiplier = 1 #reset
                                self.speed_change = -self.init_stepsize*self.stepsize_multiplier
                        elif average_hr > (self.baseline+self.upper_limit):
                            #lower speed
                            if not self.last_direction_raise:
                                self.stepsize_multiplier = self.stepsize_multiplier+1
                                self.speed_change = -self.init_stepsize*self.stepsize_multiplier
                            else:
                                self.stepsize_multiplier = 1 #reset
                                self.speed_change = self.init_stepsize*self.stepsize_multiplier
                        else:
                            #maintain speed
                            self.speed_change = 0.0
                            
                        self.signals = []
                global speed_lock
                speed_lock.acquire()
                try:
                    global speed_change
                    speed_change = self.speed_change
                    self.speed_change = 0.0
                    print 'changed speed_change', str(speed_change)
                except:
                    print "Unexpected error:", sys.exc_info()[0]
                    raise
                finally:
                    speed_lock.release()
                self.time= 0.0
                self.time_start = time.time()
            
    def close(self):
        self.conn.close()

class game_thread(threading.Thread):
    
    def __init(self):
        
        pass
        
    def run(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        #print WIDTH, HEIGHT
        pygame.display.set_caption("MaTris")
        Menu().main(self.screen)

if __name__ == '__main__':
    '''
    #start listening to tcp port
    try:
        print 'Trying to create socket'
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print 'Trying to bind', HOST, str(PORT)
        s.connect((HOST,PORT))
        #print 'Trying to listen'
        #s.listen(5)
        #print 'Trying to accept'
        #conn, address = s.accept()
        #print 'Trying to create object'
        c = dda(s,perf_dda=False)
    except socket.error, v:
        print 'Failed to create socket', str(v[0])
        s.close()
    '''
    c = dda(None,perf_dda=True)
    g = game_thread()
    thread = threading.Thread(target = c.run)
    thread2 = threading.Thread(target = g.run)
    thread.start()
    thread2.start()
    thread.join()
    thread2.join()
    print 'finished'
    
