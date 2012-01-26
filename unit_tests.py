import time
import struct
import socket
import logging
from random import randrange
from unittest import TestCase, main

import collectd

class BaseCase(TestCase):
    def assertValidPacket(self, expected_type_count, s):
        type_codes = {}
        while s:
            type_code, size = struct.unpack("!HH", s[:4])
            type_codes[type_code] = 1
            self.assertTrue(size > 0)
            self.assertTrue(len(s) >= size)
            self.assertTrue(type_code in (collectd.LONG_INT_CODES
                                        + collectd.STRING_CODES
                                        + [collectd.TYPE_VALUES]))
            if type_code in collectd.LONG_INT_CODES:
                self.assertEqual(size, 12)
                struct.unpack("!q", s[4:12])
            elif type_code in collectd.STRING_CODES:
                self.assertEqual(s[size-1], "\0")
                struct.unpack(str(size-4) + "s", s[4:size])
            else:
                self.assertEqual(type_code, collectd.TYPE_VALUES)
                values = s[6:size]
                count = 0
                while values:
                    value_code = struct.unpack("B", values[0])[0]
                    self.assertTrue(value_code in collectd.VALUE_CODES)
                    struct.unpack(collectd.VALUE_CODES[value_code], values[1:9])
                    values = values[9:]
                    count += 1
                self.assertEqual(count, struct.unpack("!H", s[4:6])[0])
            s = s[size:]
        self.assertEqual(expected_type_count, sum(type_codes.values()))
    
    def assertValidMessages(self, expected_message_count, stats):
        packets = collectd.messages(stats)
        self.assertEqual(expected_message_count, len(packets))
        for packet in packets:
            self.assertValidPacket(8, packet)


class CounterTests(BaseCase):
    def setUp(self):
        self.counter = collectd.Counter("test")
    
    def snapshot(self):
        return self.counter.snapshot()
    
    def record(self, *args, **kwargs):
        self.counter.record(*args, **kwargs)
    
    def set_exact(self, **kwargs):
        self.counter.set_exact(**kwargs)
    
    def test_snapshot_reset(self):
        self.assertEqual({}, self.snapshot())
        self.record(foo = 2)
        self.assertEqual({"test-foo": 2}, self.snapshot())
        self.assertEqual({"test-foo": 0}, self.snapshot())
    
    def test_record_adding(self):
        self.record(foo = 0.5)
        self.record(foo = 1.5)
        self.assertEqual({"test-foo": 2}, self.snapshot())
    
    def test_record_many(self):
        self.record(foo = 2, bar = 3)
        self.assertEqual({"test-foo":2, "test-bar":3}, self.snapshot())
    
    def test_record_duplicates(self):
        self.record("sub1", "sub2", foo = 2)
        self.assertEqual({"test-foo":2, "test-sub1-foo":2, "test-sub2-foo":2},
                         self.snapshot())
    
    def test_record_heirarchy(self):
        self.record("sub1", foo = 2)
        self.record("sub2", foo = 3)
        self.assertEqual({"test-foo":5, "test-sub1-foo":2, "test-sub2-foo":3},
                         self.snapshot())
    
    def test_exact(self):
        self.set_exact(foo = 3)
        self.set_exact(foo = 2)
        self.assertEqual({"test-foo": 2}, self.snapshot())
        self.assertEqual({"test-foo": 0}, self.snapshot())
        
        self.record(foo = 5)
        self.set_exact(foo = 2)
        self.assertEqual({"test-foo": 2}, self.snapshot())
        
        self.set_exact(foo = 2)
        self.record(foo = 5)
        self.assertEqual({"test-foo": 7}, self.snapshot())
    
    def test_no_stats(self):
        self.record()
        self.assertEqual({}, self.snapshot())
        
        self.record("sub1")
        self.assertEqual({}, self.snapshot())
        
        self.set_exact()
        self.assertEqual({}, self.snapshot())
    
    def test_bad_stats(self):
        for arg in [None, 666, int, float]:
            self.record(arg, foo = 2)
            self.assertEqual({}, self.snapshot())
        
        for val in ["invalid", 2 ** 100, int, float]:
            self.record(foo = "invalid")
            self.set_exact(foo = "invalid")
            self.assertEqual({}, self.snapshot())
    
    def test_sanitize(self):
        valid = []
        for start,end in [("a","z"), ("A","Z"), ("0","9")]:
            for i in range(ord(start), ord(end) + 1):
                valid.append(i)
        
        invalid = "".join(chr(i) for i in range(256) if i not in valid)
        stats = {invalid + "foo" + invalid + "bar" + invalid: 5}
        for func in [self.record, self.set_exact]:
            func(**stats)
            self.assertEqual({"test-foo_bar": 5}, self.snapshot())


