---
sidebar_position: 2
---

# Installation

There are two ways to get started:

- [A local `pip` installation on your system](#pip).
- [Running the `pinnacledb` docker image](#docker-image).

## Pip

`pinnacledb` is available on [PyPi.org](https://pypi.org/project/pinnacledb/).

### Prerequisites

Before you begin the installation process, please make sure you have the following prerequisites in place:

#### Operating System

`pinnacledb` is compatible with several Linux distributions, including:

- MacOS
- Ubuntu
- Debian

#### Python Ecosystem

If you plan to install SuperDuperDB from source, you'll need the following:

- `python3.8` or later
- `pip` 22.0.4 or later

Your experience with `pinnacledb` on Linux may vary depending on your system and compute requirements.

### Installation

To install `pinnacledb` on your system using `pip`, open your terminal and run the following command:

```bash
pip install pinnacledb
```

This command will install `pinnacledb` along with a minimal set of  common dependencies required for running the framework. Some larger  dependencies, like `pytorch`, are not included to keep the image size small. You can install such dependencies using the following syntax:

```bash
pip install pinnacledb[<category>]
```

Here are the available categories you can use:

- `api`: Installs clients for third-party services like OpenAI, Cohere, and Anthropic.
- `torch`: Installs PyTorch dependencies.
- `docs`: Installs tools for rendering Markdown files into websites.
- `quality`: Installs tools for aiding in the development of high-quality code.
- `testing`: Installs tools for testing the SuperDuperDB ecosystem.
- `dev`: Installs all the above categories.
- `demo`: Installs all the common dependencies and the dependencies required for the `examples`.

You can find more details on these categories in the [pyproject.toml](https://github.com/SuperDuperDB/pinnacledb/blob/main/pyproject.toml) file.

## Docker Image

#### Using Pre-built Images

If you prefer using Docker, you can pull a pre-built Docker image from Docker Hub and run it with Docker version 19.03 or later:

```bash
docker run -p 8888:8888 pinnacledb/pinnacledb:latest
```

This command installs the base `pinnacledb` image. If you want to run  the ready-to-use examples, you'll need to download the required  dependencies at runtime. Alternatively, we provide a pre-built image  with all the dependencies for examples preinstalled:

```bash
docker run -p 8888:8888 pinnacledb/demo:latest
```

#### Building the image yourself

For more control, you can build the Docker images yourself using the following commands:

```bash
make build_pinnacledb
make build_demo
```

#### Hosted Docker Image

If you prefer a hassle-free solution, visit our hosted images at https://demo.pinnacledb.com. 
This way, you can use SuperDuperDB directly in your browser without the need for local installation.