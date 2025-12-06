import logging

from ocs_ci.utility.log_utility import LogDeduplicator


log = logging.getLogger(__name__)
log.propagate = True
_dedup_filter = LogDeduplicator(
    name="ConsoleLogDeduplocal",
    flush_time_window=10,
    emit_count_threshold=30,
    max_keys=1000,
)

log.addFilter(_dedup_filter)

rlog = logging.getLogger()


from ocs_ci.framework.testlib import brown_squad


@brown_squad
class TestGetCommands:
    def test_log_dedup(self):
        log.info(f"ROOT FILTERS = {[type(f).__name__ for f in rlog.filters]}")
        root_handlers = [
            f"{type(h).__name__}:"
            f"{getattr(h, 'baseFilename', getattr(h, 'stream', '<stream>'))}"
            for h in rlog.handlers
        ]
        log.info(f"ROOT_HANDLERS = {root_handlers}")
        log.info(f"LOCAL FILTERS = {[type(f).__name__ for f in log.filters]}")
        local_handlers = [
            f"{type(h).__name__}:"
            f"{getattr(h, 'baseFilename', getattr(h, 'stream', '<stream>'))}"
            for h in log.handlers
        ]
        log.info(f"LOCAL HANDLERS = {local_handlers}")
        log.info(f"Propagate = {log.propagate}")

        for i in range(100):
            log.info("Hello")