class ConnectionTests(CounterTests):
    def setUp(self):
        self.conn = collectd.Connection()
    
    def tearDown(self):
        collectd.Connection.instances.clear()
    
    def snapshot(self):
        snap = self.conn._snapshot()
        return snap[0] if snap else {}
    
    def record(self, *args, **kwargs):
        self.conn.test.record(*args, **kwargs)
    
    def set_exact(self, **kwargs):
        self.conn.test.set_exact(**kwargs)
    
    def test_sameness(self):
        for params in [{"hostname":"127.0.0.1"}, {"collectd_port":1337}]:
            self.assertTrue(self.conn is not collectd.Connection(**params))
            self.assertTrue(collectd.Connection(plugin_inst = "xkcd", **params)
                     is not collectd.Connection(**params))
            self.assertTrue(collectd.Connection(**params)
                         is collectd.Connection(**params))


class PacketTests(BaseCase):
    def test_numeric_valid(self):
        for num in [0, 1, -1, 2**63-1, -2**63]:
            for type_code in collectd.LONG_INT_CODES:
                self.assertValidPacket(1, collectd.pack(type_code, num))
    
    def test_numeric_invalid(self):
        for x in [2**63, -2**63-1, float("nan"), float("inf"), None, "s"]:
            for type_code in collectd.LONG_INT_CODES:
                self.assertRaises(Exception, collectd.pack, type_code, x)
    
    def test_string_valid(self):
        for s in ["", "s", "Hello World!", "X" * 1024]:
            for type_code in collectd.STRING_CODES:
                self.assertValidPacket(1, collectd.pack(type_code, s))
    
    def test_string_invalid(self):
        for x in [None, 5, 1.2, ()]:
            for type_code in collectd.STRING_CODES:
                self.assertRaises(Exception, collectd.pack, type_code, x)
    
    def test_start_valid(self):
        for params in [{}, {"host":""}, {"when":time.time()}]:
            self.assertValidPacket(6, collectd.message_start(**params))
    
    def test_empty_messages(self):
        self.assertValidMessages(0, {})
    
    def test_small_messages(self):
        for stats in [{"stat":5}, {"foo":6,"bar":7}, {"foo-bar-baz":0}]:
            self.assertValidMessages(1, stats)
    
    def test_large_messages(self):
        size = collectd.MAX_PACKET_SIZE // 2
        self.assertValidMessages(2, {"X"*size: 6, "Y"*size: 7})
    
    def test_many_messages(self):
        avail = collectd.MAX_PACKET_SIZE - len(collectd.message_start())
        val_size = len(collectd.pack("xxxx", 0))
        too_many = avail // val_size + 1
        stats = dict(("{0:04}".format(i), i) for i in range(too_many))
        self.assertValidMessages(2, stats)
    
    def test_oversize_messages(self):
        self.assertValidMessages(0, {"X"*collectd.MAX_PACKET_SIZE: 1})
        self.assertValidMessages(1, {"X"*collectd.MAX_PACKET_SIZE: 1, "Y": 2})


