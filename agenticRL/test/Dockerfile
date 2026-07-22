FROM slimerl/slime:latest

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
RUN if ! id -u agent >/dev/null 2>&1; then useradd --create-home --shell /bin/bash agent; fi \
    && mkdir -p /workspace \
    && chown -R agent:agent /workspace /home/agent

WORKDIR /workspace
COPY --chown=agent:agent test_workspace/ /workspace/
ENV HOME=/home/agent
USER agent
CMD ["/bin/bash"]
