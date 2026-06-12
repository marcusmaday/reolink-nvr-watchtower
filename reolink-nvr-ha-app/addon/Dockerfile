# BUILD_FROM is injected by the workflow's build-args for each architecture.
# It resolves to the correct arch-specific HA base image (see build.yaml).
ARG BUILD_FROM
FROM $BUILD_FROM

# Fail fast on any error in a pipeline
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# ffmpeg is required by clip_generator.py for RTSP buffering and clip extraction.
# tzdata is needed so the container respects the HA timezone setting.
RUN apk add --no-cache \
    ffmpeg \
    tzdata

# Install Python dependencies.
# The build context is ./reolink-nvr-ha-app, so app/ and addon/ are both reachable.
WORKDIR /app

COPY app/requirements.txt requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application source
COPY app/ .

# Copy and prepare the add-on entry point
COPY addon/run.sh /run.sh
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
