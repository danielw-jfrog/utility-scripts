#!/usr/bin/env python3

### IMPORTS ###
import logging
import os
import queue
import random
import requests
import threading
import time
import uuid

### GLOBALS ###
TOTAL_COUNT = int(5000000) # 5 million files
TOTAL_SIZE = int(10000000000000) # 10 terabytes
FILE_MIN_SIZE = int(100000) # 100 kilobytes
FILE_MAX_SIZE = int(10000000000) # 10 gigabytes

TOTAL_COUNT = int(20000)
TOTAL_SIZE = int(20000000000)
FILE_MIN_SIZE = int(100000)
FILE_MAX_SIZE = int(10000000)

NUM_THREADS = 3

POST_URL = "https://artifactory.example.com/artifactory/demo-federated-repo/"
POST_USER = ""
POST_APIKEY = ""

COUNT_RUNNER = 0
SIZE_RUNNER = 0

requests.packages.urllib3.disable_warnings()

### FUNCTIONS ###
def gen_number(total_count, total_size, min_size, max_size):
    global COUNT_RUNNER
    global SIZE_RUNNER

    tmp_target_average = total_size / total_count
    if tmp_target_average < min_size:
        tmp_target_average = min_size
    elif tmp_target_average > max_size:
        tmp_target_average = max_size
    tmp_start_average = int(SIZE_RUNNER / COUNT_RUNNER if COUNT_RUNNER > 0 else 0)
    logging.debug("Average at start: %s after %s generations", tmp_start_average, COUNT_RUNNER)

    tmp_remain = total_size - SIZE_RUNNER
    tmp_max = tmp_remain if tmp_remain < max_size else max_size
    logging.debug("tmp_remain: %s, tmp_max: %s", tmp_remain, tmp_max)

    tmp_rando = 0
    if tmp_target_average < tmp_start_average:
        logging.debug("  average over target")
        tmp_rando = random.randint(min_size, tmp_start_average)
    elif tmp_target_average > tmp_start_average:
        logging.debug("  average under target")
        tmp_rando = random.randint(tmp_start_average, tmp_max)
    COUNT_RUNNER = int(COUNT_RUNNER + 1)
    SIZE_RUNNER = int(SIZE_RUNNER + tmp_rando)

    tmp_finish_average = SIZE_RUNNER / COUNT_RUNNER
    logging.debug("Average at finish: %s after %s generations", tmp_finish_average, COUNT_RUNNER)

    logging.debug("Random number: %s", tmp_rando)
    return tmp_rando

def gen_numbers(count, total, min_size, max_size):
    # NOTE: The returns a list of numbers with a sum that approaches the "total"
    #       value and has a list length not exceeding the count.  The numbers
    #       will be in the range "min_size" to "max_size" with a weighting
    #       towards the lower end of the range
    logging.info(
        "gen_numbers( count: %s, total: %s, min_size: %s, max_size: %s )",
        count, total, min_size, max_size
    )
    numbers = []
    for i in range(count):
        numbers.append(gen_number(count, total, min_size, max_size))

    # Report on the quality of the numbers
    tmp_sum = 0
    for i in numbers:
        tmp_sum = tmp_sum + i
    tmp_avg = tmp_sum / len(numbers)
    tmp_mode = TOTAL_SIZE / TOTAL_COUNT
    logging.info("Target Count: %s, Count: %s", TOTAL_COUNT, len(numbers))
    logging.info("Target Sum: %s, Sum: %s, ratio: %s", TOTAL_SIZE, tmp_sum, tmp_sum / TOTAL_SIZE)
    logging.info("Target Avg: %s, Avg: %s", tmp_mode, tmp_avg)

    tmp_lower = FILE_MIN_SIZE
    tmp_upper = FILE_MIN_SIZE * 10
    tmp_pop = []
    while tmp_lower < FILE_MAX_SIZE:
        tmp_pop.append(tmp_lower)
        tmp_lower = tmp_upper
        tmp_upper = tmp_lower * 10
    logging.debug("  tmp_pop: %s", tmp_pop)
    tmp_bins = {}
    for i in tmp_pop:
        tmp_bins["{}".format(i)] = 0
    for i in numbers:
        for j in range(len(tmp_pop)):
            if i > tmp_pop[j] and i < (tmp_pop[j] * 10): # i < tmp_pop[j+1]:
                tmp_bins["{}".format(tmp_pop[j])] = tmp_bins["{}".format(tmp_pop[j])] + 1
    logging.info("Binning: %s", tmp_bins)

    return numbers

