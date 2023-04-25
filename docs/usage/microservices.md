Jupyverse's modularity allows to run services quite independently from each other, following a microservice architecture. This can be useful when resources are provided by separate systems, or just to have a clear separation of concerns. For instance, you may want to host the contents on AWS and the kernels on Google Cloud, or on different machines in your private network. One way to achieve this is to use a reverse proxy that will forward client requests to the corresponding Jupyverse server. We will show how to do that using [Nginx](https://en.wikipedia.org/wiki/Nginx) on a single computer with local servers. This can serve as a basis for more complicated architectures involving remote servers.

## Nginx setup

Nginx is a web server that can also be used as a reverse proxy. We will use it to forward client requests to separate Jupyverse servers, based on the request URL.

First, install Nginx in its own environment:
```bash
micromamba create -n nginx
micromamba activate nginx
micromamba install -c conda-forge nginx
```
We will just edit the default configuration file at `~/micromamba/envs/nginx/etc/nginx/sites.d/default-site.conf` with the following:
```
server {
    listen       8000;
    server_name  localhost;

    location / {
        proxy_pass http://localhost:8001;
    }

    location /api/kernelspecs {
        proxy_pass http://localhost:8002;
    }
    location /api/kernels {
        proxy_pass http://localhost:8002;
    }
    location ~ \/api\/kernels\/.+\/channels {
        proxy_pass http://localhost:8002;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
    }
    location /api/sessions {
        proxy_pass http://localhost:8002;
    }
}
```
Our Nginx server will listen at `http://localhost:8000`. This is the URL the client will see, i.e. the one we enter in the browser.

Our Jupyverse servers will run on:

- `http://localhost:8001` for everything except the kernels API. This means that this server doesn't have the ability to run user code, and thus cannot be used to execute a notebook.
- `http://localhost:8002` for the kernels API. This server only deals with executing code in a kernel. It cannot serve JupyterLab's UI, for instance.

Together, these Jupyverse servers can serve a full JupyterLab API. But because they run on different machines (not exactly in this case, since ports `8001` and `8002` are on the same machine, but let's pretend), we need to make them appear as a unique server. That is the role of the reverse proxy server.

!!! note
    WebSocket forwarding requires extra-configuration. Here, we use a `regex` to redirect `/api/kernels/{kernel_id}/channels`, which is the WebSocket endpoint for the kernel protocol. We also set the `Upgrade` and `Connection` headers used to upgrade the connection from HTTP to WebSocket.

We can now run our reverse proxy server. Just enter:
```bash
nginx
```

## Jupyverse setup

### Server 1: everything but kernels

Let's create a new environment in a new terminal:
```bash
micromamba create -n jupyverse1
micromamba activate jupyverse1
micromamba install -c conda-forge python
```
Since we don't want to install the fully-fledged Jupyverse server, we will install the required plugins individually:
```bash
pip install fps-auth
pip install fps-contents
pip install fps-frontend
pip install fps-lab
pip install fps-jupyterlab
pip install fps-login
```
Now we launch Jupyverse at port `8001` and pass our own authentication token. In production, you would either create your own token, or let Jupyverse create it, and copy/paste it for server 2.
```bash
jupyverse --port=8001 --set auth.token=5e9b01f993bc4fb48b2bf6958fd22981
```
If you open your browser at `http://127.0.0.1:8000` (the URL of the Nginx reverse proxy), you should see the JupyterLab UI you're used to. But if you look closer, you can see that there is no icon for kernels in the launcher tab. And in the terminal where you launched Jupyverse, you will see a bunch of `404` for requests at e.g. `GET /api/kernels`. This is expected, because we didn't install the kernels plugin. You can still use JupyterLab if you don't want to execute a notebook, for instance. But let's close it for now, and install the kernels plugin in another Jupyverse instance.

### Server 2: the kernels API

Let's create a new environment in a new terminal:
```bash
micromamba create -n jupyverse2
micromamba activate jupyverse2
micromamba install -c conda-forge python
```
This time, we only want to install the kernels plugin. Let's not forget to install a kernel, such as `ipykernel`:
```bash
pip install fps-kernels
pip install fps-auth
pip install fps-frontend
pip install ipykernel
```
Launch Juyverse at port `8002` with the same authentication token as for server 1:
```bash
jupyverse --port=8002 --set auth.token=5e9b01f993bc4fb48b2bf6958fd22981
```
Now if you re-open a browser at `http://127.0.0.1:8000`, you should be able to create or open a notebook, and execute it.
