from flask_app.apschedule_tasks import _get_config
import paramiko
import re
import os
from paramiko.ssh_exception import SSHException


servers_config = _get_config.REMOTE_SERVERS
res_dir = _get_config.SERVER_STAT_RES_DIR
private_key = paramiko.RSAKey.from_private_key_file(_get_config.PRIVATE_KEY_PATH)

mem_pattern = re.compile(r'(:|：)\s+(\d+)\s+(\d+)')


def get_remote_server_stats():
    if not os.path.exists(res_dir):
        os.makedirs(res_dir)

    for server_id, server_user, server_host, server_port in servers_config:
        monitor(server_user, server_host, server_port, server_id)


def get_mem_usage(ssh_client):
    mem_usage = None
    stdin, stdout, stderr = ssh_client.exec_command('free | grep -E "Mem|内存"')
    out_str = stdout.read().decode('utf-8')
    if out_str and out_str != '':
        tmp = mem_pattern.findall(out_str)
        print("tmp", tmp, out_str)
        used_mem = int(tmp[0][2])
        total_mem = int(tmp[0][1])
        mem_usage = used_mem / total_mem
    return mem_usage



def get_cpu_usage(ssh_client):
    cpu_usage = None
    stdin, stdout, stderr = ssh_client.exec_command("top -b -n1 | sed -n '3p' | awk '{print $2}'")
    out_str = stdout.read().decode('utf-8')
    if out_str and out_str != '':
        cpu_usage = out_str.strip()
        cpu_usage = eval(cpu_usage) / 100
    return cpu_usage


def get_gpu_usage(ssh_client):
    gpu_usages = None
    stdin, stdout, stderr = ssh_client.exec_command("nvidia-smi dmon -c 1 -s um")
    out_str = stdout.read().decode('utf-8')
    if out_str != '':
        lines = out_str.strip().split('\n')
        gpu_usages = [int(device.split()[1]) / 100 for device in lines[2:]]  # [0.1, 0.2, 1.0]
    return gpu_usages


def monitor(username, host, port, server_id):
    try:
        with paramiko.Transport((host, port)) as transport:
            transport.connect(username=username, pkey=private_key)

            with paramiko.SSHClient() as ssh:
                ssh._transport = transport

                mem_usage = get_mem_usage(ssh)
                cpu_usage = get_cpu_usage(ssh)
                gpu_usages = get_gpu_usage(ssh)
            # print('CPU: {} % | MEM: {} % | GPU: {}'.format(cpu_usage, mem_usage, str(gpu_usages)))

        with open(os.path.join(res_dir, '{}_monitor.txt'.format(server_id)), 'w') as f:
            f.write('cpu: {}\nmemory: {}\ngpu: {}'.format(cpu_usage, mem_usage, str(gpu_usages)))
    except SSHException or OSError or EOFError:
        return
    except Exception:
        raise
