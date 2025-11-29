from proc.proc import Process
from router.router import Router
from threading import Lock, Condition
import time


class ChameleonProcess(Process):
    def __init__(self):
        super().__init__()
