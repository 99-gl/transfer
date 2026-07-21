FROM ubuntu:22.04

ENV CLAUDE_DIR=/cc_dir
ENV PATH=/cc_dir:${PATH}
ENV ANTHROPIC_BASE_URL=http://host.docker.internal:8005
ENV ANTHROPIC_AUTH_TOKEN=dummy
ENV ANTHROPIC_MODEL=qwen3-coder-30B-A3B

# Mount the host's Claude runtime here when starting the container:
#   docker run -it --rm --add-host=host.docker.internal:host-gateway \
#     -v /host/path/cc_dir:/cc_dir:ro agenticrl-claude-env
# The mounted directory must provide an executable named "claude".
# The host service must listen on 0.0.0.0:8005 (or the Docker bridge address),
# rather than only 127.0.0.1:8005.
WORKDIR /workspace
CMD ["/bin/bash"]
