FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV CLAUDE_DIR=/cc_dir
ENV PATH=/cc_dir:${PATH}

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    coreutils \
    git \
    less \
    procps \
    sudo \
    vim-tiny && \
    rm -rf /var/lib/apt/lists/*

# Mount the host's Claude runtime here when starting the container:
#   docker run -it --rm -v /host/path/cc_dir:/cc_dir:ro agenticrl-claude-env
# The mounted directory must provide an executable named "claude".
WORKDIR /workspace
CMD ["/bin/bash"]
