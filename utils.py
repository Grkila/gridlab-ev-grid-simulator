import json
import pickle
import os
from threading import Event, Thread
from time import time, sleep
from functools import wraps

cf = json.load(open('config.json'))


def runtime_counter(timer_msg):
    """Decorator function wrapper for dynamically measuring the execution time of a given function by creating a second
    thread that continuously updates the elapsed time and prints it to the console.
    :param: func (function): The function to be wrapped.
    :return: wrapper (function): The wrapped function."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            def exec_time(msg='Elapsed_time', stop=None):
                start = time()
                while not stop.is_set():
                    elapsed = time() - start
                    print("\r{}: {} seconds".format(msg, int(elapsed)), end="", flush=True)
                    sleep(1)
                print("\n")

            stop_event = Event()
            et_thread = Thread(target=exec_time, kwargs={"msg": timer_msg, "stop": stop_event})
            et_thread.start()
            result = func(*args, **kwargs)
            stop_event.set()
            et_thread.join()
            return result
        return wrapper
    return decorator


def data_p(data, filename):
    with open(filename, 'wb') as file:
        pickle.dump(data, file, protocol=pickle.HIGHEST_PROTOCOL)


def data_un(filename):
    if not os.path.exists(filename):
        return {}
    with open(filename, 'rb') as file:
        return pickle.load(file)


def pad_center(string, length):
    leftpad = int((length - len(string)) / 2)
    padded = ' ' * leftpad + string + ' ' * (length - leftpad - len(string))
    return padded


def mmm(series):
    return {'min': series.min(), 'mean': series.mean(), 'median': series.median(), 'max': series.max()}
