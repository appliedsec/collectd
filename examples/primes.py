import time
from Queue import Queue
from threading import Thread
from random import normalvariate

import collectd

numbers = Queue()
conn = collectd.Connection()

def is_prime(n):
    for i in xrange(2, n):
        if n % i == 0:
            return False
    return True

def watch_queue():
    while True:
        conn.queue.set_exact(size = numbers.qsize())
        time.sleep(1)

def consumer():
    while True:
        n = numbers.get()
        before = time.time()
        primality = is_prime(n)
        elapsed = time.time() - before
        if primality:
            print n, "is prime"
            conn.consumer.record("prime", count = 1, time = elapsed)
        else:
            print n, "is not prime"
            conn.consumer.record("composite", count = 1, time = elapsed)

def producer():
    while True:
        n = int((time.time() % 30) ** normalvariate(5, 2))
        if n < 2:
            conn.producer.record(too_small = 1)
        elif n > 10 ** 9:
            conn.producer.record(too_big = 1)
        else:
            conn.producer.record(just_right = 1)
            numbers.put(n)
        time.sleep(0.33)

if __name__ == "__main__":
    collectd.start_threads()
    for func in [producer, consumer]:
        t = Thread(target = func)
        t.daemon = True
        t.start()
    
    watch_queue()
