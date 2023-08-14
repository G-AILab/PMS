import getpass
from fabric import Connection,Config
from invoke import Responder

backend_ssh_url = 'git@github.com:Dormitabnia/power_model_system.git'
frontend_ssh_url = 'git@github.com:theoYe/csu_thermal_power_fontend.git'
# result = Connection('grid-251-external').run('uname -a', hide=True)

# sudo_pass = getpass.getpass("What's your sudo password?")

def update_hxy_code(backend=True, frontend=True):
    # if backend:
    #     c  = Connection('248-external-production-root')
    #     with c.cd('/workspace/power_model_system'):
    #         c.run(f'supervisorctl status')
    #         c.run(f'git remote  add origin_ssh {backend_ssh_url}', hide=True)
    #         c.run(f'proxychains4 git fetch origin_ssh production')
    #         c.run(f'git merge origin_ssh/production')
    #         c.run(f'supervisorctl restart all')
    #         c.run(f'supervisorctl status')
            
    if frontend:
        sudo_pass = 'dajia315' #getpass.getpass("What's your sudo password?") #'dajia315'
        config = Config(overrides={'sudo': {'password': sudo_pass}})
        c  = Connection('251-external-grid', config=config)
        sudopass = Responder(
        pattern=r'\[sudo\] password for grid:',
        response='dajia315\n',
    )
        participating_interest = Responder(
            pattern='Are you interested in participating',
            response='No\n'
        )
        with c.cd('/lab-pool/LabProjects/hdm/production/frontend'):
            # c.run(f'sudo git remote  add origin_ssh {frontend_ssh_url}', hide=True, pty=True, watchers=[sudopass])
            c.run(f'sudo git pull origin_ssh dev-hxy', hide=True, pty=True, watchers=[sudopass])
            c.run('sudo proxychains4 npm i', pty=True, watchers=[sudopass,participating_interest])
            c.run('sudo npm run generate', pty=True, watchers=[sudopass,participating_interest])
            # c.sudo('proxychains4 npm i', pty=True, watchers=[sudopass])
            # c.sudo('npm run generate', pty=True, watchers=[sudopass])
    
update_hxy_code()