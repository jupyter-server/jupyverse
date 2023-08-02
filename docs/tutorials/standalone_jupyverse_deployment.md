In this tutorial, we will deploy Jupyverse as a standalone server on a public [OVHcloud](https://www.ovhcloud.com) instance using [Fief](https://fief.dev), and allow authentication using a [GitHub](https://github.com) account.

## OVH setup

### Create and connect to a public instance

Let's follow the guide on [Creating and connecting to your first Public Cloud instance](https://help.ovhcloud.com/csm/en-public-cloud-compute-getting-started?id=kb_article_view&sysparm_article=KB0051009). We first need to create SSH keys, so that we can connect to our instance using SSH. Enter in a terminal:

```console
$ ssh-keygen -b 4096
Generating public/private rsa key pair.
Enter file in which to save the key (/home/user/.ssh/id_rsa):
```

You can hit _Enter_. You are then asked to enter a passphrase, we will need it later.

The public key can be accessed with:

```console
$ cat ~/.ssh/id_rsa.pub
```

Copy this public key into your clipboard.

In the OVHcloud Control Panel, click on "Instances" and then "Create an instance". Choose the "B2-7" model, which is a light and general use instance, and click "Next".

Select a region of you choice and click "Next".

Select the "Ubuntu 23.04" image and click "Add a key" under "SSH key". Give it a name an paste your public key, then click "Next". Your instance should already be configured, you can click "Next" again. In the network configuration, make sure "Public mode" is checked, and click "Next". Then select your preferred billing period and click "Create an instance".

Your instance should activate shortly. You can see it has a public IP, something like `1.2.3.4`. Let's connect to the instance using this IP address:

```console
$ ssh ubuntu@1.2.3.4
The authenticity of host '1.2.3.4 (1.2.3.4)' can't be established.
ED25519 key fingerprint is SHA256:Q1&tbgX3fp9+7J90zyK0ctuKe1aqPoEY76Qi58uoSnA.
This key is not known by any other names
Are you sure you want to continue connecting (yes/no/[fingerprint])?
```
Enter "yes", then enter your passphrase. You should now be connected to your instance.

### Set up the environment

Let's install [micromamba](https://mamba.readthedocs.io/en/latest/installation.html#micromamba) and configure it:

```console
$ sudo apt install bzip2
$ curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xvj bin/micromamba
$ bin/micromamba shell init --shell bash --root-prefix=~/micromamba
$ exec bash
```

Now create a conda environment and install Python:

```console
$ micromamba create -n jupyverse
$ micromamba activate jupyverse
$ micromamba install -c conda-forge python
```

And install Jupyverse:

```console
$ pip install jupyverse[jupyterlab,auth-fief] jupyter-collaboration
```

### Set up HTTPS and NGINX

For this you will need a domain name, like [https://my.jupyverse.com](https://my.jupyverse.com), that must point to your instance through its IP address.

We'll use [NGINX and Let's Encrypt](https://www.nginx.com/blog/using-free-ssltls-certificates-from-lets-encrypt-with-nginx/) to manage SSL/TLS certificates. Enter in a terminal:

```console
$ sudo apt install certbot nginx python3-certbot-nginx
```

Create a file at `/etc/nginx/conf.d/my.jupyverse.com.conf` (note that `my.jupyverse.com` is your domain name) with the following content:

```
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    root /var/www/html;
    server_name my.jupyverse.com;
}
```

Save the file, then run this command to verify the syntax of your configuration and restart NGINX:

```console
$ sudo nginx -t && sudo nginx -s reload
```

You may have to remove the _server_ section in `/etc/nginx/sites-enabled/default`, or simply remove this file. Now run the following command to generate certificates with the NGINX plug‑in:

```console
$ sudo certbot --nginx -d my.jupyverse.com
```

After answering a few questions, you should be all set. If you look at `/etc/nginx/conf.d/my.jupyverse.com.conf` again, you should see that it was modified. Add the following `location` sections at the bottom:

```
server {
    root /var/www/html;
    server_name my.jupyverse.com;

    listen [::]:443 ssl ipv6only=on; # managed by Certbot
    listen 443 ssl; # managed by Certbot
    ssl_certificate /etc/letsencrypt/live/my.jupyverse.com/fullchain.pem; # managed by Certbot
    ssl_certificate_key /etc/letsencrypt/live/my.jupyverse.com/privkey.pem; # managed by Certbot
    include /etc/letsencrypt/options-ssl-nginx.conf; # managed by Certbot
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem; # managed by Certbot

    location / {
        proxy_pass http://localhost:8000;
    }
    location ~ \/api\/kernels\/.+\/channels {
        proxy_pass http://localhost:8000;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
    }
    location ~ \/terminals\/websocket\/.+ {
        proxy_pass http://localhost:8000;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
    }
    location ~ \/api\/collaboration\/room\/.+ {
        proxy_pass http://localhost:8000;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
    }

}
```

## Fief setup

You will first need to [create a Fief account](https://fief.fief.dev/register). At the time of writing, you can join the beta for free.

Then, [create a workspace](https://docs.fief.dev/getting-started/workspace). Let's call it "jupyverse".

You will be asked where to store your data. Let's choose Fief's cloud database.

Now that your workspace is created, we need to configure our [tenant](https://docs.fief.dev/configure/tenants). There can be multiple tenants per workspace, but a default tenant was created with the same name as your workspace, so we'll use this one. Since we want to allow GitHub authentication, we first need to create a corresponding OAuth provider.

Click on "OAuth Providers" on the left, and then "create OAuth Provider" on the right. Choose GitHub in the provider list. You can see that we need to provide a client ID and secret. In order to get those, we need to register a new GitHub App. Leave this window open, we'll get back to it later.

You can go through the [steps given by Fief](https://docs.fief.dev/configure/oauth-providers/#github) to [create a GitHub App](https://github.com/settings/apps/new). In the "GitHub App name", enter "Jupyverse". In "Homepage URL", enter the URL of your public instance, [https://my.jupyverse.com](https://my.jupyverse.com). In "Callback URL", enter [https://jupyverse.fief.dev/oauth/callback](https://jupyverse.fief.dev/oauth/callback). Make sure "Expire user authorization tokens" and "Request user authorization (OAuth) during installation" are checked. Uncheck "Active" for "Webhook". In "Account permissions", give "Read-only" access to "Email addresses". Finally, hit the "Create GitHub App" button at the bottom.

If this was successful, you can now generate a private key. Click on "Generate a new client secret", and copy it somewhere safe. Let's also copy the client ID shown on the same page. Now let's go back to the Fief browser window where we were creating our GitHub OAuth provider, and enter the client ID and Secret, and hit "Create" (also remove any scope if present).

Let's click on "Tenants" on the left, and then on our "jupyverse" tenant, then "Edit tenant" on the right. We want registration to be allowed, and it should be checked by default. In "OAuth Providers", choose "GitHub" and click "Update".

Click on "Clients" on the left. A client was already created, click on it and then click on "Edit Client" on the right. We need to change the "Redirect URIs", so let's delete the existing one and click on "Add", then enter [https://my.jupyverse.com/auth-callback](location ~ \/api\/kernels\/.+\/channels {
        proxy_pass http://localhost:8000;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
    }
    location ~ \/terminals\/websocket\/.+ {
        proxy_pass http://localhost:8000;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
    }
    location ~ \/api\/collaboration\/room\/.+ {
        proxy_pass http://localhost:8000;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
    }), and click "Update".

Now let's click on "API Keys" on the left, then "Create API Key" on the right. Name it and click "Create". This should give you a key, copy it somewhere safe.

We need to create user fields. Click on "User fields" on the left, then "Create User field" on the right. Enter each of the following fields. The name is automatically copied into "Slug", and the "String" type is chosen by default. Enter a default value if any, and check "Ask at profile update":

| Name | Default value |
|---|---|
| `workspace` | `{}`|
| `settings` | `{}`|
| `username` | |
| `name` | |
| `display_name` | |
| `initials` | |
| `color` | |
| `avatar_url` | |

We also need to create permissions. Click on "Access control" on the left, then "Permissions". Enter each of the following values into "Name" and "Codename", and click "Create Permission" on the right.

| Name | Codename |
|---|---|
| `Read contents` | `contents:read` |
| `Read kernelspecs` | `kernelspecs:read` |
| `Read kernels` | `kernels:read` |
| `Read sessions` | `sessions:read` |
| `Read terminals` | `terminals:read` |
| `Read yjs` | `yjs:read` |
| `Write contents` | `contents:write` |
| `Write kernels` | `kernels:write` |
| `Write sessions` | `sessions:write` |
| `Write terminals` | `terminals:write` |
| `Write yjs` | `yjs:write` |
| `Execute kernels` | `kernels:execute` |
| `Execute terminals` | `terminals:execute` |

## Run the server

We are ready to run Jupyverse. Let's do it in a separate directory, replacing in the following command:

- `fief_client_id` with our Fief client ID,
- `fief_client_secret` with our Fief client secret,
- `fief_admin_api` with our API key,
- `fief_oauth_provider_id` with our GitHub OAuth provider ID.

```console
$ mkdir jupyverse && cd jupyverse
$ jupyverse \
    --set auth_fief.base_url=https://jupyverse.fief.dev \
    --set auth_fief.client_id=fief_client_id \
    --set auth_fief.client_secret=fief_client_secret \
    --set auth_fief.admin_api_key=fief_admin_api \
    --set auth_fief.oauth_provider_id=fief_oauth_provider_id \
    --set auth_fief.callback_url=https://my.jupyverse.com/auth-callback
```

Now open a browser window at [https://my.jupyverse.com](https://my.jupyverse.com), and click "Sign in with GitHub". Enter your credentials and click "Sign in". If you have two-factor authentication enabled on your GitHub account, you may have to approve the request by entering a code e.g. in your mobile phone GitHub application. You should be redirected back to Fief, where you are asked to provide an email to finalize the sign up. It should be pre-filled with your GitHub email. Just click "Finalize sign up".

After a while, JupyterLab should start. You should see your avatar in the top-right corner. Any other connected user should be visible in the "Collaboration" tab on the left, and if you work on the same notebook, you should see them collaborate live!
