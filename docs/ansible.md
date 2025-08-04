# Ansible Deployment Guide

This guide covers the Ansible automation used to deploy Homelab.

## Overview

Homelab uses Ansible for automated deployment to ensure consistent, repeatable deployments.

## Prerequisites

### Local Machine

Install Ansible:
```bash
# Using pip
pip install ansible

# macOS with Homebrew
brew install ansible

# Ubuntu/Debian
sudo apt update
sudo apt install ansible
```

### Target Server

Requirements:
- SSH access
- Python 3.12+
- sudo privileges

## Directory Structure

```
deploy/
├── ansible.cfg          # Ansible configuration
├── deploy.yml          # Main deployment playbook
├── inventory/
│   └── hosts.yml       # Server inventory
├── host_vars/
│   └── production.yml  # Host-specific variables
├── templates/          # Jinja2 templates
│   ├── env.template.j2
│   └── systemd.service.j2
├── vars.yml            # Shared variables
└── secrets.yml         # Encrypted secrets (Ansible Vault)
```

## Configuration Files

### ansible.cfg

```ini
[defaults]
inventory = inventory/hosts.yml
host_key_checking = False
stdout_callback = yaml
```

### inventory/hosts.yml

```yaml
all:
  hosts:
    production:
      ansible_host: macmini.fritz.box
      ansible_user: jochen
      ansible_python_interpreter: /usr/bin/python3
```

### host_vars/production.yml

```yaml
fqdn: home.wersdoerfer.de
deploy_environment: production
username: homelab
site_path: /home/{{ username }}/site
django_settings_module: config.settings.production
port: 8001
```

## Playbook Structure

### Main Deploy Playbook

The `deploy.yml` playbook performs these tasks:

1. **User Setup**
   ```yaml
   - name: Create application user
     user:
       name: "{{ username }}"
       shell: /usr/bin/bash
       home: "/home/{{ username }}"
   ```

2. **Directory Structure**
   ```yaml
   - name: Create directory structure
     file:
       path: "{{ item }}"
       state: directory
       owner: "{{ username }}"
     loop:
       - "{{ site_path }}"
       - "{{ site_path }}/logs"
       - "{{ site_path }}/backups"
   ```

3. **Code Deployment**
   ```yaml
   - name: Clone/update repository
     git:
       repo: "{{ git_repo }}"
       dest: "{{ site_path }}"
       version: "{{ git_branch | default('main') }}"
     become_user: "{{ username }}"
   ```

4. **Dependencies**
   ```yaml
   - name: Install Python dependencies
     command: uv sync
     args:
       chdir: "{{ site_path }}"
     become_user: "{{ username }}"
   ```

5. **Configuration**
   ```yaml
   - name: Create .env file
     template:
       src: env.template.j2
       dest: "{{ site_path }}/.env"
       owner: "{{ username }}"
       mode: '0600'
   ```

6. **Database**
   ```yaml
   - name: Run migrations
     command: .venv/bin/python manage.py migrate
     args:
       chdir: "{{ site_path }}"
     environment:
       DJANGO_SETTINGS_MODULE: "{{ django_settings_module }}"
     become_user: "{{ username }}"
   ```

7. **Static Files**
   ```yaml
   - name: Collect static files
     command: .venv/bin/python manage.py collectstatic --noinput
     args:
       chdir: "{{ site_path }}"
     become_user: "{{ username }}"
   ```

8. **Service Setup**
   ```yaml
   - name: Create systemd service
     template:
       src: systemd.service.j2
       dest: "/etc/systemd/system/{{ username }}.service"
     notify: restart service
   ```

## Templates

### env.template.j2

```django
DJANGO_SETTINGS_MODULE={{ django_settings_module }}
DJANGO_SECRET_KEY={{ django_secret_key }}
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS={{ fqdn }},{{ ansible_host }}
DATABASE_URL=sqlite:///{{ site_path }}/db.sqlite3
DJANGO_ADMIN_URL={{ admin_url }}
```

### systemd.service.j2

```ini
[Unit]
Description={{ username }} web application
After=network.target

[Service]
Type=simple
User={{ username }}
WorkingDirectory={{ site_path }}
Environment="DJANGO_SETTINGS_MODULE={{ django_settings_module }}"
ExecStart={{ site_path }}/.venv/bin/granian \
    --interface wsgi \
    config.wsgi:application \
    --host 0.0.0.0 \
    --port {{ port }} \
    --workers 2
Restart=always

[Install]
WantedBy=multi-user.target
```

## Secret Management

### Creating Secrets

1. Create `secrets.yml`:
   ```yaml
   django_secret_key: "your-secret-key-here"
   admin_url: "secret-admin/"
   db_encryption_key: "encryption-key"
   ```

2. Encrypt with Ansible Vault:
   ```bash
   ansible-vault encrypt deploy/secrets.yml
   ```

3. Edit encrypted file:
   ```bash
   ansible-vault edit deploy/secrets.yml
   ```

