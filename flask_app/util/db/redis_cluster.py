from rediscluster import RedisCluster

startup_nodes = [{"host": "192.168.100.251", "port": "7000"}]

rc = RedisCluster(
    startup_nodes=startup_nodes,
    decode_responses=True,
    host_port_remap=[
        {
            'from_host': '172.17.0.8',
            'from_port': 7000,
            'to_host': '192.168.100.251',
            'to_port': 7000,
        },
               {
            'from_host': '172.17.0.8',
            'from_port': 7001,
            'to_host': '192.168.100.251',
            'to_port': 7001,
        },
                       {
            'from_host': '172.17.0.8',
            'from_port': 7002,
            'to_host': '192.168.100.251',
            'to_port': 7002,
        },
        {
            'from_host': '172.17.0.8',
            'from_port': 7003,
            'to_host': '192.168.100.251',
            'to_port': 7003,
        },
        {
            'from_host': '172.17.0.8',
            'from_port': 7004,
            'to_host': '192.168.100.251',
            'to_port': 7004,
        },
        {
            'from_host': '172.17.0.8',
            'from_port': 7005,
            'to_host': '192.168.100.251',
            'to_port': 7005,
        },
    ]
)

print(rc.connection_pool.nodes.nodes)

## Test the client that it can still send and recieve data from the nodes after the remap has been done
print(rc.ping())
print(rc.set('foo', 'bar'))
print(rc.get('foo'))

with rc.pipeline() as p:
    p.set('sad', 'asd')
    p.set('zcx', 'vsa')
    print(p.execute())

p = rc.pipeline()
p.set('ert', 'tre')
p.set('wer', 'rew')
print(p.execute())

rc.mset({'n2': 'v2', 'n1': 'v1'})
print(rc.mget('n1', 'n2'))


