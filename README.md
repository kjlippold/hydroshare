# HydroShare _(hydroshare)_

HydroShare is a website and hydrologic information system for sharing hydrologic data and models aimed at giving users the cyberinfrastructure needed to innovate and collaborate in research to solve water problems.

#### Nightly Build Status generated by [Jenkins CI](http://ci.hydroshare.org:8080) (develop branch)

| Workflow | Clean | Build/Deploy | Unit Tests | Flake8 | Requirements |
| -------- | ----- | ------------ | ---------- | -------| ------------ |
| [![Build Status](http://ci.hydroshare.org:8080/job/nightly-build-workflow/badge/icon?style=plastic)](http://ci.hydroshare.org:8080/job/nightly-build-workflow/) | [![Build Status](http://ci.hydroshare.org:8080/job/nightly-build-clean/badge/icon?style=plastic)](http://ci.hydroshare.org:8080/job/nightly-build-clean/) | [![Build Status](http://ci.hydroshare.org:8080/job/nightly-build-deploy/badge/icon?style=plastic)](http://ci.hydroshare.org:8080/job/nightly-build-deploy/) | [![Build Status](http://ci.hydroshare.org:8080/job/nightly-build-test/badge/icon?style=plastic)](http://ci.hydroshare.org:8080/job/nightly-build-test/) | [![Build Status](http://ci.hydroshare.org:8080/job/nightly-build-flake8/badge/icon?style=plastic)](http://ci.hydroshare.org:8080/job/nightly-build-flake8/) | [![Requirements Status](https://requires.io/github/hydroshare/hs_docker_base/requirements.svg?branch=develop)](https://requires.io/github/hydroshare/hs_docker_base/requirements/?branch=master) | 

HydroShare is a website and hydrologic information system for sharing hydrologic data and models aimed at providing the cyberinfrastructure needed to enable innovation and collaboration in research to solve water problems. HydroShare is designed to advance hydrologic science by enabling the scientific community to more easily and freely share products resulting from their research, not just the scientific publication summarizing a study, but also the data and models used to create the scientific publication. With HydroShare users can: (1) share data and models with colleagues; (2) manage who has access to shared content; (3) share, access, visualize and manipulate a broad set of hydrologic data types and models; (4) use the web services API to program automated and client access; (5) publish data and models to meet the requirements of research project data management plans; (6) discover and access data and models published by others; and (7) use web apps to visualize, analyze, and run models on data in HydroShare.

More information can be found in our [Wiki Pages](https://github.com/hydroshare/hydroshare/wiki)

## Install

This README file is for developers interested in working on the Hydroshare code itself, or for developers or researchers learning about how the application works at a deeper level. If you simply want to _use_ the application, go to http://hydroshare.org and register an account.

If you want to install and run the source code of application locally and/or contribute to development, read on.

### [DOCKER](https://www.docker.com) development environment

We use docker to simplify the development process

### Install docker
#####Linux/Mac
[Installation Instructions](https://docs.docker.com/compose/install/)
#####Windows
[Install Docker for Windows and WSL](https://nickjanetakis.com/blog/setting-up-docker-for-windows-and-wsl-to-work-flawlessly)
######Windows Installation Summary
1. [Install Docker For Windows](https://docs.docker.com/docker-for-windows/install/)
    * Enable `Expose daemon on tcp://localhost:2375 without TLS` within Docker General Settings
2. [Install WSL](https://docs.microsoft.com/en-us/windows/wsl/install-win10)
3. [Install Docker within WSL](https://docs.docker.com/install/linux/docker-ce/ubuntu/)
4. [Install Docker-Compose within WSL](https://docs.docker.com/compose/install/)
5. Set DOCKER_HOST within .bashrc
    * `echo "export DOCKER_HOST=tcp://0.0.0.0:2375" >> ~/.bashrc && source ~/.bashrc`
6. Bind /mnt/c to /c (Assuming your drive is c)
    * `sudo mkdir /c`
    * `sudo mount --bind /mnt/c /c`
7. bind mount within .bashrc
    * `echo "sudo mount --bind /mnt/c /c" >> ~/.bashrc && source ~/.bashrc`
### Configuration
1. Clone this repository (the scripts won't work with CLRF line endings so make sure to turn off `core.autocrlf false` 
2. `cd` into the cloned repo folder
3. Edit config/hydroshare-config.yaml.  Replace `/home/hydro/hydroshare` with the path to your cloned repo for the following keys:
- HS_PATH
- HOST_SSL_DIR
- HS_LOG_FILES
- NGINX_DIR
- SSL_CERT_DIR
4. Within the base directory of the cloned repo folder run `./hsctl rebuild --db` to build the application and run it
5. If all goes well, your local version of Hydroshare should be running at http://localhost:8000
6. You can connect to the python interpreter via sftp (`ssh://hydro-service@localhost:1338` with path `/usr/bin/python`)

For more detailed installation, please see this document: [Getting Started with HydroShare](https://github.com/hydroshare/hydroshare/wiki/getting_started)

## Usage

For all intents and purposes, Hydroshare is a large Python/Django application with some extra features and technologies added on:
- SOLR for searching
- Redis for caching
- RabbitMQ for concurrency and serialization
- iRODS for a federated file system
- PostgreSQL for the database backend

#### The `hsctl` Script

The `hsctl` script is your primary tool in interacting with and running tasks against your Hydroshare install. It has the syntax `./hsccl [command]` where `[command]` is one of:

- `loaddb`: Deletes existing database and reloads the database specified in the `hydroshare-config.yaml` file.
- `managepy [args]`: Executes a `python manage.py [args]` call on the running hydroshare container.
- `maint_off`: Removes the maintenance page from view (only if NGINX is being used).
- `maint_on`: Displays the maintenance page in the browser (only if NGINX is being used).
- `rebuild`: Stops, removes and deletes only the hydroshare docker containers and images while retaining the database contents on the subsequent build as defined in the `hydroshare-config.yaml` file
- `rebuild --db`: Fully stops, removes and deletes any prior hydroshare docker containers, images and database contents prior to installing a clean copy of the hydroshare codebase as defined in the `hydroshare-config.yaml` file.
- `rebuild_index`: Rebuilds the solr/haystack index in a non-interactive way.
- `restart`: Restarts the django server only (and nginx if applicable).
- `start`: Starts all containers as defined in the `docker-compose.yml` file (and nginx if applicable).
- `stop`: Stops all containers as defined in the `docker-compose.yml` file.
- `update_index`: Updates the solr/haystack index in a non-interactive way.

## Testing and Debugging

### Testing

Tests are run via normal Django tools and conventions. However, you should use the `hsctl` script mentioned abouve with the `managepy` command. For example: `./hsctl managepy test hs_core.tests.api.rest.test_resmap --keepdb`.

There are currently over 600 tests in the system, so it is highly recommended that you run the test suites separately from one another.

### Debugging

You can debug via PyCharm by following the instructions [here](https://github.com/hydroshare/hydroshare/wiki/pycharm-configuration).

## Other Configuration Options

### Local iRODS

Local iRODS is _not_ required for development unless you are specifically working on the iRODS integration. However,if you want to work with iRODS or you simply want to learn about it, you can enable it locally.

### Local HTTPS

To enable HTTPS locally:
1. edit `config/hydroshare-config.template` and change the two values under `### Deployment Options ###` to `true` like so:
```
### Deployment Options ###
USE_NGINX: true
USE_SSL: true
```
2. Run `./hsctl rebuild`

## Contribute

There are many ways to contribute to Hydroshare. Review [Contributing guidelines](https://github.com/hydroshare/hydroshare/blob/develop/docs/contributing.rst) and github practices for information on
1. Opening issues for any bugs you find or suggestions you may have
2. Developing code to contribute to HydroShare 
3. Developing a HydroShare App
4. Submiting pull requests with code changes for review

## License 

Hydroshare is released under the BSD 3-Clause License. This means that [you can do what you want, so long as you don't mess with the trademark, and as long as you keep the license with the source code](https://tldrlegal.com/license/bsd-3-clause-license-(revised)).

©2017 CUAHSI. This material is based upon work supported by the National Science Foundation (NSF) under awards 1148453 and 1148090. Any opinions, findings, conclusions, or recommendations expressed in this material are those of the authors and do not necessarily reflect the views of the NSF.
