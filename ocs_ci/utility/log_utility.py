"""
A module for helping/improving logging functionalities

"""

import time
import logging
import atexit
import threading

from collections import OrderedDict
from typing import Iterable, Optional


log = logging.getLogger(__name__)
rlogger = logging.getLogger()


class LogDeduplicator(logging.Filter):
    """
    A filter that supresses repeated log messages from printing, instead
    we print the message based on :
        1. suppressed count >= emit after count
        2. periodic flush based on time threshold
    concepts:
        Key: (logger_name, level, message)
        first occurence: message emitted normally for the first occurence, subsequently
                         repeated messages will be counted rather than emit
        Triggers: when we reach count_threshold OR flush_time_window, for each record we will log the
                   summary with count

    """

    def __init__(
        self,
        name: str = "",
        flush_time_window: int = 5,  # after 'flush_time_window' seconds we will emit
        emit_count_threshold: int = 10,  # after a count of 'emit_count_threshold' messages we will emit
        max_keys: int = 2000,
        log_levels: Iterable[int] = (logging.INFO, logging.DEBUG),
        log_whitelist: Optional[Iterable[str]] = None,
        log_blacklist: Optional[Iterable[str]] = None,
        bg_flush_interval: Optional[int] = None,
    ):
        super().__init__(name)
        self.flush_time_window = flush_time_window
        self.emit_count_threshold = emit_count_threshold
        self.max_keys = max_keys
        self.log_levels = set(log_levels)
        self.log_whitelist = tuple(log_whitelist) if log_whitelist else None
        self.log_blacklist = tuple(log_blacklist) if log_blacklist else None

        self._kstore = OrderedDict()
        self._lock = threading.RLock()

        # background flusher thread
        self._bg_thread = None
        self._bg_thread_stop = threading.Event()
        self._bg_interval = None

        if bg_flush_interval is not None and bg_flush_interval > 0:
            self.start_bg_flusher_thread(bg_flush_interval)

        atexit.register(self._atexit_flush)

    def _get_key(self, record: logging.LogRecord):
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        return (record.name, record.levelno, msg)

    def _is_logger_allowed(self, logger_name):
        if self.log_whitelist:
            if not any(logger_name.startswith(s) for s in self.log_whitelist):
                return False
        if self.log_blacklist:
            if any(logger_name.startswith(i) for i in self.log_blacklist):
                return False
        return True

    def filter(self, record: logging.LogRecord):
        """
        Decide whether to emit a message or not

        Returns:
            True: Emit the log
            False: don't emit

        """
        log.info("Entering filter")
        if record.levelno not in self.log_levels:
            return True

        # if its a stackinfo then don't supress
        if record.exc_info or record.stack_info:
            return True

        if not self._is_logger_allowed(record.name):
            return True

        # A key ex:- ("ocs_ci.utility.utils", 20, "Running command: oc get pods")
        key = self._get_key(record)
        now = time.time()

        with self._lock:
            # key -> [count, start_ts, last_ts, sample_record] (this is an 'entry')
            entry = self._kstore.get(key)
            if entry is None:
                # first entry for this message so print it once
                # and check if _kstore has max keys already
                log.info("Entry doesn't exist, going to create now")
                if len(self._kstore) > self.max_keys:
                    # pop oldest key and emit its message
                    o_key, o_entry = self._kstore.popitem(last=False)
                    self._emit_summary_for_key_without_lock(o_key, o_entry)
                self._kstore[key] = [0, now, now, record]
                log.info(f"Added: {self._kstore[key]} with record {record}")
                return True
            else:
                # repeated log
                entry[0] += 1
                entry[2] = now

                # case - emit_count_threshold reached
                # emit summary and reset
                if entry[0] >= self.emit_count_threshold:
                    self._emit_summary_for_key_without_lock(key, entry)
                    # reset the entry to treat record as a new sample
                    self._kstore[key] = [0, now, now, record]
                    return True

                # case - flush_time_window threashold reached
                if now - entry[1] >= self.flush_time_window:
                    log.info("Flush time window threashold reached")
                    self._emit_summary_for_key_without_lock(key, entry)
                    self._kstore[key] = [0, now, now, record]
                    return True
                # supress the log
                return False

    def _emit_summary_for_key_without_lock(self, key, entry):
        # Caller should hold the lock
        # we will not hold any lock inside this function
        count, start_ts, last_ts, sample = entry
        if count <= 0:
            return
        logger_name, levelno, _msg = key
        logger = logging.getLogger(logger_name)

        duration = last_ts - start_ts
        summary_msg = (
            f"{sample.getMessage()}... repeated {count} times over {duration:.1f}s"
        )
        try:
            logger.log(levelno, summary_msg)
        except Exception:
            # emit on root
            rlogger.log(levelno, summary_msg)

    def flush_key(self, logger_name, levelno, msg_text):
        key = (logger_name, levelno, msg_text)
        with self._lock:
            entry = self._kstore.pop(key, None)
        if entry:
            with self._lock:
                self._emit_summary_for_key_without_lock(key, entry)

    def flush_all_keys(self):
        with self._lock:
            items = list(self._kstore.items())
            self._kstore.clear()
        for k, e in items:
            self._emit_summary_for_key_without_lock(k, e)

    def _atexit_flush(self):
        self.stop_bg_flusher_thread()
        try:
            self.flush_all_keys()
        except Exception:
            pass

    def start_bg_flusther_thread(self, interval):
        """
        Background thread for periodic key flush

        """
        with self._lock:
            if self._bg_thread and self._bg_thread.is_alive():
                return
            self._bg_interval = int(interval)
            self._bg_thread_stop.clear()
            th = threading.Thread(
                target=self._bg_worker, name="Logdedupflusher", daemon=True
            )
            self._bg_thread = th
            th.start()

    def stop_bg_flusher_thread(self, timeout=5):
        """
        Args:
            timeout (int): Join timeout
        """
        with self._lock:
            if not self._bg_thread:
                return
            self._bg_thread_stop.set()
            thread = self._bg_thread
            self._bg_thread = None

        thread.join(timeout=timeout)

    def _bg_worker(self):
        """
        Periodically flush keys
        Keys that have crossed flush_time_window and have non-zero count

        """
        interval = self._bg_interval or 10
        while not self._bg_thread_stop.wait(interval):
            now = time.time()
            to_flush = []
            with self._lock:
                for k, e in list(self._kstore.items()):
                    count, first_ts, _, _ = e
                    if count > 0 and ((now - first_ts) >= self.flush_time_window):
                        to_flush.append((k, e))
            # Emit all the collected (k,e)
            for k, e in to_flush:
                with self._lock:
                    found = self._kstore.get(k)
                    if found is e:
                        self._kstore.pop(k, None)
                        self._emit_summary_for_key_without_lock(k, e)
