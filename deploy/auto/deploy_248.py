
import getpass
from fabric import Connection, Config
from invoke import Responder

backend_ssh_url = 'git@github.com:Dormitabnia/power_model_system.git'
frontend_ssh_url = 'git@github.com:theoYe/csu_thermal_power_fontend.git'
# result = Connection('grid-251-external').run('uname -a', hide=True)

# sudo_pass = getpass.getpass("What's your sudo password?")


def update_backend_code(c):
    sudopass = Responder(
    pattern=r'\[sudo\] password for',
    response='dajia315\n',
        )
    fingerprint = Responder(
    pattern='Are you sure you want to continue',
    response='yes\n')
    c.run(f'supervisorctl status')
    # # c.run(f'git remote  add origin_ssh {backend_ssh_url}', hide=True, pty=True, watchers=[sudopass,fingerprint])
    # # c.run(f'git stash', hide=True, pty=True, watchers=[sudopass,fingerprint])
    c.run(f'proxychains4 git fetch origin_ssh test',
            pty=True, watchers=[sudopass, fingerprint])
    c.run(f'git merge origin_ssh/test',
            pty=True, watchers=[sudopass, fingerprint])
    c.run(f'supervisorctl restart apscheduler')
    # c.run(f'service nginx restart')
    # c.run(f'supervisorctl status')
    
    
    # c.run('service nginx status')
    # c.run('cp -r /workspace/power_model_system/deploy/nginx/nginx.conf /etc/nginx/nginx.conf')
    # c.run('service nginx restart')
    # c.run('service nginx status')

def deploy_to_248(backend=True, frontend=True):
    if backend:
        c = Connection('248-external-production-root')
        with c.cd('/workspace/power_model_system'):
            update_backend_code(c)
           

    if frontend:
        # sudo_pass='dajia315'
        # config=Config(overrides={'sudo': {'password': sudo_pass}})
        
        sudopass = Responder(
        pattern=r'\[sudo\] password for',
        response='dajia315\n',
            )
        participating_interest = Responder(
            pattern='Are you interested in participating',
            response='No\n'
        )
        fingerprint = Responder(
            pattern='Are you sure you want to continue',
            response='yes\n'
        )
        passphrase = Responder(
            pattern='Enter passphrase for key',
            response='\n'
        )      
        
        c=Connection('248-external-admin1')
        front_end_path = '/lab-pool/LabProjects/hdm/production/frontend/'
        with c.cd(front_end_path):
            c.run(f'sudo git stash', pty=True, watchers=[sudopass])
            # c.run(f'git remote  add origin_ssh {frontend_ssh_url}', hide=True, watchers=[sudopass])
            c.run(f'sudo proxychains4 git pull origin_ssh test-251', pty=True, watchers=[sudopass,fingerprint,passphrase])
            
            c.run(f'sudo chown -R admin1 ./static/config.json nuxt.config.js plugins/websocket.js', pty=True, watchers=[sudopass,fingerprint,passphrase])
            c.run(f'sudo chgrp -R admin1 ./static/config.json nuxt.config.js plugins/websocket.js', pty=True, watchers=[sudopass,fingerprint,passphrase])
            
            c.put('/workspace/power_model_system/deploy/auto/config/248/config.js', remote=front_end_path+'static/config.json')
            c.put('/workspace/power_model_system/deploy/auto/config/248/nuxt.config.js', remote=front_end_path+'nuxt.config.js')
            c.put('/workspace/power_model_system/deploy/auto/config/248/websocket.js', remote=front_end_path+'plugins/websocket.js')

            c.run('sudo proxychains4 npm i', pty=True, watchers=[sudopass,participating_interest])
            c.run('sudo npm run generate', pty=True, watchers=[sudopass,participating_interest])
            
        


if __name__ == '__main__':
    deploy_to_248(backend=True, frontend=False)
# # c  = Connection('248-external-admin1')
# result = Connection('248-external-admin1').run('uname -a', hide=True)
# print(result)

# c  = Connection('248-external-production-root')
