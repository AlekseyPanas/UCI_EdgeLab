import math
import pygame
from util.util import do_intervals_intersect
pygame.init()


class IntervalVisualizer:
    ZOOM_OUT_FACTOR = 0.91
    ZOOM_IN_FACTOR = 1.09

    def __init__(self, intervals: list[tuple[float, float] | tuple[float, float, tuple[int, int, int]]]):
        self.__size = (800, 200)
        self.__screen = None
        self.__running = True

        # Divides intervals into visual slots (so overlapping intervals are shown on different layers)
        self.__binned_intervals = []
        for v in intervals:
            available = False
            for ib in range(len(self.__binned_intervals)):
                b = self.__binned_intervals[ib]
                if all(not do_intervals_intersect(v1[0], v1[1], v[0], v[1]) for v1 in b):
                    available = True
                    self.__binned_intervals[ib].append(v)
                    break
            if not available:
                self.__binned_intervals.append([])
                self.__binned_intervals[-1].append(v)

        min_int = min(v[0] for v in intervals if abs(v[0]) < math.inf)
        max_int = max(v[1] for v in intervals if abs(v[1]) < math.inf)
        self.__camera = [min_int, max_int]

        self.__font = pygame.font.SysFont("Arial", self.__size[1] // 15)

        self.__dragging = None

    def scale_camera_about_center(self, factor: float):
        diff = (self.__camera[1] - self.__camera[0]) / 2
        translate = self.__camera[0] + diff
        self.__camera = [((self.__camera[0] - translate) * factor) + translate, ((self.__camera[1] - translate) * factor) + translate]

    def run(self):
        self.__screen = pygame.display.set_mode(self.__size, pygame.DOUBLEBUF)
        while self.__running:
            pixels_per_unit = self.__size[0] / (self.__camera[1] - self.__camera[0])

            cam = self.__camera
            if self.__dragging is not None:
                drag_diff = (pygame.mouse.get_pos()[0] - self.__dragging) / pixels_per_unit
                cam = [cam[0] - drag_diff, cam[1] - drag_diff]

            self.__screen.fill((255, 255, 255))

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.__running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == pygame.BUTTON_WHEELDOWN:
                        self.scale_camera_about_center(self.ZOOM_IN_FACTOR)
                    elif event.button == pygame.BUTTON_WHEELUP:
                        self.scale_camera_about_center(self.ZOOM_OUT_FACTOR)
                    elif event.button == pygame.BUTTON_LEFT:
                        self.__dragging = pygame.mouse.get_pos()[0]
                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == pygame.BUTTON_LEFT:
                        self.__dragging = None
                        self.__camera = cam

            pygame.draw.line(self.__screen, (0, 0, 0), (0, self.__size[1] // 2), (self.__size[0], self.__size[1] // 2), 1)

            txt_left_bound = self.__font.render(str(round(cam[0], 2)), False, (0, 0, 0))
            txt_right_bound = self.__font.render(str(round(cam[1], 2)), False, (0, 0, 0))

            self.__screen.blit(txt_left_bound, txt_left_bound.get_rect(bottomleft=(0, (self.__size[1] // 2) - 5)))
            self.__screen.blit(txt_right_bound, txt_right_bound.get_rect(bottomright=(self.__size[0], (self.__size[1] // 2) - 5)))

            for ib in range(len(self.__binned_intervals)):
                for i in range(len(self.__binned_intervals[ib])):
                    v = self.__binned_intervals[ib][i]

                    if do_intervals_intersect(v[0], v[1], *cam):
                        v_proj = [max(v[0], cam[0]), min(v[1], cam[1])]
                        if len(v) > 2:
                            v_proj.append(v[2])

                        h = (self.__size[1] // 2) + 2
                        h += ib * 5
                        start = ((v_proj[0] - cam[0]) * pixels_per_unit, h)
                        end = ((v_proj[1] - cam[0]) * pixels_per_unit, h)

                        pygame.draw.line(self.__screen, (255, 0, 0) if len(v_proj) == 2 else v_proj[2], start, end, 2)
                        if v_proj[0] == v[0]:
                            pygame.draw.circle(self.__screen, (0, 0, 0), start, 3)
                        if v_proj[1] == v[1]:
                            pygame.draw.circle(self.__screen, (0, 0, 0), end, 3)


            pygame.display.update()


if __name__ == "__main__":
    vis = IntervalVisualizer([(1, 3), (10, 15), (2, 12, (0, 0, 255)), (-math.inf, 2)])
    vis.run()
