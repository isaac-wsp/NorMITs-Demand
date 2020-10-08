# -*- coding: utf-8 -*-
"""
Created on: Mon August 3 10:04:32 2020
Updated on:

Original author: Ben Taylor
Last update made by:
Other updates made by:

File purpose:
Wrapper around python multiprocessing module, making multi-processing code
much easier to write in future
"""
import os
import sys
import time
import traceback

from multiprocessing import Pool as ProcessPool
from multiprocessing import Event
from multiprocessing import Value
from multiprocessing import TimeoutError

import demand_utilities.utils as du


class MultiprocessingError(Exception):
    """
    Custom Error Wrapper to throw in this module
    """
    def __init__(self, message):
        super().__init__(message)


# TODO: Don't kill all processes when an error is encountered
# Try to fail on that one process and return a default value
class FailCounter:
    """
    Simple thread/process-safe counter
    """

    fail_counter = None

    def __init__(self, i: int = 0):
        self.fail_counter = Value('i', i)

    def increment(self, i: int = 1):
        """

        Parameters
        ----------
        i:
            The amount the increment the counter by.

        Returns
        -------
        None

        """
        with self.fail_counter.get_lock():
            self.fail_counter.value += i

    def value(self):
        return self.fail_counter.value


def create_kill_pool_fn(pool,
                        terminate_process_event,
                        fail_counter,
                        fail_tolerance=5):
    """
    Creates a Callback function for each function in a Pool.

    This is called whenever an exception is raised inside one of the processes in
    a Pool. This is mostly used to give a clean error output when an error occurs.
    """
    def kill_pool(process_error=None, process_callback=True):
        """
        Needs to accept a process_error arg to be used as a callback
        """
        if process_callback:
            print("-" * 15,
                  "WARNING: Got an error in a process - " +
                  "Killing the whole pool.",
                  "-" * 15)
        else:
            print("Got the following exception while killing process:\n")
        traceback.print_exception(type(process_error),
                                  process_error,
                                  process_error.__traceback__)
        if process_callback:
            print("-" * 20, " End of process error. ", "-" * 20, "\n")

        pool.close()
        pool.terminate()
        terminate_process_event.set()

    return kill_pool


def wait_for_pool_results(results, terminate_process_event, result_timeout):
    """
    Returns the result when they arrive. Throws an error if event is set,
    or result_timeout is reached.

    Parameters
    ----------
    results:
        A list of multiprocessing.pool.AsyncResult. The results we're waiting
        for.

    terminate_process_event:
        A multiprocessing.event. This event should get set if an error occurs
        and the processpool is trying to terminate.

    result_timeout:
        Int. How long to wait before throwing an error.

    Returns
    -------
    results_out:
        A list of the results collected from the original results.
        May not be in the same order as received.
    """
    # Initialise loop
    start_time = time.time()
    got_all_results = False
    return_results = list()
    n_start_results = len(results)

    while not got_all_results:
        # Wait for a little bit to avoid intensive looping
        time.sleep(0.05)

        # Check for an event
        if terminate_process_event.is_set():
            raise MultiprocessingError(
                "While getting results terminate_process_event was set.")

        # Check if we've ran out of time
        if (time.time() - start_time) > result_timeout:
            raise TimeoutError("Ran out of time while waiting for results.")

        # Check if we have any results
        res_to_remove = list()
        for i, res in enumerate(results):
            if not res.ready():
                continue

            if not res.successful():
                raise MultiprocessingError(
                    "An error occurred in one of the processes.")

            # Give a minute to get the result
            # Shouldn't take this long as we know the result is ready
            return_results.append(res.get(60))
            res_to_remove.append(i)

        # Remove results we've got
        for i in sorted(res_to_remove, reverse=True):
            del results[i]

        # Quick sanity check
        if not len(results) + len(return_results) == n_start_results:
            raise MultiprocessingError(
                "While getting the multiprocessing results an error occurred." +
                "Lost one or more results. Started with %d, now have %d." %
                (n_start_results, len(results)+len(return_results)))

        # Check if we have all results
        if len(return_results) == n_start_results:
            got_all_results = True

    return return_results


def _call_order_wrapper(index, func, *args, **kwargs):
    """
    A function wrapper allowing an index to be added to the function call
    and return

    Useful when placing a function into an asynchronous Pool. The index of the
    function is returned alongside the results, allowing for sorting.

    NOTE:
        Originally tried to implement this as a function decorator, however
        Pools do not like decorated functions as they become unpickleable.
    """
    return index, func(*args, **kwargs)