class SnapshotTests(BaseCase):
    def tearDown(self):
        collectd.Connection.instances.clear()
        while collectd.snaps.qsize():
            collectd.snaps.get()
    
    def assertQueued(self, size):
        self.assertEqual(size, collectd.snaps.qsize())
        while collectd.snaps.qsize():
            when, stats, conn = collectd.snaps.get()
            self.assertValidMessages(1, stats)
    
    def test_none(self):
        collectd.take_snapshots()
        self.assertEqual(0, collectd.snaps.qsize())
    
    def test_empty(self):
        conn = collectd.Connection()
        collectd.take_snapshots()
        self.assertQueued(0)
        conn.test
        self.assertQueued(0)
    
    def test_regular(self):
        collectd.Connection().test.record(foo = 5)
        collectd.take_snapshots()
        self.assertQueued(1)
    
    def test_multiple_counters(self):
        conn = collectd.Connection()
        conn.foo.record(baz = 5)
        conn.bar.record(baz = 5)
        collectd.take_snapshots()
        self.assertQueued(1)
    
    def test_multiple_conns(self):
        conn1 = collectd.Connection(collectd_host = "localhost")
        conn2 = collectd.Connection(collectd_host = "127.0.0.1")
        conn1.foo.record(baz = 5)
        conn2.bar.record(baz = 5)
        collectd.take_snapshots()
        self.assertQueued(2)


class SocketTests(BaseCase):
    TEST_PORT = 13367
    
    def setUp(self):
        self.conn = collectd.Connection(collectd_port = self.TEST_PORT)
        self.server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(("localhost", self.TEST_PORT))
    
    def tearDown(self):
        collectd.Connection.instances.clear()
        self.server.close()
    
    def send_and_recv(self, conn=None, *specific, **stats):
        (conn or self.conn).test.record(*specific, **stats)
        collectd.take_snapshots()
        collectd.send_stats(raise_on_empty = True)
        packet = self.server.recv(collectd.MAX_PACKET_SIZE)
        self.assertValidPacket(8, packet)
        return packet
    
    def test_empty(self):
        collectd.send_stats()
    
    def test_single(self):
        self.send_and_recv(foo = 5)
    
    def test_multiple(self):
        stats = {"foo": 345352, "bar": -5023123}
        packet = self.send_and_recv(**stats)
        for name, value in stats.items():
            self.assertTrue(name + "\0" in packet)
            self.assertTrue(struct.pack("<d", value) in packet)
            self.assertTrue(collectd.pack("test-"+name, value) in packet)
    
    def test_plugin_name(self):
        conn = collectd.Connection(collectd_port = self.TEST_PORT,
                                   plugin_name = "dckx")
        self.assertTrue("dckx" in self.send_and_recv(conn, foo=5))

    def test_plugin_inst(self):
        conn = collectd.Connection(collectd_port = self.TEST_PORT,
                                   plugin_inst = "xkcd")
        self.assertTrue("xkcd" in self.send_and_recv(conn, foo=5))
    
    def test_unicode(self):
        self.send_and_recv(self.conn, u"admin.get_connect_server_status", hits = 1)
    
    def test_too_large(self):
        size = collectd.MAX_PACKET_SIZE // 2
        stats = [("X"*size, 123), ("Y"*size, 321)]
        self.conn.test.record(**dict(stats))
        collectd.take_snapshots()
        collectd.send_stats(raise_on_empty = True)
        for name,val in stats:
            packet = self.server.recv(collectd.MAX_PACKET_SIZE)
            self.assertTrue(name + "\0" in packet)
            self.assertTrue(struct.pack("<d", val) in packet)
            self.assertValidPacket(8, packet)
    
    def test_too_many(self):
        stats = [("x{0:02}".format(i), randrange(256)) for i in range(50)]
        self.conn.test.record(**dict(stats))
        collectd.take_snapshots()
        collectd.send_stats(raise_on_empty = True)
        
        packets = [self.server.recv(collectd.MAX_PACKET_SIZE) for i in range(2)]
        for packet in packets:
            self.assertValidPacket(8, packet)
        
        data = "".join(packets)
        for name,val in stats:
            self.assertTrue(name + "\0" in data)
            self.assertTrue(struct.pack("<d", val) in data)



class NullHandler(logging.Handler):
    def emit(self, record):
        pass
collectd.logger.addHandler(NullHandler())

if __name__ == "__main__":
    main()
