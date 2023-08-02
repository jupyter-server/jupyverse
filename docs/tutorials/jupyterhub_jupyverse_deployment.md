In this tutorial, we will deploy Jupyverse through JupyterHub on a public [OVHcloud](https://www.ovhcloud.com) instance, and allow authentication using a [GitHub](https://github.com) account.

## OVH setup

### Create and connect to a public instance

Let's follow the guide on [Creating and connecting to your first Public Cloud instance](https://help.ovhcloud.com/csm/en-public-cloud-compute-getting-started?id=kb_article_view&sysparm_article=KB0051009). We first need to create SSH keys, so that we can connect to our instance using SSH. Enter in a terminal:

```bash
ssh-keygen -b 4096
# Generating public/private rsa key pair.
# Enter file in which to save the key (/home/user/.ssh/id_rsa):
```

You can hit _Enter_. You are then asked to enter a passphrase, we will need it later.

The public key can be accessed with:

```bash
cat ~/.ssh/id_rsa.pub
```

Copy this public key into your clipboard.

In the OVHcloud Control Panel, click on "Instances" and then "Create an instance". Choose the "B2-7" model, which is a light and general use instance, and click "Next".

Select a region of you choice and click "Next".

Select the "Ubuntu 23.04" image and click "Add a key" under "SSH key". Give it a name an paste your public key, then click "Next". Your instance should already be configured, you can click "Next" again. In the network configuration, make sure "Public mode" is checked, and click "Next". Then select your preferred billing period and click "Create an instance".

Your instance should activate shortly. You can see it has a public IP, something like `1.2.3.4`. Let's connect to the instance using this IP address:

```bash
ssh ubuntu@1.2.3.4
# The authenticity of host '1.2.3.4 (1.2.3.4)' can't be established.
# ED25519 key fingerprint is SHA256:Q1&tbgX3fp9+7J90zyK0ctuKe1aqPoEY76Qi58uoSnA.
# This key is not known by any other names
# Are you sure you want to continue connecting (yes/no/[fingerprint])?
```
Enter "yes", then enter your passphrase. You should now be connected to your instance.

### Set up the environment

Let's install [micromamba](https://mamba.readthedocs.io/en/latest/installation.html#micromamba) and configure it:

```bash
sudo apt install bzip2
curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xvj bin/micromamba
bin/micromamba shell init --shell bash --root-prefix=~/micromamba
exec bash
```

Now create a conda environment and install Python and Node.js:

```bash
micromamba create -n jupyterhub
micromamba activate jupyterhub
micromamba install -c conda-forge python nodejs
```

And install JupyterHub and Jupyverse:

```bash
pip install jupyverse[jupyterlab,auth-jupyterhub]
pip install jupyter-collaboration
pip install oauthenticator
pip install https://github.com/davidbrochart/jupyterhub/archive/jupyverse.zip
npm install -g configurable-http-proxy
```

### Set up HTTPS

For this you will need a domain name, like [https://my.jupyverse.com](https://my.jupyverse.com), that must point to your instance through its IP address.

We'll use the [Certbot](https://certbot.eff.org) ACME client to manage SSL/TLS certificates. Enter in a terminal:

```bash
sudo snap install --classic certbot
sudo ln -s /snap/bin/certbot /usr/bin/certbot
sudo certbot certonly --standalone
```

## Create a GitHub App

We'll [register a new GitHub App](https://github.com/settings/apps/new). In the "GitHub App name", enter "JupyterHub-Jupyverse". In "Homepage URL", enter the URL of your public instance, [https://my.jupyverse.com](https://my.jupyverse.com). In "Callback URL", enter [https://my.jupyverse.com/hub/oauth_callback](https://my.jupyverse.com/hub/oauth_callback). Make sure "Expire user authorization tokens" and "Request user authorization (OAuth) during installation" are checked. Uncheck "Active" for "Webhook". In "Account permissions", give "Read-only" access to "Email addresses". Finally, hit the "Create GitHub App" button at the bottom.

If this was successful, you can now generate a private key. Click on "Generate a new client secret", and copy it somewhere safe. Let's also copy the client ID shown on the same page.

## Run the server

### Configure JupyterHub

Let's create a JupyterHub configuration file. Fill in the `allowed_users` and `admin_users` as you like.

```bash
sudo mkdir /etc/jupyterhub
sudo vim /etc/jupyterhub/jupyterhub_config.py
```

With the following content:

```py
# jupyterhub_config.py file
c = get_config()

import os
pjoin = os.path.join

runtime_dir = os.path.join('/srv/jupyterhub')

# Allows multiple single-server per user
c.JupyterHub.allow_named_servers = True

# https on :443
c.JupyterHub.port = 443
c.JupyterHub.ssl_key = '/etc/letsencrypt/live/jupyterhub.quantstack.net/privkey.pem'
c.JupyterHub.ssl_cert = '/etc/letsencrypt/live/jupyterhub.quantstack.net/cert.pem'

# put the JupyterHub cookie secret and state db
# in /var/run/jupyterhub
c.JupyterHub.cookie_secret_file = pjoin(runtime_dir, 'cookie_secret')
c.JupyterHub.db_url = pjoin(runtime_dir, 'jupyterhub.sqlite')
# or `--db=/path/to/jupyterhub.sqlite` on the command-line

# use GitHub OAuthenticator for local users
c.JupyterHub.authenticator_class = 'oauthenticator.LocalGitHubOAuthenticator'
c.GitHubOAuthenticator.oauth_callback_url = os.environ['OAUTH_CALLBACK_URL']

# create system users that don't exist yet
c.LocalAuthenticator.create_system_users = True

# specify users and admin
c.Authenticator.allowed_users = {'rgbkrk', 'minrk', 'jhamrick'}
c.Authenticator.admin_users = {'jhamrick', 'rgbkrk'}
```

### Launch JupyterHub

Let's launch JupyterHub with some environment variables. Use the GitHub client ID and secret of your GitHub App.

```bash
sudo mkdir /srv/jupyterhub
chmod -R o+rx /home/ubuntu
mkdir jupyterhub
cd jupyterhub
sudo env "PATH=$PATH" \
"OAUTH_CALLBACK_URL=https://my.jupyverse.com/hub/oauth_callback" \
"GITHUB_CLIENT_ID=github_id" \
"GITHUB_CLIENT_SECRET=github_secret" \
jupyterhub -f /etc/jupyterhub/jupyterhub_config.py
```

Now open a browser window at [https://my.jupyverse.com](https://my.jupyverse.com), and click "Sign in with GitHub". Enter your credentials and click "Sign in". If you have two-factor authentication enabled on your GitHub account, you may have to approve the request by entering a code e.g. in your mobile phone GitHub application.

After a while, JupyterLab should start. You should see an icon for your user in the top-right corner, with your initials. Any other connected user should be visible in the "Collaboration" tab on the left, and if you work on the same notebook, you should see them collaborate live!
