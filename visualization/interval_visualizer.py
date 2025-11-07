import math
import pygame


class IntervalVisualizer:
    def __init__(self):
        self.__size = (800, 200)
        self.__screen = None
        self.__running = True

        self.__camera = [0, 10]

    def run(self):
        self.__screen = pygame.display.set_mode(self.__size, pygame.DOUBLEBUF)
        while self.__running:
            self.__screen.fill((255, 255, 255))

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.__running = False
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.butt

            pygame.display.update()