def gen_file_metas(list_sizes):
    # Generate the file information
    #   - UUID4 (to help prevent collisions)
    #   - path (currently depth of 5, so 4 dirs + filename)
    #   - size
    logging.debug("gen_file_metas( list_sizes: [%s] )", len(list_sizes))
    files = []
    for tmp_size in list_sizes:
        tmp_file = { 'uuid': uuid.uuid4(), 'size': tmp_size, }
        tmp_file['path'] = "{}/{}/{}/{}/{}/{}.bin;env=dev;uploader=danielw;shortsha={}".format(
            tmp_file['uuid'].hex[0:2],
            tmp_file['uuid'].hex[2:4],
            tmp_file['uuid'].hex[4:6],
            tmp_file['uuid'].hex[6:8],
            tmp_file['uuid'].hex[8:10],
            tmp_file['uuid'].hex,
            tmp_file['uuid'].hex[-8:]
        )
        files.append(tmp_file)
    logging.info("  Number of paths generated: %s", len(files))
    return files

### CLASSES ###
class RandomDataGenerator:
    def __init__(self, size):
        self.logger = logging.getLogger(type(self).__name__)
        self.size = int(size)
        self.len = self.size # Attribute that requests uses to check length of the body
        self.remaining = self.size

    def __iter__(self):
        return self

    def __next__(self):
        return self.next()

    def next(self):
        if self.remaining > 0:
            self.remaining = self.remaining - 1
            return os.urandom(1)
        raise StopIteration()

    def read(self, size = -1):
        tmp_size = int(size)
        if self.remaining <= 0:
            #raise StopIteration()
            return b''
        if (tmp_size > 0) and (tmp_size < self.remaining):
            self.remaining = self.remaining - tmp_size
            return os.urandom(tmp_size)
        tmp_size = self.remaining
        self.remaining = 0
        return os.urandom(tmp_size)

class FilePoster(threading.Thread):
    def __init__(self, input_queue):
        super().__init__()
        self.logger = logging.getLogger(type(self).__name__)
        self._shutdown = False
        self._input_queue = input_queue
        self.auth = requests.auth.HTTPBasicAuth(POST_USER, POST_APIKEY)
        self.post_count = 0

    def _random_data_generator(self, size):
        # This generates data for streaming to the POST request
        self.logger.debug("_random_data_generator( size: %s )", size)
        tmp_size = int(size)
        while tmp_size > 0:
            tmp_cycle_size = 1024
            if tmp_cycle_size > tmp_size:
                tmp_cycle_size = tmp_size
            tmp_data = os.urandom(tmp_cycle_size)
            tmp_size = tmp_size - tmp_cycle_size
            yield tmp_data
        self.logger.debug("  done generating data")


    def run(self):
        self.logger.debug("Starting the FilePoster thread.")
        while not self._shutdown:
            # Get a file_meta from the queue
            tmp_file_meta = None
            try:
                tmp_file_meta = self._input_queue.get_nowait()
            except queue.Empty:
                self.logger.debug("No more work, shutting down.")
                self.stop()
                break # Force the while loop to end.
            # PUT the file to the repository using the data generator
            tmp_gen = RandomDataGenerator(tmp_file_meta['size'])
            tmp_post_url = POST_URL
            if POST_URL[-1] == '/':
                tmp_post_url = POST_URL[:-1]
            tmp_url = "{}/{}".format(tmp_post_url, tmp_file_meta['path'])
            r = requests.put(tmp_url, auth = self.auth, data = tmp_gen, verify = False)
            self.logger.debug("  requests.put: %s", r)
            self.post_count = self.post_count + 1
            # FIXME: Should log the file_meta here
            # FIXME: Should add some sort of thread ID into the logging lines
            # FIXME: Should probably perform some error handling here.
            # Mark the file_meta complete in the queue
            self._input_queue.task_done()
        self.logger.debug("Ending the FilePoster thread.")

    def stop(self):
        self.logger.debug("Shutting down the FilePoster thread.")
        self._shutdown = True

### MAIN ###
def main():
    logging.basicConfig(
        format = "%(asctime)s:%(levelname)s:%(name)s.%(funcName)s: %(message)s",
        level = logging.INFO
    )

    tmp_file_sizes = gen_numbers(TOTAL_COUNT, TOTAL_SIZE, FILE_MIN_SIZE, FILE_MAX_SIZE)

    tmp_file_metas = gen_file_metas(tmp_file_sizes)

    tmp_queue = queue.Queue()
    for item in tmp_file_metas:
        tmp_queue.put(item)

    tmp_threads = []
    for i in range(NUM_THREADS):
        tmp_threads.append(FilePoster(tmp_queue))
    for tmp_th in tmp_threads:
        tmp_th.start()

    # FIXME: Add CTRL+C handling.

    tmp_post_count = 0
    while tmp_post_count < len(tmp_file_metas):
        time.sleep(15)
        tmp_old_post_count = tmp_post_count
        tmp_post_count = 0
        for i in tmp_threads:
            tmp_post_count = tmp_post_count + i.post_count
        logging.info(
            "Post Count: %s of %s, Rate: %s per minute ( %s per hour )",
            tmp_post_count,
            len(tmp_file_metas),
            (tmp_post_count - tmp_old_post_count) * 4,
            (tmp_post_count - tmp_old_post_count) * 4 * 60
        )

    for tmp_th in tmp_threads:
        tmp_th.join()
    logging.debug("Threads ended.")

if __name__ == "__main__":
    main()
