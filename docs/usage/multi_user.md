Jupyverse supports multiple users working collaboratively. Depending on the chosen authentication method, access to the server can be finer-grained. For instance, it is possible to require users to create an account before they can log in, and to give them permissions restricting access to specific resources. It is also possible to let them log in as anonymous users. The authentication method largely depends on the desired level of security.

## Collaborative editing

The first thing to do is to install the Jupyter collaboration package:
```bash
pip install jupyter-collaboration
```
Jupyverse must then be launched in collaborative mode:
```bash
jupyverse --set frontend.collaborative=true
```
The collaborative mode will handle users through the [auth plugin](../../plugins/auth) you have installed, which will provide user identity.

## Identity provider

The real power of collaborative editing comes with proper user authentication and authorization. Jupyverse comes with several "auth plugins", that will be described below, but you can implement your own. It just has to follow a defined [API](../../plugins/auth/#api).

### Using fps-auth

#### Token or no authentication

It can be enabled by launching:
```bash
jupyverse --set frontend.collaborative=true --set auth.mode=token
```
This uses the token authentication, the same as described in the [single user mode](../single_user/#token-authentication). This means that users don't get a "real" identity, since all they provide is the shared token. For this reason, we call them "anonymous users".

They can still be differenciated, and they will each get assigned a different name e.g. in JupyterLab, but they will all have full access to any resource. For instance, they will be able to open all documents and to execute any code.

You can also disable token authentication in collaborative mode, just as in [single user mode](../single_user/#no-authentication):
```bash
jupyverse --set frontend.collaborative=true --set auth.mode=noauth
```

#### User authentication

It can be enabled by launching:
```bash
jupyverse --set frontend.collaborative=true --set auth.mode=user
```
In this mode, users have to be registered in a database before logging in. User information includes a user name and a password, that will be asked at login. It can also include a "real" name, that will be displayed when editing documents, and permissions that will determine if they can see or edit a document, run some code, etc.

### Using fps-auth-fief

[fps-auth-fief](../../plugins/auth/#fps-auth-fief) uses [Fief](https://www.fief.dev) to authenticate users. Fief itself can be hosted in the cloud or locally, but in any case it runs a separate server, and implements OAuth2 to access Jupyverse.

Fief allows to manage users using a dashboard. It supports permissions and Role-Based Access Control (RBAC).

Just launch in a terminal:
```bash
jupyverse --set frontend.collaborative=true
```