### Using Secrets

Include in playbook:
```yaml
- name: Include secrets
  include_vars: secrets.yml
```

Run playbook with vault password:
```bash
ansible-playbook deploy.yml --ask-vault-pass
```

Or use password file:
```bash
ansible-playbook deploy.yml --vault-password-file ~/.vault_pass
```

## Running Deployments

### First Deployment

```bash
cd deploy
ansible-playbook deploy.yml --limit production --ask-vault-pass
```

### Update Deployment

```bash
# Quick update (code only)
ansible-playbook deploy.yml --limit production --tags code

# Full deployment
ansible-playbook deploy.yml --limit production
```

### Rollback

```bash
# Deploy specific version
ansible-playbook deploy.yml -e git_branch=v1.0.0
```

## Advanced Usage

### Tags

Use tags for partial deployments:

```yaml
- name: Update code
  git:
    repo: "{{ git_repo }}"
    dest: "{{ site_path }}"
  tags: [code]

- name: Update configuration
  template:
    src: env.template.j2
    dest: "{{ site_path }}/.env"
  tags: [config]
```

Run specific tags:
```bash
ansible-playbook deploy.yml --tags "code,config"
```

### Handlers

Define handlers for service management:

```yaml
handlers:
  - name: restart service
    systemd:
      name: "{{ username }}"
      state: restarted
      daemon_reload: yes
    become: yes
```

### Variables

Override variables from command line:
```bash
ansible-playbook deploy.yml -e port=8002 -e debug=true
```

## Backup and Restore

### Backup Playbook

```yaml
---
- hosts: production
  tasks:
    - name: Create backup
      archive:
        path: "{{ site_path }}/db.sqlite3"
        dest: "{{ site_path }}/backups/db-{{ ansible_date_time.epoch }}.tar.gz"
      become_user: "{{ username }}"
    
    - name: Download backup
      fetch:
        src: "{{ site_path }}/backups/db-{{ ansible_date_time.epoch }}.tar.gz"
        dest: ./backups/
        flat: yes
```

### Restore Playbook

```yaml
---
- hosts: production
  tasks:
    - name: Stop service
      systemd:
        name: "{{ username }}"
        state: stopped
    
    - name: Upload backup
      copy:
        src: "{{ backup_file }}"
        dest: "{{ site_path }}/db.sqlite3"
        owner: "{{ username }}"
    
    - name: Start service
      systemd:
        name: "{{ username }}"
        state: started
```

## Monitoring Deployment

### Check Deployment Status

```bash
# Test connection
ansible production -m ping

# Check service status
ansible production -m systemd -a "name=homelab" --become

# View logs
ansible production -m command -a "journalctl -u homelab -n 20" --become
```

### Ad-hoc Commands

```bash
# Restart service
ansible production -m systemd -a "name=homelab state=restarted" --become

# Check disk space
ansible production -m command -a "df -h"

# Update code only
ansible production -m git -a "repo=https://github.com/user/homelab dest=/home/homelab/site"
```

## Troubleshooting

### SSH Connection Failed

```bash
# Test SSH
ssh user@macmini.fritz.box

# Add SSH key
ssh-copy-id user@macmini.fritz.box

# Check inventory
ansible-inventory --list
```

### Python Not Found

Update inventory:
```yaml
ansible_python_interpreter: /usr/bin/python3.12
```

### Permission Denied

Ensure sudo access:
```bash
ansible production -m command -a "sudo -l" --become --ask-become-pass
```

### Service Won't Start

Debug with verbose output:
```bash
ansible-playbook deploy.yml -vvv
```

## Best Practices

1. **Test First**: Use `--check` for dry runs
2. **Version Control**: Tag releases in git
3. **Backup**: Always backup before deployment
4. **Secrets**: Never commit unencrypted secrets
5. **Idempotency**: Ensure playbooks can run multiple times
6. **Documentation**: Document custom configurations

## Security Considerations

1. **Vault**: Always encrypt sensitive data
2. **SSH Keys**: Use key-based authentication
3. **Firewall**: Limit SSH access
4. **Sudo**: Use specific sudo rules
5. **Audit**: Log all deployments

## Extending Deployment

### Multiple Environments

```yaml
# inventory/hosts.yml
all:
  children:
    production:
      hosts:
        prod1:
          ansible_host: server1.example.com
    staging:
      hosts:
        stage1:
          ansible_host: staging.example.com
```

### Role-based Organization

```
deploy/
├── roles/
│   ├── common/
│   ├── database/
│   ├── app/
│   └── webserver/
└── site.yml
```

### CI/CD Integration

```yaml
# .github/workflows/deploy.yml
- name: Deploy to production
  run: |
    ansible-playbook deploy/deploy.yml \
      --inventory deploy/inventory/hosts.yml \
      --limit production \
      --vault-password-file ${{ secrets.VAULT_PASS }}
```