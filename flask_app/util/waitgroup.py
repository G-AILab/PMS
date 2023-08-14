import threading
import multiprocessing
import time
from multiprocessing import Value



class WaitGroup(object):
    """WaitGroup is like Go sync.WaitGroup.

    Without all the useful corner cases.
    """

    def __init__(self):
        self.count = Value('i', 0)
        self.cv = multiprocessing.Condition()

    def add(self, n):
        self.cv.acquire()
        self.count.value += n
        self.cv.release()

    def done(self):
        self.cv.acquire()
        self.count.value -= 1
        if self.count.value == 0:
            self.cv.notify_all()
        self.cv.release()

    def wait(self):
        self.cv.acquire()
        while self.count.value > 0:
            self.cv.wait()
        self.cv.release()

    


if __name__ == "__main__":
    w = WaitGroup()
    def block_task(t):
        w.add(1)
        time.sleep(t)
        w.done()
        print("finished {t}")

    
    for i in range(100):
        multiprocessing.Process(target=block_task, args=(i,)).start()
    print("waiting....")
    w.wait()
    print("done")


