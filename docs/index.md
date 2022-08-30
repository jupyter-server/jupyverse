Jupyverse is a [FastAPI](https://fastapi.tiangolo.com)-based Jupyter server. It can be used to run [JupyterLab](https://jupyterlab.readthedocs.io) and other web clients in different scenarios:

- On your personal machine: that's the most common use case, where you want to do interactive computing, most often running notebooks, in your local environment. Although JupyterLab runs in the browser, it really feels like a desktop application.
- Collaboratively: users work on the same document in real time, connected to the same server. That means they are on the same private network (LAN), or the server is hosted on the Internet. The user experience is similar to Google Docs.
- With access control: this becomes necessary when working collaboratively, as you don't want everybody to be able to see or change any thing. You want to know who users are and give them more or less permissions.