def _check_args_kwargs(args,
                       kwargs,
                       args_default=list(),
                       kwargs_default=dict(),
                       length=None):
    """
    If args or kwargs are set to None they are filled with their default value
    to match the length of the other.
    If both are None, then they are set to length.
    If neither are None, they are returned as is.
    """
    if args is not None and kwargs is None:
        kwargs = [kwargs_default for _ in range(len(args))]
    elif args is None and kwargs is not None:
        args = [args_default for _ in range(len(kwargs))]
    elif args is None and kwargs is None and length is not None:
        args = [args_default for _ in range(length)]
        kwargs = [kwargs_default for _ in range(length)]
    elif args is None and kwargs is None and length is None:
        raise ValueError("Both args and kwargs are None and length has not " +
                         "been set. Don't know how to proceed!")

    return args, kwargs


def _process_pool_wrapper_kwargs_in_order(fn,
                                          args=None,
                                          kwargs=None,
                                          process_count=os.cpu_count()-1,
                                          pool_maxtasksperchild=4,
                                          result_timeout=86400):
    """
    See process_pool_wrapper() for full documentation of this function.
    Sister function with _process_pool_wrapper_kwargs_out_order().
    Should only be called from process_pool_wrapper().
    """
    args, kwargs = _check_args_kwargs(args, kwargs)

    terminate_processes_event = Event()
    fail_counter = FailCounter(0)

    with ProcessPool(processes=process_count, maxtasksperchild=pool_maxtasksperchild) as pool:
        kill_pool = create_kill_pool_fn(pool,
                                        terminate_processes_event,
                                        fail_counter)
        try:
            results = list()

            # Add each function call to the pool
            for i, (a, k) in enumerate(zip(args, kwargs)):
                # Set up ready to use _call_order_wrapper()
                new_args = (i, fn, *a)
                results.append(pool.apply_async(_call_order_wrapper,
                                                args=new_args,
                                                kwds=k,
                                                error_callback=kill_pool))

            result_timeout *= max(len(results), 1)
            results = wait_for_pool_results(results, terminate_processes_event,
                                            result_timeout)

        except BaseException:
            # If any exception, clean up and exit to be safe
            kill_pool(process_callback=False)
            traceback.print_exc()
            print("Everything cleaned up, exiting...")
            sys.exit(1)
    del pool

    # Order the results, and separate from enumerator
    _, results = zip(*sorted(results, key=lambda x: x[0]))
    return list(results)


def _process_pool_wrapper_kwargs_out_order(fn,
                                           args=None,
                                           kwargs=None,
                                           process_count=os.cpu_count()-1,
                                           pool_maxtasksperchild=4,
                                           result_timeout=86400):
    """
    See process_pool_wrapper() for full documentation of this function.
    Sister function with _process_pool_wrapper_kwargs_in_order().
    Should only be called from process_pool_wrapper().
    """
    args, kwargs = _check_args_kwargs(args, kwargs)

    terminate_process_event = Event()
    fail_counter = FailCounter(0)

    with ProcessPool(processes=process_count, maxtasksperchild=pool_maxtasksperchild) as pool:
        kill_pool = create_kill_pool_fn(pool,
                                        terminate_process_event,
                                        fail_counter)

        try:
            results = list()

            # Add each function call to the pool
            for a, k in zip(args, kwargs):
                results.append(pool.apply_async(fn,
                                                args=a,
                                                kwds=k,
                                                error_callback=kill_pool))

            result_timeout *= max(len(results), 1)
            results = wait_for_pool_results(results, terminate_process_event,
                                            result_timeout)

        except BaseException:
            # If any exception, clean up and exit to be safe
            kill_pool(process_callback=False)
            traceback.print_exc()
            print("Everything cleaned up, exiting...")
            sys.exit(1)

    del pool
    return results


