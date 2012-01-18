import time, random

import collectd

collectd.start_threads()
conn = collectd.Connection()

while True:
    conn.some_category.record(some_counter = 1, another_stat = random.random())
    if random.randrange(2):
        conn.coin_stats.record("heads", flips = 1)
    else:
        conn.coin_stats.record("tails", flips = 1)
    
    time.sleep(random.randint(1, 4))
