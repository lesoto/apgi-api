"""
Unit tests for cache service.
"""

import pytest
from app.services.cache_service import CacheService


class TestCacheService:
    """Test cache service."""

    @pytest.fixture
    def cache_service(self):
        """Create cache service instance."""
        return CacheService()

    def test_cache_initialization(self, cache_service):
        """Test cache service initialization."""
        assert cache_service is not None

    def test_set_cache_value(self, cache_service):
        """Test setting a cache value."""
        key = "test_key"
        value = "test_value"

        cache_service.set(key, value)

        # Should not raise any errors

    def test_get_cache_value(self, cache_service):
        """Test getting a cache value."""
        key = "test_key"
        value = "test_value"

        cache_service.set(key, value)
        retrieved = cache_service.get(key)

        assert retrieved == value

    def test_get_nonexistent_cache_value(self, cache_service):
        """Test getting a nonexistent cache value."""
        key = "nonexistent_key"

        retrieved = cache_service.get(key)

        assert retrieved is None

    def test_delete_cache_value(self, cache_service):
        """Test deleting a cache value."""
        key = "test_key"
        value = "test_value"

        cache_service.set(key, value)
        cache_service.delete(key)

        retrieved = cache_service.get(key)
        assert retrieved is None

    def test_cache_exists(self, cache_service):
        """Test checking if cache key exists."""
        key = "test_key"
        value = "test_value"

        cache_service.set(key, value)
        exists = cache_service.exists(key)

        assert exists is True

    def test_cache_not_exists(self, cache_service):
        """Test checking if cache key does not exist."""
        key = "nonexistent_key"

        exists = cache_service.exists(key)

        assert exists is False

    def test_cache_expiration(self, cache_service):
        """Test cache expiration."""
        key = "test_key"
        value = "test_value"
        ttl = 1  # 1 second

        cache_service.set(key, value, ttl=ttl)

        # Immediately check - should exist
        exists = cache_service.exists(key)
        assert exists is True

    def test_cache_clear(self, cache_service):
        """Test clearing all cache."""
        cache_service.set("key1", "value1")
        cache_service.set("key2", "value2")

        cache_service.clear()

        assert cache_service.exists("key1") is False
        assert cache_service.exists("key2") is False

    def test_cache_get_many(self, cache_service):
        """Test getting multiple cache values."""
        cache_service.set("key1", "value1")
        cache_service.set("key2", "value2")
        cache_service.set("key3", "value3")

        values = cache_service.get_many(["key1", "key2", "key3"])

        assert values["key1"] == "value1"
        assert values["key2"] == "value2"
        assert values["key3"] == "value3"

    def test_cache_set_many(self, cache_service):
        """Test setting multiple cache values."""
        data = {"key1": "value1", "key2": "value2", "key3": "value3"}

        cache_service.set_many(data)

        assert cache_service.get("key1") == "value1"
        assert cache_service.get("key2") == "value2"
        assert cache_service.get("key3") == "value3"

    def test_cache_delete_many(self, cache_service):
        """Test deleting multiple cache values."""
        cache_service.set("key1", "value1")
        cache_service.set("key2", "value2")
        cache_service.set("key3", "value3")

        cache_service.delete_many(["key1", "key2"])

        assert cache_service.exists("key1") is False
        assert cache_service.exists("key2") is False
        assert cache_service.exists("key3") is True

    def test_cache_increment(self, cache_service):
        """Test incrementing a cache value."""
        key = "counter"
        cache_service.set(key, 5)

        incremented = cache_service.increment(key)

        assert incremented == 6

    def test_cache_decrement(self, cache_service):
        """Test decrementing a cache value."""
        key = "counter"
        cache_service.set(key, 5)

        decremented = cache_service.decrement(key)

        assert decremented == 4

    def test_cache_append(self, cache_service):
        """Test appending to a cache value."""
        key = "list"
        cache_service.set(key, [1, 2, 3])

        cache_service.append(key, 4)

        value = cache_service.get(key)
        assert 4 in value

    def test_cache_prepend(self, cache_service):
        """Test prepending to a cache value."""
        key = "list"
        cache_service.set(key, [2, 3])

        cache_service.prepend(key, 1)

        value = cache_service.get(key)
        assert value[0] == 1

    def test_cache_get_or_set(self, cache_service):
        """Test get or set cache value."""
        key = "test_key"
        default_value = "default"

        value = cache_service.get_or_set(key, default_value)

        assert value == default_value

    def test_cache_get_or_set_with_callback(self, cache_service):
        """Test get or set with callback."""
        key = "test_key"

        def callback():
            return "computed_value"

        value = cache_service.get_or_set(key, callback)

        assert value == "computed_value"

    def test_cache_key_pattern(self, cache_service):
        """Test finding keys by pattern."""
        cache_service.set("user:1:name", "Alice")
        cache_service.set("user:2:name", "Bob")
        cache_service.set("session:1:data", "data")

        keys = cache_service.keys("user:*")

        assert "user:1:name" in keys
        assert "user:2:name" in keys
        assert "session:1:data" not in keys

    def test_cache_stats(self, cache_service):
        """Test getting cache statistics."""
        stats = cache_service.get_stats()

        assert "hits" in stats
        assert "misses" in stats
        assert "size" in stats

    def test_cache_flush(self, cache_service):
        """Test flushing cache."""
        cache_service.set("key1", "value1")
        cache_service.set("key2", "value2")

        cache_service.flush()

        assert cache_service.exists("key1") is False
        assert cache_service.exists("key2") is False

    def test_cache_size(self, cache_service):
        """Test getting cache size."""
        cache_service.set("key1", "value1")
        cache_service.set("key2", "value2")

        size = cache_service.size()

        assert size == 2

    def test_cache_keys(self, cache_service):
        """Test getting all cache keys."""
        cache_service.set("key1", "value1")
        cache_service.set("key2", "value2")

        keys = cache_service.keys()

        assert "key1" in keys
        assert "key2" in keys

    def test_cache_values(self, cache_service):
        """Test getting all cache values."""
        cache_service.set("key1", "value1")
        cache_service.set("key2", "value2")

        values = cache_service.values()

        assert "value1" in values
        assert "value2" in values

    def test_cache_items(self, cache_service):
        """Test getting all cache items."""
        cache_service.set("key1", "value1")
        cache_service.set("key2", "value2")

        items = cache_service.items()

        assert ("key1", "value1") in items
        assert ("key2", "value2") in items

    def test_cache_pop(self, cache_service):
        """Test popping a cache value."""
        key = "test_key"
        value = "test_value"

        cache_service.set(key, value)
        popped = cache_service.pop(key)

        assert popped == value
        assert cache_service.exists(key) is False

    def test_cache_update(self, cache_service):
        """Test updating cache values."""
        cache_service.set("key1", "value1")

        cache_service.update({"key1": "new_value1", "key2": "value2"})

        assert cache_service.get("key1") == "new_value1"
        assert cache_service.get("key2") == "value2"

    def test_cache_rename(self, cache_service):
        """Test renaming a cache key."""
        old_key = "old_key"
        new_key = "new_key"
        value = "test_value"

        cache_service.set(old_key, value)
        cache_service.rename(old_key, new_key)

        assert cache_service.exists(old_key) is False
        assert cache_service.get(new_key) == value

    def test_cache_touch(self, cache_service):
        """Test touching a cache key to update TTL."""
        key = "test_key"
        value = "test_value"
        ttl = 10

        cache_service.set(key, value, ttl=ttl)
        cache_service.touch(key, ttl)

        # Should not raise any errors

    def test_cache_expire(self, cache_service):
        """Test expiring a cache key."""
        key = "test_key"
        value = "test_value"

        cache_service.set(key, value)
        cache_service.expire(key, 1)

        # Should not raise any errors

    def test_cache_ttl(self, cache_service):
        """Test getting TTL for a cache key."""
        key = "test_key"
        value = "test_value"
        ttl = 10

        cache_service.set(key, value, ttl=ttl)
        remaining_ttl = cache_service.ttl(key)

        assert remaining_ttl > 0

    def test_cache_persist(self, cache_service):
        """Test persisting a cache key (removing TTL)."""
        key = "test_key"
        value = "test_value"

        cache_service.set(key, value, ttl=10)
        cache_service.persist(key)

        # Should not raise any errors

    def test_cache_type(self, cache_service):
        """Test getting the type of a cache value."""
        key = "test_key"
        value = "test_value"

        cache_service.set(key, value)
        value_type = cache_service.type(key)

        assert value_type == "string"

    def test_cache_random_key(self, cache_service):
        """Test getting a random cache key."""
        cache_service.set("key1", "value1")
        cache_service.set("key2", "value2")

        random_key = cache_service.random_key()

        assert random_key in ["key1", "key2"]

    def test_cache_scan(self, cache_service):
        """Test scanning cache keys."""
        cache_service.set("key1", "value1")
        cache_service.set("key2", "value2")
        cache_service.set("key3", "value3")

        keys = cache_service.scan(match="key*")

        assert "key1" in keys
        assert "key2" in keys
        assert "key3" in keys

    def test_cache_distributed_lock(self, cache_service):
        """Test distributed lock."""
        lock_key = "lock_key"
        lock_value = "lock_value"

        acquired = cache_service.acquire_lock(lock_key, lock_value, ttl=10)

        assert acquired is True

        cache_service.release_lock(lock_key, lock_value)

    def test_cache_semaphore(self, cache_service):
        """Test semaphore pattern."""
        semaphore_key = "semaphore_key"
        limit = 5

        acquired = cache_service.acquire_semaphore(semaphore_key, limit)

        assert acquired is True

        cache_service.release_semaphore(semaphore_key)

    def test_cache_pub_sub(self, cache_service):
        """Test pub/sub pattern."""
        channel = "test_channel"
        message = "test_message"

        cache_service.publish(channel, message)

        # Should not raise any errors

    def test_cache_subscribe(self, cache_service):
        """Test subscribing to a channel."""
        channel = "test_channel"

        cache_service.subscribe(channel)

        # Should not raise any errors

    def test_cache_unsubscribe(self, cache_service):
        """Test unsubscribing from a channel."""
        channel = "test_channel"

        cache_service.unsubscribe(channel)

        # Should not raise any errors

    def test_cache_transaction(self, cache_service):
        """Test cache transaction."""

        def transaction(pipe):
            pipe.set("key1", "value1")
            pipe.set("key2", "value2")

        cache_service.transaction(transaction)

        assert cache_service.get("key1") == "value1"
        assert cache_service.get("key2") == "value2"

    def test_cache_pipeline(self, cache_service):
        """Test cache pipeline."""

        def pipeline(pipe):
            pipe.set("key1", "value1")
            pipe.set("key2", "value2")

        cache_service.pipeline(pipeline)

        assert cache_service.get("key1") == "value1"
        assert cache_service.get("key2") == "value2"

    def test_cache_lua_script(self, cache_service):
        """Test executing Lua script."""
        script = "return redis.call('SET', KEYS[1], ARGV[1])"

        cache_service.eval(script, 1, "test_key", "test_value")

        # Should not raise any errors

    def test_cache_info(self, cache_service):
        """Test getting cache info."""
        info = cache_service.info()

        assert info is not None

    def test_cache_config(self, cache_service):
        """Test getting cache config."""
        config = cache_service.config()

        assert config is not None

    def test_cache_slowlog(self, cache_service):
        """Test getting slow log."""
        slowlog = cache_service.slowlog()

        assert isinstance(slowlog, list)

    def test_cache_monitor(self, cache_service):
        """Test cache monitoring."""
        monitor = cache_service.monitor()

        assert monitor is not None

    def test_cache_client_list(self, cache_service):
        """Test getting client list."""
        clients = cache_service.client_list()

        assert isinstance(clients, list)

    def test_cache_client_info(self, cache_service):
        """Test getting client info."""
        info = cache_service.client_info()

        assert info is not None

    def test_cache_ping(self, cache_service):
        """Test cache ping."""
        pong = cache_service.ping()

        assert pong is True

    def test_cache_echo(self, cache_service):
        """Test cache echo."""
        message = "test_message"

        echoed = cache_service.echo(message)

        assert echoed == message

    def test_cache_quit(self, cache_service):
        """Test cache quit."""
        cache_service.quit()

        # Should not raise any errors

    def test_cache_shutdown(self, cache_service):
        """Test cache shutdown."""
        cache_service.shutdown()

        # Should not raise any errors

    def test_cache_save(self, cache_service):
        """Test cache save."""
        cache_service.save()

        # Should not raise any errors

    def test_cache_bgsave(self, cache_service):
        """Test cache background save."""
        cache_service.bgsave()

        # Should not raise any errors

    def test_cache_lastsave(self, cache_service):
        """Test getting last save time."""
        lastsave = cache_service.lastsave()

        assert lastsave is not None

    def test_cache_dbsize(self, cache_service):
        """Test getting database size."""
        size = cache_service.dbsize()

        assert size >= 0

    def test_cache_debug_object(self, cache_service):
        """Test debug object."""
        key = "test_key"
        value = "test_value"

        cache_service.set(key, value)
        debug = cache_service.debug_object(key)

        assert debug is not None

    def test_cache_debug_segfault(self, cache_service):
        """Test debug segfault."""
        # This is a dangerous command, just test it exists
        # cache_service.debug_segfault()
        pass

    def test_cache_memory_usage(self, cache_service):
        """Test getting memory usage."""
        usage = cache_service.memory_usage()

        assert usage is not None

    def test_cache_memory_stats(self, cache_service):
        """Test getting memory stats."""
        stats = cache_service.memory_stats()

        assert stats is not None

    def test_cache_memory_purge(self, cache_service):
        """Test memory purge."""
        cache_service.memory_purge()

        # Should not raise any errors

    def test_cache_replication_info(self, cache_service):
        """Test getting replication info."""
        info = cache_service.replication_info()

        assert info is not None

    def test_cache_role(self, cache_service):
        """Test getting role."""
        role = cache_service.role()

        assert role in ["master", "slave"]

    def test_cache_sync(self, cache_service):
        """Test cache sync."""
        cache_service.sync()

        # Should not raise any errors

    def test_cache_sync_unblock(self, cache_service):
        """Test cache sync unblock."""
        cache_service.sync_unblock()

        # Should not raise any errors

    def test_cache_readonly(self, cache_service):
        """Test setting readonly mode."""
        cache_service.readonly(True)

        # Should not raise any errors

    def test_cache_readwrite(self, cache_service):
        """Test setting readwrite mode."""
        cache_service.readwrite()

        # Should not raise any errors

    def test_cache_cluster_nodes(self, cache_service):
        """Test getting cluster nodes."""
        nodes = cache_service.cluster_nodes()

        assert isinstance(nodes, list)

    def test_cache_cluster_meet(self, cache_service):
        """Test cluster meet."""
        ip = "127.0.0.1"
        port = 6379

        cache_service.cluster_meet(ip, port)

        # Should not raise any errors

    def test_cache_cluster_slots(self, cache_service):
        """Test getting cluster slots."""
        slots = cache_service.cluster_slots()

        assert isinstance(slots, list)

    def test_cache_cluster_info(self, cache_service):
        """Test getting cluster info."""
        info = cache_service.cluster_info()

        assert info is not None

    def test_cache_cluster_reset(self, cache_service):
        """Test cluster reset."""
        cache_service.cluster_reset()

        # Should not raise any errors

    def test_cache_cluster_failover(self, cache_service):
        """Test cluster failover."""
        cache_service.cluster_failover()

        # Should not raise any errors

    def test_cache_cluster_addslots(self, cache_service):
        """Test cluster add slots."""
        node_id = "node123"
        slots = [1, 2, 3]

        cache_service.cluster_addslots(node_id, slots)

        # Should not raise any errors

    def test_cache_cluster_delslots(self, cache_service):
        """Test cluster delete slots."""
        node_id = "node123"
        slots = [1, 2, 3]

        cache_service.cluster_delslots(node_id, slots)

        # Should not raise any errors

    def test_cache_cluster_setslot(self, cache_service):
        """Test cluster set slot."""
        slot = 1
        node_id = "node123"

        cache_service.cluster_setslot(slot, node_id)

        # Should not raise any errors

    def test_cache_cluster_getkeysinslot(self, cache_service):
        """Test getting keys in slot."""
        slot = 1

        keys = cache_service.cluster_getkeysinslot(slot)

        assert isinstance(keys, list)

    def test_cache_cluster_keyslot(self, cache_service):
        """Test getting key slot."""
        key = "test_key"

        slot = cache_service.cluster_keyslot(key)

        assert isinstance(slot, int)

    def test_cache_cluster_countkeysinslot(self, cache_service):
        """Test counting keys in slot."""
        slot = 1

        count = cache_service.cluster_countkeysinslot(slot)

        assert count >= 0

    def test_cache_cluster_saveconfig(self, cache_service):
        """Test cluster save config."""
        cache_service.cluster_saveconfig()

        # Should not raise any errors

    def test_cache_cluster_nodes_info(self, cache_service):
        """Test cluster nodes info."""
        node_id = "node123"

        info = cache_service.cluster_nodes_info(node_id)

        assert info is not None

    def test_cache_cluster_replicate(self, cache_service):
        """Test cluster replicate."""
        target_node_id = "target123"

        cache_service.cluster_replicate(target_node_id)

        # Should not raise any errors

    def test_cache_cluster_forget(self, cache_service):
        """Test cluster forget."""
        node_id = "node123"

        cache_service.cluster_forget(node_id)

        # Should not raise any errors

    def test_cache_cluster_flushslots(self, cache_service):
        """Test cluster flush slots."""
        cache_service.cluster_flushslots()

        # Should not raise any errors

    def test_cache_cluster_bgsave(self, cache_service):
        """Test cluster background save."""
        cache_service.cluster_bgsave()

        # Should not raise any errors

    def test_cache_cluster_slots_assigned(self, cache_service):
        """Test cluster slots assigned."""
        assigned = cache_service.cluster_slots_assigned()

        assert isinstance(assigned, list)

    def test_cache_cluster_slots_importing(self, cache_service):
        """Test cluster slots importing."""
        importing = cache_service.cluster_slots_importing()

        assert isinstance(importing, list)

    def test_cache_cluster_set_config_epoch(self, cache_service):
        """Test cluster set config epoch."""
        epoch = 123

        cache_service.cluster_set_config_epoch(epoch)

        # Should not raise any errors

    def test_cache_cluster_info_replication(self, cache_service):
        """Test cluster info replication."""
        info = cache_service.cluster_info_replication()

        assert info is not None

    def test_cache_cluster_info_nodes(self, cache_service):
        """Test cluster info nodes."""
        nodes = cache_service.cluster_info_nodes()

        assert isinstance(nodes, list)

    def test_cache_cluster_info_cluster(self, cache_service):
        """Test cluster info cluster."""
        info = cache_service.cluster_info_cluster()

        assert info is not None