def process_pool_wrapper(fn,
                         args=None,
                         kwargs=None,
                         process_count=os.cpu_count()-1,
                         pool_maxtasksperchild=4,
                         in_order=False,
                         result_timeout=86400):
    """
    Runs the given function with the arguments given in a multiprocessing.Pool,
    returning the function output.

    Parameters
    ----------
    fn:
        The name of the function to call.

    args:
        A list of iterables e.g. tuples/lists. len(args) matches the number of
        times fn should be called. Each tuple contains a full set of non-
        keyword arguments to be passed to a single call of fn.
        Defaults to None.

    kwargs:
        A list of dictionaries. The keys are the keyword argument names, and
        the values are the keyword argument values. len(kwargs) matches the
        number of times fn should be called, and should directly correspond to
        args. Each dictionary contains a full set of keyword arguments to be
        passed to a single call of fn.
        Defaults to None.

    process_count:
        The number of processes to create in the Pool. Typically this
        should not exceed the number of cores available.
        Defaults to os.cpu_count().

    pool_maxtasksperchild:
        Passed into the created Pool as maxtaskperchild=pool_maxtaskperchild.
        It is the number of tasks a worker process can complete before it will
        exit and be replaced with a fresh worker process, to enable unused
        resources to be freed.
        Defaults to 4.

    in_order:
        Boolean. Whether the return values need to be in the same order they
        were given. in_order=True is slightly slower due to sorting the results.
        Defaults to False.

    result_timeout:
        Int. How long to wait for each process before throwing an exception
        because the results have taken too long to return
        Defaults to 86400 seconds, (24 hours).

    Examples
    --------
    The following three function calls:
    >>> a = sorted(range(10))
    >>> b = sorted(range(100))
    >>> c = sorted(range(20), reverse=True)

    Would be called, using this function, like this:
    >>> # Note the use of a tuple to make sure a single argument is still
    >>> # iterable
    >>> a_args = (range(10), )
    >>> b_args = (range(100), )
    >>> c_args = (range(20 ), )
    >>>
    >>> # Need to use an empty dict where arguments are not given
    >>> a_kwargs = dict()
    >>> b_kwargs = dict()
    >>> c_kwargs = {'reverse': True}

    >>> args = [a_args, b_args, c_args]
    >>> kwargs = [a_kwargs, b_kwargs, c_kwargs]
    >>> a, b, c = process_pool_wrapper(sorted, args, kwargs)
    """
    # Input validation
    assert (args is not None or kwargs is not None), \
        ("In multiprocessing_wrapper.process_pool_wrapper(), "
         "Either args or kwargs need to be set.")

    if in_order:
        return _process_pool_wrapper_kwargs_in_order(fn, args, kwargs,
                                                     process_count=process_count,
                                                     pool_maxtasksperchild=pool_maxtasksperchild,
                                                     result_timeout=result_timeout)
    else:
        return _process_pool_wrapper_kwargs_out_order(fn, args, kwargs,
                                                      process_count=process_count,
                                                      pool_maxtasksperchild=pool_maxtasksperchild,
                                                      result_timeout=result_timeout)


def _test_my_sorted(iterator=None, reverse=None):
    if iterator is None or reverse is None:
        raise ValueError
    return sorted(iterator, reverse=reverse)


def _test_raise_error(index):
    if index == 4:
        print("%d is Error!" % index)
        raise ValueError("Throwing a test error!")
    print("%d is waiting!" % index)
    time.sleep(5)


def process_pool_tests():
    """
    Run some tests to make sure the written functions are working correctly.

    Also provides some examples for proper use.
    """
    print("Running multiprocessing_wrapper.py tests...")

    # # Use this to test Exception catching and terminating
    # args = [(x, ) for x in range(10)]
    # process_pool_wrapper(_test_raise_error, args)
    # process_pool_wrapper(_test_raise_error, args, in_order=True)
    # print("Left Error Test")

    # Set up
    n_repeats = 10
    arg_val = list(range(10))
    kwarg_val = {'reverse': True}

    args = list()
    kwargs = list()
    for i in range(n_repeats):
        args.append((arg_val.copy(), ))

        # Test empty kwarg
        if i == 1:
            kwargs.append(dict())
        else:
            kwargs.append(kwarg_val.copy())

    # Run normally to get baseline
    baseline_results = list()
    baseline_results_kw = list()
    for a, k in zip(args, kwargs):
        baseline_results.append(sorted(*a))
        baseline_results_kw.append(sorted(*a, **k))

    # Run tests and assert they are correct
    assert (process_pool_wrapper(sorted, args, kwargs,
                                 in_order=True) == baseline_results_kw)
    assert (process_pool_wrapper(sorted, args,
                                 in_order=True) == baseline_results)
    assert (process_pool_wrapper(sorted, args, None,
                                 in_order=True) == baseline_results)

    # Need special check here in case they are out of order
    assert (du.equal_ignore_order(
        process_pool_wrapper(sorted, args, kwargs, in_order=False),
        baseline_results_kw)
    )
    assert (du.equal_ignore_order(
        process_pool_wrapper(sorted, args, in_order=False),
        baseline_results)
    )

    # Kwargs only set up
    kwargs_dict = {'reverse': True,
                   'iterator': arg_val.copy()}
    args = [list() for _ in range(n_repeats)]
    kwargs = [kwargs_dict for _ in range(n_repeats)]
    baseline_results = [_test_my_sorted(**k) for k in kwargs]

    # Test passing in empty args
    assert (process_pool_wrapper(_test_my_sorted, args, kwargs,
                                 in_order=True) == baseline_results)

    # Test passing in None args
    assert (process_pool_wrapper(_test_my_sorted, None, kwargs,
                                 in_order=True) == baseline_results)

    print("All tests passed!")


if __name__ == '__main__':
    process_pool_tests()
