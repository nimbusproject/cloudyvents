import unittest
import datetime
import logging
import os
import shutil
import tempfile
import time

import cloudyvents.cyvents as cyvents

# Set this to False to look at generated log files afterwards.  There will be
# many directories like /tmp/cytestlog*
DESTROY_LOGDIR = True

logger = logging.getLogger(__name__)

class CloudyVentsTestCase(unittest.TestCase):
    
    def setUp(self):
        if not self._is_setup():
            self._configure()
            logger.debug("test suite set up")

    def tearDown(self):
        if not DESTROY_LOGDIR:
            logger.debug("logdir destruction disabled")
            return
        if not self._is_setup():
            raise Exception("tear down called without setup")
        shutil.rmtree(self.logdirpath)
    
    def _configure(self):
        tmpdir = tempfile.mkdtemp(prefix="cytestlog")
        logfilepath = os.path.join(tmpdir, str(int(time.time())))
        f = None
        try:
            f = file(logfilepath, 'w')
            f.write("\n## auto-generated @ %s\n\n" % time.ctime())
        finally:
            if f:
                f.close()
        
        logfilehandler = logging.FileHandler(logfilepath)
        logfilehandler.setLevel(logging.DEBUG)
        formatstring = "%(asctime)s %(levelname)s @%(lineno)d: %(message)s"
        logfilehandler.setFormatter(logging.Formatter(formatstring))
        logger.addHandler(logfilehandler)
        
        self.logfilepath = logfilepath
        self.logdirpath = tmpdir
    
    def _is_setup(self):
        try:
            if self.logfilepath and self.logdirpath:
                return True
        except:
            pass
        return False
        
    # -----------------------------------------------------------------------

    def test_event_write(self):
        logger.debug("something")
        cyvents.event("unittest", "TRIAL1", logger)
        logger.debug("something-else")
        events = cyvents.events_from_file(self.logfilepath)
        assert len(events) == 1
        assert events[0].source == "unittest"
        assert events[0].name == "TRIAL1"
        
    def test_manual_event_write(self):
        cruft = "some cruft %s" % cyvents.event_logtxt("unittest", "TRIAL1")
        logger.warning(cruft)
        events = cyvents.events_from_file(self.logfilepath)
        assert len(events) == 1
        
        cyvents.event("unittest", "TRIAL2", logger)
        events = cyvents.events_from_file(self.logfilepath)
        assert len(events) == 2
        
        cruft = "cruft2 %s" % cyvents.event_logtxt("unittest", "TRIAL3")
        logger.warning(cruft)
        
        events = cyvents.events_from_file(self.logfilepath)
        assert len(events) == 3
        
        found = {"TRIAL1":False, "TRIAL2":False, "TRIAL3":False}
        for ev in events:
            if found.has_key(ev.name):
                found[ev.name] = True
        for val in found.values():
            assert val

    def test_timestamp(self):
        utc_now = datetime.datetime.utcnow()
        cyvents.event("unittest", "TRIAL1", logger)
        events = cyvents.events_from_file(self.logfilepath)
        assert len(events) == 1
        ts = events[0].timestamp
        
        # It is possible that any of these values could have rolled over
        # between acquiring utc_now and recording the event.  But this is
        # unlikely enough that we'll keep this important UTC sanity check:
        assert ts.year == utc_now.year
        assert ts.month == utc_now.month
        assert ts.day == utc_now.day
        assert ts.hour == utc_now.hour

    def test_unique_keys(self):
        cyvents.event("unittest", "NAME", logger)
        cyvents.event("unittest", "NAME", logger)
        cyvents.event("unittest", "NAME", logger)
        cyvents.event("unittest", "NAME", logger)
        cyvents.event("unittest", "NAME", logger)
        cyvents.event("unittest", "NAME", logger)
        cyvents.event("unittest", "NAME", logger)
        events = cyvents.events_from_file(self.logfilepath)
        assert len(events) == 7
        uniqs = {}
        for ev in events:
            uniqs[ev.timestamp] = None
        assert len(uniqs) == 7

    def test_extra(self):
        adict = {"hello1":"hello2"}
        cyvents.event("unittest", "TRIAL1", logger, extra=adict)
        events = cyvents.events_from_file(self.logfilepath)
        assert len(events) == 1
        assert events[0].extra["hello1"] == "hello2"
        
    def test_bad_extra(self):
        self.assertRaises(Exception, cyvents.event, 
                          "unittest", "TRIAL1", logger, extra="astring")

    def test_extra_integer_values(self):
        adict = {"hello1":34}
        cyvents.event("unittest", "TRIAL1", logger, extra=adict)
        events = cyvents.events_from_file(self.logfilepath)
        assert len(events) == 1
        assert events[0].extra["hello1"] == 34

    def test_extra_integer_keys(self):
        # This does not serialize as an integer, fails.  Added rule
        # to events recorder to not allow integer keys.
        pass
        #adict = {23:"something"}
        #cyvents.event("unittest", "TRIAL1", logger, extra=adict)
        #events = cyvents.events_from_file(self.logfilepath)
        #assert len(events) == 1
        #assert events[0].extra[23] == "something"

    def test_extra_hierarchy(self):
        # note the conflicting "hello3" key in higher level:
        innerdict = {"hello3":"hello4"}
        adict = {"hello1":"hello2", "hello5":innerdict, "hello3":"hello6"}
        
        cyvents.event("unittest", "TRIAL1", logger, extra=adict)
        events = cyvents.events_from_file(self.logfilepath)
        assert len(events) == 1
        assert events[0].extra["hello1"] == "hello2"
        assert events[0].extra["hello3"] == "hello6"
        
        innerdict = events[0].extra["hello5"]
        assert isinstance(innerdict, dict)
        assert innerdict["hello3"] == "hello4"
        
    def test_newline_rules(self):
        self.assertRaises(Exception, cyvents.event, 
                          "unit\ntest", "TRIAL", logger)
        self.assertRaises(Exception, cyvents.event, 
                          "unittest", "TRIAL\nA", logger)
        self.assertRaises(Exception, cyvents.event, 
                          "unittest", "TRIAL", logger, extra="some\nthing")
        self.assertRaises(Exception, cyvents.event, 
                          "unittest\n", "TRIAL", logger)
        self.assertRaises(Exception, cyvents.event, 
                          "\nunittest", "TRIAL", logger)
        self.assertRaises(Exception, cyvents.event, 
                          "\n", "TRIAL", logger)
      
    def test_missing_rules(self):
        self.assertRaises(Exception, cyvents.event, 
                          None, "TRIAL", logger)
        self.assertRaises(Exception, cyvents.event, 
                          "unittest", None, logger)
      
    def test_event_namefilter(self):
        cyvents.event("unittest", "NM1", logger)
        cyvents.event("unittest", "NM2", logger)
        cyvents.event("unittest", "NM3", logger)
        logger.debug("something not an event")
        cyvents.event("unittest", "NM4", logger)
        cyvents.event("unittest", "NM5", logger)
        logger.debug("something not an event")
        cyvents.event("unittest", "NM6", logger)
        path = self.logfilepath
        events = cyvents.events_from_file(path, namefilter="NM")
        assert len(events) == 6
        
    def test_event_namefilter2(self):
        cyvents.event("unittest", "NM1", logger)
        logger.debug("something not an event")
        cyvents.event("unittest", "XX2", logger)
        cyvents.event("unittest", "NM3", logger)
        logger.debug("something not an event")
        cyvents.event("unittest", "XX4", logger)
        cyvents.event("unittest", "NM5", logger)
        cyvents.event("unittest", "XX6", logger)
        path = self.logfilepath
        events = cyvents.events_from_file(path, namefilter="NM")
        assert len(events) == 3

    def test_event_sourcefilter(self):
        cyvents.event("SRC1", "NM1", logger)
        logger.debug("something not an event")
        cyvents.event("SRC2", "NM2", logger)
        cyvents.event("SRC3", "NM3", logger)
        logger.debug("something not an event")
        cyvents.event("SRC4", "NM4", logger)
        cyvents.event("SRC5", "NM5", logger)
        cyvents.event("SRC6", "NM6", logger)
        path = self.logfilepath
        events = cyvents.events_from_file(path, sourcefilter="SRC")
        assert len(events) == 6
        
    def test_event_sourcefilter2(self):
        cyvents.event("SRC1", "NM1", logger)
        logger.debug("something not an event")
        cyvents.event("SRX2", "NM2", logger)
        cyvents.event("SRC3", "NM3", logger)
        logger.debug("something not an event")
        cyvents.event("SRX4", "NM4", logger)
        cyvents.event("SRC5", "NM5", logger)
        cyvents.event("SRC6", "NM6", logger)
        path = self.logfilepath
        events = cyvents.events_from_file(path, sourcefilter="SRC")
        assert len(events) == 4
    
    def test_event_nameandsourcefilter(self):
        cyvents.event("SRC1", "NX1", logger)
        logger.debug("something not an event")
        cyvents.event("SRX2", "NM2", logger)
        cyvents.event("SRC3", "XX3", logger)
        cyvents.event("SRX4", "XX4", logger)
        cyvents.event("SRC5", "NM5", logger)
        logger.debug("something not an event")
        cyvents.event("SRC6", "NM6", logger)
        path = self.logfilepath
        events = cyvents.events_from_file(path, sourcefilter="SRC", namefilter="NM")
        assert len(events) == 2
